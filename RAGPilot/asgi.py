"""
ASGI config for RAGPilot project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RAGPilot.settings')

# 使用標準的 Django ASGI application（不再支援 WebSocket）
application = get_asgi_application()
