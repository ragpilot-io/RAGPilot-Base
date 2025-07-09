from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

class MessageStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    PROCESSING = 'processing', 'Processing'

# 共用內容型態 Enum
class ContentTypeChoices(models.TextChoices):
    TEXT = 'text', 'Text'
    AUDIO = 'audio', 'Audio'
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    FILE = 'file', 'File'


# 共用 sender Enum
class SenderChoices(models.TextChoices):
    USER = 'user', 'User'
    AI = 'ai', 'AI'
    TOOL = 'tool', 'Tool'


User = get_user_model()


class Session(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=128, blank=True)

    class Meta:
        verbose_name = "對話會話"
        verbose_name_plural = "對話會話"

    def __str__(self):
        user_info = self.user.email if self.user else "匿名用戶"
        return f"{user_info} - {self.title or str(self.session_uuid)[:8]}"

    @classmethod
    def get_or_create_user_session(cls, user):
        """取得或建立使用者的 session（目前每位使用者只有一個 session）"""
        session, created = cls.objects.get_or_create(
            user=user,
            defaults={'title': 'default'}
        )
        return session


class Message(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_messages')
    status = models.CharField(
        max_length=16,
        choices=MessageStatusChoices.choices,
        default=MessageStatusChoices.COMPLETED,
        db_index=True,
    )
    
    sender = models.CharField(
        max_length=16,
        choices=SenderChoices.choices,
        default=SenderChoices.USER,
        db_index=True,
    )
    content_type = models.CharField(
        max_length=16,
        choices=ContentTypeChoices.choices,
        default=ContentTypeChoices.TEXT,
        db_index=True,
    )
    text = models.TextField(blank=True, null=True, default=None)
    citations = models.JSONField(default=list, blank=True)
    file_url = models.URLField(blank=True, null=True, default=None)
    file_path = models.CharField(max_length=256, blank=True, null=True, default=None)
    traceback = models.TextField(blank=True, null=True, default=None)
    references = models.JSONField(default=None, blank=True, null=True)

    # Tool 專屬欄位（sender=TOOL 時才需填寫）
    tool_name = models.CharField(max_length=64, blank=True)
    tool_keywords = models.JSONField(default=list, blank=True)  # 儲存 keyword 清單

    # 軟刪除欄位
    is_deleted = models.BooleanField(
        default=False,
        help_text="軟刪除標記",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "對話訊息"
        verbose_name_plural = "對話訊息"
        ordering = ['-updated_at']

    def __str__(self):
        sender_display = self.get_sender_display()
        preview = (self.text[:50] + '...') if self.text and len(self.text) > 50 else (self.text or '')
        if self.sender == SenderChoices.TOOL:
            return f"[{sender_display}] {self.tool_name}: {preview}"
        return f"[{sender_display}] {preview}"

    def soft_delete(self):
        """軟刪除訊息"""
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])

    def get_child_messages(self):
        """取得子訊息（通常是相關的 Tool Messages）"""
        return self.child_messages.filter(is_deleted=False).order_by('created_at')

    def get_parent_message(self):
        """取得父訊息"""
        return self.message

    def get_related_tool_messages(self):
        """取得相關的工具訊息（如果這是 AI Message）"""
        if self.sender == SenderChoices.AI:
            return self.get_child_messages().filter(sender=SenderChoices.TOOL)
        return Message.objects.none()

    @classmethod
    def clear_conversation(cls, session):
        """清空對話（軟刪除所有訊息）"""
        return cls.objects.filter(session=session, is_deleted=False).update(is_deleted=True)

    @classmethod
    def create_user_message(cls, session, user, text):
        """建立使用者訊息記錄"""
        return cls.objects.create(
            session=session,
            user=user,
            sender=SenderChoices.USER,
            content_type=ContentTypeChoices.TEXT,
            text=text
        )

    @classmethod
    def create_ai_message(cls, session, user, text, status=None):
        """建立 AI 回覆訊息記錄"""
        return cls.objects.create(
            session=session,
            user=user,
            sender=SenderChoices.AI,
            content_type=ContentTypeChoices.TEXT,
            text=text,
            status=status or MessageStatusChoices.PENDING
        )

    @classmethod
    def create_tool_message(cls, session, user, tool_name, tool_params, tool_result=None):
        """建立 Tool 調用訊息記錄"""
        return cls.objects.create(
            session=session,
            user=user,
            sender=SenderChoices.TOOL,
            content_type=ContentTypeChoices.TEXT,
            tool_name=tool_name,
            tool_keywords=tool_params,
            text=tool_result
        )

    @classmethod
    def create_tool_message_with_parent(cls, session, user, parent_message, tool_name, tool_params, tool_result=None):
        """建立 Tool 調用訊息記錄，並關聯到父訊息（通常是 AI Message）"""
        return cls.objects.create(
            session=session,
            user=user,
            message=parent_message,  # 設置父訊息關聯
            sender=SenderChoices.TOOL,
            content_type=ContentTypeChoices.TEXT,
            tool_name=tool_name,
            tool_keywords=tool_params,
            text=tool_result
        )

    @classmethod
    def get_today_chat_amount(cls, user):
        """
        計算指定用戶今日的聊天次數（包含已刪除的訊息）
        
        Args:
            user: Django User 物件
            
        Returns:
            int: 今日聊天次數
        """
        if not user:
            return 0
            
        today = timezone.now().date()
        return cls.objects.filter(
            session__user=user,
            created_at__date=today
        ).count()

    @classmethod
    def get_monthly_chat_amount(cls, user):
        """
        計算指定用戶本月的聊天次數（包含已刪除的訊息）
        
        Args:
            user: Django User 物件
            
        Returns:
            int: 本月聊天次數
        """
        if not user:
            return 0
            
        now = timezone.now()
        current_month = now.month
        current_year = now.year
        
        return cls.objects.filter(
            session__user=user,
            created_at__year=current_year,
            created_at__month=current_month
        ).count()

    @property
    def today_chat_amount(self):
        """
        取得當前訊息所屬用戶的今日聊天次數
        
        Returns:
            int: 今日聊天次數
        """
        if not self.session or not self.session.user:
            return 0
        return self.__class__.get_today_chat_amount(self.session.user)

    @property
    def monthly_chat_amount(self):
        """
        取得當前訊息所屬用戶的本月聊天次數
        
        Returns:
            int: 本月聊天次數
        """
        if not self.session or not self.session.user:
            return 0
        return self.__class__.get_monthly_chat_amount(self.session.user)
