"""
OAuth 相關工具函數
"""
import os
from django.conf import settings


def is_google_oauth_enabled():
    """
    檢查 Google OAuth 是否已正確設定並啟用
    
    Returns:
        bool: True 如果 Google OAuth 已設定，False 否則
    """
    # 可以直接使用 settings 中的設定
    return getattr(settings, 'GOOGLE_OAUTH_ENABLED', False)


def get_google_oauth_status():
    """
    取得 Google OAuth 的詳細狀態資訊
    
    Returns:
        dict: 包含 Google OAuth 狀態的詳細資訊
    """
    client_id = getattr(settings, 'GOOGLE_OAUTH2_CLIENT_ID', None)
    client_secret = getattr(settings, 'GOOGLE_OAUTH2_CLIENT_SECRET', None)
    oauth_enabled = getattr(settings, 'GOOGLE_OAUTH_ENABLED', False)
    
    return {
        'has_client_id': bool(client_id),
        'has_client_secret': bool(client_secret),
        'is_enabled': oauth_enabled,
        'providers_configured': 'google' in getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}),
    }


def check_oauth_environment():
    """
    檢查 OAuth 環境設定狀態
    
    Returns:
        tuple: (is_enabled, status_message)
    """
    status = get_google_oauth_status()
    
    if status['is_enabled']:
        return True, "Google OAuth 已正確設定並啟用"
    elif not status['has_client_id'] or not status['has_client_secret']:
        return False, "缺少必要的環境變數：GOOGLE_OAUTH2_CLIENT_ID 或 GOOGLE_OAUTH2_CLIENT_SECRET"
    else:
        return False, "Google OAuth 設定不完整"


def check_google_oauth_redirect():
    """
    檢查 Google OAuth 重新導向 URL 設定
    
    Returns:
        dict: 包含重新導向相關資訊
    """
    try:
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
        
        # 獲取 callback URL
        callback_url = getattr(GoogleOAuth2Adapter, 'callback_url', None)
        
        print(f"Google OAuth Adapter callback_url: {callback_url}")
        
        # 檢查 settings 中的 REDIRECT_URI 設定
        redirect_uri_from_settings = None
        if hasattr(settings, 'SOCIALACCOUNT_PROVIDERS') and 'google' in settings.SOCIALACCOUNT_PROVIDERS:
            redirect_uri_from_settings = settings.SOCIALACCOUNT_PROVIDERS['google'].get('REDIRECT_URI')
        
        print(f"Settings 中的 REDIRECT_URI: {redirect_uri_from_settings}")
        
        return {
            'adapter_callback_url': callback_url,
            'settings_redirect_uri': redirect_uri_from_settings,
            'status': 'success'
        }
        
    except ImportError as e:
        error_msg = f"無法導入 GoogleOAuth2Adapter: {e}"
        print(error_msg)
        return {
            'error': error_msg,
            'status': 'error'
        }
    except Exception as e:
        error_msg = f"檢查 Google OAuth 重新導向時發生錯誤: {e}"
        print(error_msg)
        return {
            'error': error_msg,
            'status': 'error'
        } 