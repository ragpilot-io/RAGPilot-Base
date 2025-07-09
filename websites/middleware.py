"""
條款同意檢查中介軟體
防止用戶透過修改前端HTML繞過條款同意檢查
"""
import re
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from .models import Terms, UserTermsAgreement


class TermsAgreementMiddleware(MiddlewareMixin):
    """
    條款同意檢查中介軟體
    
    在每個請求中檢查已登入用戶是否已同意最新條款
    如果沒有同意，則阻止訪問並要求同意條款
    """
    
    # 不需要檢查條款的URL模式（使用正則表達式）
    EXEMPT_URL_PATTERNS = [
        r'^/login/',                    # 登入頁面
        r'^/logout/',                   # 登出頁面  
        r'^/accounts/',                 # allauth 相關頁面
        r'^/admin/',                    # 管理員頁面
        r'^/static/',                   # 靜態檔案
        r'^/media/',                    # 媒體檔案
        r'^/websites/agree-to-terms/',  # 條款同意API
        r'^/websites/check-terms-status/', # 條款檢查API
        r'^/favicon\.ico$',             # 網站圖示
        r'^/ws/',                       # WebSocket 連線
        r'^/api/health/',               # 健康檢查
        r'^/conversations/',            # 對話相關API（避免WebSocket衝突）
        r'^/api/.*-suggestions/',       # 問題建議API
    ]
    
    # 需要條款檢查的頁面URL模式（只檢查主要功能頁面）
    PROTECTED_PAGE_PATTERNS = [
        r'^/sources/',                  # 自建資料源頁面
        r'^/profile/',                  # 個人資料頁面
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        # 編譯正則表達式以提高效能
        self.exempt_patterns = [re.compile(pattern) for pattern in self.EXEMPT_URL_PATTERNS]
        self.protected_patterns = [re.compile(pattern) for pattern in self.PROTECTED_PAGE_PATTERNS]
        super().__init__(get_response)
    
    def __call__(self, request):
        response = self.process_request(request)
        if response:
            return response
        
        response = self.get_response(request)
        return response
    
    def process_request(self, request):
        """
        處理請求前的條款檢查 - 只檢查受保護的頁面
        """
        # 檢查是否為免檢查的URL
        if self._is_exempt_url(request.path):
            return None
            
        # 只對受保護的頁面進行條款檢查
        if not self._is_protected_page(request.path):
            return None
        
        # 安全地檢查用戶認證狀態（避免異步問題）
        try:
            # 檢查是否有session
            if not hasattr(request, 'session') or not request.session.session_key:
                return None
                
            # 檢查用戶是否已登入（避免觸發異步操作）
            user = getattr(request, 'user', None)
            if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
                return None
            
            # 檢查用戶是否已同意最新條款
            if not self._has_agreed_to_latest_terms(user):
                return self._handle_terms_not_agreed(request)
                
        except Exception as e:
            # 如果檢查過程中發生任何錯誤，為了避免影響正常功能，直接跳過檢查
            return None
        
        return None
    
    def _is_exempt_url(self, path):
        """
        檢查URL是否為免檢查路徑
        """
        return any(pattern.match(path) for pattern in self.exempt_patterns)
    
    def _is_protected_page(self, path):
        """
        檢查URL是否為需要條款檢查的受保護頁面
        """
        return any(pattern.match(path) for pattern in self.protected_patterns)
    
    def _has_agreed_to_latest_terms(self, user):
        """
        檢查用戶是否已同意最新條款
        """
        try:
            return UserTermsAgreement.has_agreed_to_latest(user)
        except Exception:
            # 如果檢查過程中發生錯誤，為了安全起見，視為未同意
            return False
    
    def _handle_terms_not_agreed(self, request):
        """
        處理用戶未同意條款的情況 - 重定向到首頁並彈出條款
        """
        # 添加查詢參數來觸發條款彈窗
        redirect_url = '/?force_terms=1'
        return HttpResponseRedirect(redirect_url)
    
    def _get_terms_agreement_url(self):
        """
        獲取條款同意頁面的URL
        """
        try:
            return reverse('check_terms_status')
        except Exception:
            return '/websites/check-terms-status/'


class TermsSecurityMiddleware(MiddlewareMixin):
    """
    條款安全性中介軟體
    
    添加額外的安全檢查，防止通過各種方式繞過條款檢查
    支持異步環境
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    async def __call__(self, request):
        # 檢查是否為異步環境
        if hasattr(self.get_response, '_is_coroutine'):
            response = await self.get_response(request)
        else:
            response = self.get_response(request)
        
        return self.process_response(request, response)
    
    def process_response(self, request, response):
        """
        在響應中添加安全標頭
        """
        try:
            # 防止頁面被嵌入iframe（防止點擊劫持）
            if hasattr(response, '__getitem__') and 'X-Frame-Options' not in response:
                response['X-Frame-Options'] = 'DENY'
            
            # 防止MIME類型嗅探
            if hasattr(response, '__getitem__') and 'X-Content-Type-Options' not in response:
                response['X-Content-Type-Options'] = 'nosniff'
            
            # 對於包含條款相關內容的頁面，添加快取控制
            if (hasattr(request, 'user') and 
                hasattr(request.user, 'is_authenticated') and
                request.user.is_authenticated and 
                'terms' in request.path.lower()):
                if hasattr(response, '__setitem__'):
                    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                    response['Pragma'] = 'no-cache'
                    response['Expires'] = '0'
        except Exception:
            # 如果在添加標頭時發生任何錯誤，跳過以避免影響正常功能
            pass
        
        return response


# get_client_ip 函數已在 views.py 中定義 