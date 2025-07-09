from profiles.models import Limit, Profile
from conversations.models import Message
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.mixins import AccessMixin


class UserPlanContextMixin:
    """
    提供用戶方案相關的 context 資料的 Mixin
    """
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 只有登入用戶才提供方案資訊
        if self.request.user.is_authenticated:
            user = self.request.user
            
            # 獲取用戶的方案資訊
            limit, created = Limit.objects.get_or_create(user=user)
            profile, created = Profile.objects.get_or_create(user=user)
            
            # 計算本月聊天次數
            monthly_chat_count = Message.get_monthly_chat_amount(user)
            
            # 計算私有資料源數量
            from sources.models import Source
            private_source_count = Source.objects.filter(
                user=user
            ).count()
            
            # 檢查用戶權限層級
            is_superuser = user.is_superuser
            is_collaborator = profile.is_collaborator
            
            # 各項功能的限制狀態
            has_unlimited_chat = is_superuser or is_collaborator  # 超級使用者和協作者都有無限對話
            has_unlimited_source = is_superuser  # 只有超級使用者有無限資料源
            has_unlimited_files = is_superuser  # 只有超級使用者有無限檔案
            
            # 檢查是否超過聊天限制
            is_over_chat_limit = not has_unlimited_chat and monthly_chat_count >= limit.chat_limit_per_month
            
            context.update({
                'user_limit': limit,
                'user_profile': profile,
                'monthly_chat_count': monthly_chat_count,
                'private_source_count': private_source_count,
                'is_unlimited': has_unlimited_chat,  # 為了向後相容，保留這個變數名
                'has_unlimited_chat': has_unlimited_chat,
                'has_unlimited_source': has_unlimited_source,
                'has_unlimited_files': has_unlimited_files,
                'is_over_chat_limit': is_over_chat_limit,
            })
        else:
            # 未登入用戶的預設值
            context.update({
                'user_limit': None,
                'user_profile': None,
                'monthly_chat_count': 0,
                'private_source_count': 0,
                'is_unlimited': False,
                'has_unlimited_chat': False,
                'has_unlimited_source': False,
                'has_unlimited_files': False,
                'is_over_chat_limit': False,
            })
        
        return context 


class TermsRequiredMixin(AccessMixin):
    """
    條款檢查 Mixin
    
    驗證已登入用戶是否已同意最新條款
    類似於 LoginRequiredMixin 的使用方式
    """
    
    def dispatch(self, request, *args, **kwargs):
        # 首先檢查用戶是否已登入
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # 檢查是否已同意最新條款
        if not self.has_agreed_to_latest_terms():
            return self.handle_terms_not_agreed()
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_agreed_to_latest_terms(self):
        """
        檢查用戶是否已同意最新條款
        """
        try:
            from websites.models import UserTermsAgreement
            return UserTermsAgreement.has_agreed_to_latest(self.request.user)
        except Exception:
            # 如果檢查過程中發生錯誤，為了安全起見，視為未同意
            return False
    
    def handle_terms_not_agreed(self):
        """
        處理用戶未同意條款的情況
        """
        # 判斷是否為 AJAX 請求
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           self.request.content_type == 'application/json':
            # AJAX 請求返回 JSON 錯誤
            return JsonResponse({
                'error': 'terms_not_agreed',
                'message': '您需要先同意使用條款才能使用此功能',
                'redirect_url': '/?force_terms=1'
            }, status=403)
        else:
            # 一般頁面請求重定向到首頁並彈出條款
            return HttpResponseRedirect('/?force_terms=1')
    
    def handle_no_permission(self):
        """
        覆寫父類方法以提供自定義的未登入處理
        """
        # 判斷是否為 AJAX 請求
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           self.request.content_type == 'application/json':
            # AJAX 請求返回 JSON 錯誤
            return JsonResponse({
                'error': 'authentication_required',
                'message': '您需要先登入才能使用此功能',
                'redirect_url': '/login/'
            }, status=403)
        else:
            # 一般頁面請求重定向到登入頁面
            return HttpResponseRedirect('/login/') 