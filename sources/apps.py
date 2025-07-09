from django.apps import AppConfig


class SourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sources'
    
    def ready(self):
        # 導入信號處理器以確保它們被註冊
        import sources.signals
