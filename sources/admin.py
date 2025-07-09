from django.contrib import admin
from .models import Source, SourceFile, SourceFileChunk, SourceFileTable

# Register your models here.

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    """
    Source 模型的 Admin 配置
    """
    list_display = ['id', 'name', 'user', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['name', 'description', 'user__username', 'user__email']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('user', 'name', 'description')
        }),
        ('狀態設定', {
            'fields': ('is_public',)
        }),
        ('時間資訊', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    """
    SourceFile 模型的 Admin 配置
    """
    list_display = ['id', 'filename', 'source', 'user', 'format', 'size', 'status', 'created_at']
    list_filter = ['format', 'status', 'created_at']
    search_fields = ['filename', 'source__name', 'user__username', 'user__email']
    readonly_fields = ['uuid', 'created_at']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('user', 'source', 'filename', 'format', 'size')
        }),
        ('內容資訊', {
            'fields': ('summary', 'path', 'uuid', 'status', 'failed_reason')
        }),
        ('時間資訊', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SourceFileChunk)
class SourceFileChunkAdmin(admin.ModelAdmin):
    """
    SourceFileChunk 模型的 Admin 配置
    """
    list_display = ['id', 'source_file', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'source_file__filename', 'user__username']
    readonly_fields = ['created_at']


@admin.register(SourceFileTable)
class SourceFileTableAdmin(admin.ModelAdmin):
    """
    SourceFileTable 模型的 Admin 配置
    """
    list_display = ['table_name', 'database_name', 'source_file', 'user', 'created_at']
    list_filter = ['database_name', 'created_at']
    search_fields = ['table_name', 'database_name', 'source_file__filename', 'user__username']
    readonly_fields = ['created_at']
