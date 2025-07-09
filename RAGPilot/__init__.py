# 這將確保在 Django 啟動時載入 Celery 應用程式
from .celery import app as celery_app

__all__ = ('celery_app',)
