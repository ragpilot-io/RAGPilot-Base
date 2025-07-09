from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth import logout, get_user_model
from django.http import HttpResponseRedirect
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.conf import settings
from .forms import UsernameAuthenticationForm
from .mixins import UserPlanContextMixin, TermsRequiredMixin
from utils.oauth_utils import is_google_oauth_enabled

User = get_user_model()

@method_decorator(never_cache, name='dispatch')
class HomeView(LoginRequiredMixin, UserPlanContextMixin, TemplateView):
    template_name = 'home.html'
    login_url = '/login/'  # 未登入時重定向的 URL

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        return context

class CustomLoginView(LoginView):
    template_name = 'login.html'
    form_class = UsernameAuthenticationForm  # 使用自定義表單
    success_url = reverse_lazy('home')  # 登入成功後重定向到首頁
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')  # 如果已登入，直接跳轉到首頁
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 添加用戶數量統計信息
        total_users = User.objects.count()
        max_users_limit = getattr(settings, 'MAX_USERS_LIMIT', 200)
        remaining_slots = max_users_limit - total_users
        usage_percentage = (total_users / max_users_limit) * 100 if max_users_limit > 0 else 0
        
        # 決定是否顯示狀態提示
        show_status = usage_percentage >= 80  # 使用率達到 80% 時開始顯示
        
        if show_status:
            if usage_percentage >= 100:
                status_class = 'alert-error'
                status_icon = '🚫'
                status_title = '註冊已暫停'
                status_message = f'系統已達用戶上限（{max_users_limit}人），暫時無法接受新用戶註冊。如需註冊請聯繫管理員。'
            elif usage_percentage >= 95:
                status_class = 'alert-warning'
                status_icon = '⚠️'
                status_title = '名額緊張'
                status_message = f'系統接近用戶上限，僅剩 {remaining_slots} 個註冊名額。'
            elif usage_percentage >= 90:
                status_class = 'alert-warning'
                status_icon = '📢'
                status_title = '名額有限'
                status_message = f'系統用戶數量較多，剩餘 {remaining_slots} 個註冊名額。'
            else:  # >= 80%
                status_class = 'alert-info'
                status_icon = 'ℹ️'
                status_title = '系統提示'
                status_message = f'目前系統用戶較多，剩餘 {remaining_slots} 個註冊名額。'
        
        # 檢查 Google OAuth 是否可用
        google_oauth_enabled = is_google_oauth_enabled()
        
        context.update({
            'user_limit_status': {
                'show_status': show_status,
                'status_class': status_class if show_status else '',
                'status_icon': status_icon if show_status else '',
                'status_title': status_title if show_status else '',
                'status_message': status_message if show_status else '',
                'total_users': total_users,
                'max_users_limit': max_users_limit,
                'remaining_slots': remaining_slots,
                'usage_percentage': round(usage_percentage, 1),
            },
            'google_oauth_enabled': google_oauth_enabled,
        })
        
        return context

class CustomLogoutView(View):
    """
    自定義登出視圖，確保正確清除會話並重定向到登入頁
    """
    def get(self, request):
        return self.logout_user(request)
    
    def post(self, request):
        return self.logout_user(request)
    
    def logout_user(self, request):
        # 清除會話
        logout(request)
        
        # 創建重定向響應
        response = HttpResponseRedirect('/login/')
        
        # 添加緩存控制標頭，防止瀏覽器緩存
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
