from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.conf import settings
from .models import Limit, Profile

User = get_user_model()

# Register your models here.

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Profile 模型的 Admin 配置
    """
    list_display = ['user', 'is_collaborator', 'created_at', 'updated_at']
    list_filter = ['is_collaborator', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('使用者資訊', {
            'fields': ('user',)
        }),
        ('權限設定', {
            'fields': ('is_collaborator',)
        }),
        ('時間資訊', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def changelist_view(self, request, extra_context=None):
        """
        在 Profile 管理頁面顯示用戶數量統計
        """
        extra_context = extra_context or {}
        
        # 獲取用戶數量統計
        total_users = User.objects.count()
        max_users_limit = getattr(settings, 'MAX_USERS_LIMIT', 200)
        remaining_slots = max_users_limit - total_users
        usage_percentage = (total_users / max_users_limit) * 100 if max_users_limit > 0 else 0
        
        # 設定狀態顏色
        if usage_percentage >= 100:
            status_color = '#dc3545'  # 紅色
            status_text = '已達上限'
        elif usage_percentage >= 90:
            status_color = '#fd7e14'  # 橙色
            status_text = '接近上限'
        elif usage_percentage >= 80:
            status_color = '#ffc107'  # 黃色
            status_text = '使用偏高'
        else:
            status_color = '#28a745'  # 綠色
            status_text = '正常'
        
        extra_context['user_stats'] = {
            'total_users': total_users,
            'max_users_limit': max_users_limit,
            'remaining_slots': remaining_slots,
            'usage_percentage': round(usage_percentage, 1),
            'status_color': status_color,
            'status_text': status_text,
        }
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Limit)
class LimitAdmin(admin.ModelAdmin):
    """
    Limit 模型的 Admin 配置
    """
    list_display = ['user', 'chat_limit_per_month', 'private_source_limit', 'file_limit_per_source', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('使用者資訊', {
            'fields': ('user',)
        }),
        ('使用限制', {
            'fields': ('chat_limit_per_month', 'private_source_limit', 'file_limit_per_source')
        }),
        ('時間資訊', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
