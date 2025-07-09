from django.contrib import admin
from django.utils.html import format_html
from .models import Session, Message


class HasErrorFilter(admin.SimpleListFilter):
    title = '錯誤狀態'
    parameter_name = 'has_error'

    def lookups(self, request, model_admin):
        return (
            ('yes', '有錯誤'),
            ('no', '無錯誤'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(traceback__isnull=True).exclude(traceback='')
        if self.value() == 'no':
            return queryset.filter(traceback__isnull=True) | queryset.filter(traceback='')
        return queryset


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['session_uuid', 'user', 'title', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__username', 'title']
    readonly_fields = ['session_uuid', 'created_at', 'updated_at']
    ordering = ['-updated_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'user', 'sender', 'content_type', 'tool_name', 'parent_message_display', 'has_error', 'is_deleted', 'updated_at']
    list_filter = ['sender', 'content_type', 'is_deleted', 'updated_at', 'tool_name', HasErrorFilter]
    search_fields = ['user__email', 'user__username', 'text', 'tool_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('session', 'user', 'message', 'sender', 'content_type', 'is_deleted', 'created_at', 'updated_at')
        }),
        ('內容', {
            'fields': ('text', 'references', 'citations', 'file_url', 'file_path')
        }),
        ('工具相關', {
            'fields': ('tool_name', 'tool_keywords'),
            'classes': ('collapse',)
        }),
        ('錯誤追蹤', {
            'fields': ('traceback',),
            'classes': ('collapse',)
        }),
    )

    def parent_message_display(self, obj):
        """顯示父訊息資訊"""
        if obj.message:
            return f"{obj.message.sender} (ID: {obj.message.id})"
        return "-"
    parent_message_display.short_description = "父訊息"

    def has_error(self, obj):
        """顯示是否有錯誤追蹤信息"""
        if obj.traceback:
            return "❌ 有錯誤"
        return "✅ 正常"
    has_error.short_description = "錯誤狀態"
    has_error.admin_order_field = 'traceback'

    def traceback_display(self, obj):
        """格式化顯示 traceback 信息"""
        if obj.traceback:
            # 將 traceback 包裝在 <pre> 標籤中以保持格式
            return format_html(
                '<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; '
                'font-size: 12px; overflow-x: auto; max-height: 300px; overflow-y: auto;">{}</pre>',
                obj.traceback
            )
        return "無錯誤記錄"
    traceback_display.short_description = "錯誤追蹤"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session', 'user')

    def restore_messages(self, request, queryset):
        """恢復軟刪除的訊息"""
        updated = queryset.filter(is_deleted=True).update(is_deleted=False)
        self.message_user(request, f'已恢復 {updated} 筆訊息')
    restore_messages.short_description = "恢復選中的訊息"

    def soft_delete_messages(self, request, queryset):
        """軟刪除訊息"""
        updated = queryset.filter(is_deleted=False).update(is_deleted=True)
        self.message_user(request, f'已軟刪除 {updated} 筆訊息')
    soft_delete_messages.short_description = "軟刪除選中的訊息"

    actions = ['restore_messages', 'soft_delete_messages']
