"""
URL configuration for RAGPilot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views. home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.conf import settings
from django.shortcuts import redirect

# 處理瀏覽器自動請求的圖標檔案
def favicon_redirect(request):
    return redirect(f'{settings.STATIC_URL}favicon.ico', permanent=True)

def apple_touch_icon_redirect(request):
    return redirect(f'{settings.STATIC_URL}apple-touch-icon.png', permanent=True)

def apple_touch_icon_precomposed_redirect(request):
    return redirect(f'{settings.STATIC_URL}apple-touch-icon-precomposed.png', permanent=True)

urlpatterns = [
    # 圖標檔案重定向路由（必須放在前面，避免被其他路由攔截）
    path('favicon.ico', favicon_redirect),
    path('apple-touch-icon.png', apple_touch_icon_redirect),
    path('apple-touch-icon-precomposed.png', apple_touch_icon_precomposed_redirect),
    
    # 應用程式路由
    path('', include('home.urls')),
    path('profile/', include('profiles.urls')),
    path('admin/', admin.site.urls),
    path('conversations/', include('conversations.urls')),
    path('sources/', include('sources.urls')),
    path('websites/', include('websites.urls')),  # websites URLs
    path('accounts/', include('allauth.urls')),  # allauth URLs
]

# 添加靜態檔案 URL 設定
# 開發環境：使用 Django 內建的靜態檔案服務
# 生產環境：靜態檔案由 WhiteNoise 中間件處理
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
