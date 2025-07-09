from django.contrib import admin
from .models import Terms, UserTermsAgreement, Announcement


@admin.register(Terms)
class TermsAdmin(admin.ModelAdmin):
    list_display = ['title', 'version', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'version']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('title', 'version', 'is_active')
        }),
        ('條款內容', {
            'fields': ('content',),
            'description': '請使用 Markdown 格式編寫條款內容'
        }),
        ('時間資訊', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """儲存時自動處理版本控制"""
        super().save_model(request, obj, form, change)
        
        # 如果設定為 active，確保其他條款都是 inactive
        if obj.is_active:
            Terms.objects.exclude(id=obj.id).update(is_active=False)


@admin.register(UserTermsAgreement)
class UserTermsAgreementAdmin(admin.ModelAdmin):
    list_display = ['user', 'terms_title', 'terms_version', 'agreed_at']
    list_filter = ['agreed_at', 'terms__version']
    search_fields = ['user__username', 'user__email', 'terms__title']
    readonly_fields = ['user', 'terms', 'agreed_at', 'user_agent']
    
    def terms_title(self, obj):
        return obj.terms.title
    terms_title.short_description = '條款標題'
    
    def terms_version(self, obj):
        return obj.terms.version
    terms_version.short_description = '條款版本'

    def has_add_permission(self, request):
        """不允許手動新增同意記錄"""
        return False

    def has_change_permission(self, request, obj=None):
        """不允許修改同意記錄"""
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_important', 'is_active', 'is_currently_active_display', 'created_by', 'start_date', 'end_date', 'created_at']
    list_filter = ['is_active', 'is_important', 'created_by', 'created_at', 'start_date']
    search_fields = ['title', 'content', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('title', 'is_important', 'is_active')
        }),
        ('公告內容', {
            'fields': ('content',),
            'description': '請使用 Markdown 格式編寫公告內容'
        }),
        ('顯示時間設定', {
            'fields': ('start_date', 'end_date'),
            'description': '結束時間預設為建立後三天，留空表示永久顯示'
        }),
        ('管理資訊', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_currently_active_display(self, obj):
        return obj.is_currently_active
    is_currently_active_display.boolean = True
    is_currently_active_display.short_description = '目前是否活躍'
    
    def save_model(self, request, obj, form, change):
        """儲存時自動設定發布者"""
        if not change:  # 新建時設定發布者
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """優化查詢"""
        return super().get_queryset(request).select_related('created_by')
