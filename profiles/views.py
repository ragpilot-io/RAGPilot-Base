from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from home.mixins import TermsRequiredMixin
from django.views import View
from django.contrib.auth import update_session_auth_hash, logout
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings

from .forms import UserProfileForm, CustomPasswordChangeForm, CustomSetPasswordForm
from .models import Limit, Profile
from conversations.models import Message
from utils.oauth_utils import is_google_oauth_enabled

# Create your views here.

@method_decorator(never_cache, name='dispatch')
class ProfileView(TermsRequiredMixin, View):
    """
    個人資料管理視圖
    """
    login_url = '/login/'
    template_name = 'profile.html'
    
    def get(self, request):
        profile_form = UserProfileForm(instance=request.user)
        
        # 檢查用戶是否有可用的密碼
        has_usable_password = request.user.has_usable_password()
        
        if has_usable_password:
            # 用戶已有密碼，使用密碼修改表單
            password_form = CustomPasswordChangeForm(user=request.user)
            password_form_type = 'change'
        else:
            # 用戶沒有密碼（如 Google 登入用戶），使用設定密碼表單
            password_form = CustomSetPasswordForm(user=request.user)
            password_form_type = 'set'
        
        # 獲取或創建使用者的 Limit 和 Profile 記錄
        limit, created = Limit.objects.get_or_create(user=request.user)
        profile, created = Profile.objects.get_or_create(user=request.user)
        
        # 檢查用戶權限層級
        is_superuser = request.user.is_superuser
        is_collaborator = profile.is_collaborator
        
        # 各項功能的限制狀態
        has_unlimited_chat = is_superuser or is_collaborator  # 超級使用者和協作者都有無限對話
        has_unlimited_source = is_superuser  # 只有超級使用者有無限資料源
        has_unlimited_files = is_superuser  # 只有超級使用者有無限檔案
        
        # 計算本月聊天次數（包含已刪除的訊息）
        monthly_chat_count = Message.get_monthly_chat_amount(request.user)
        
        # 計算私有資料源數量
        from sources.models import Source
        private_source_count = Source.objects.filter(
            user=request.user
        ).count()
        
        # 計算使用百分比
        chat_usage_percentage = 0 if has_unlimited_chat else (
            (monthly_chat_count / limit.chat_limit_per_month * 100) if limit.chat_limit_per_month > 0 else 0
        )
        source_usage_percentage = 0 if has_unlimited_source else (
            (private_source_count / limit.private_source_limit * 100) if limit.private_source_limit > 0 else 0
        )
        
        # 檢查 Google OAuth 可用性
        google_oauth_enabled = is_google_oauth_enabled()
        
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
            'password_form_type': password_form_type,
            'has_usable_password': has_usable_password,
            'user': request.user,
            'user_limit': limit,
            'user_profile': profile,
            'monthly_chat_count': monthly_chat_count,
            'private_source_count': private_source_count,
            'chat_usage_percentage': chat_usage_percentage,
            'source_usage_percentage': source_usage_percentage,
            'is_superuser': is_superuser,
            'is_collaborator': is_collaborator,
            'has_unlimited_chat': has_unlimited_chat,
            'has_unlimited_source': has_unlimited_source,
            'has_unlimited_files': has_unlimited_files,
            'google_oauth_enabled': google_oauth_enabled,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'update_profile':
            return self._handle_profile_update(request)
        elif action == 'change_password':
            return self._handle_password_change(request)
        elif action == 'set_password':
            return self._handle_password_set(request)
        elif action == 'delete_account':
            return self._handle_account_deletion(request)
        
        return self.get(request)
    
    def _handle_profile_update(self, request):
        """處理個人資料更新"""
        profile_form = UserProfileForm(request.POST, instance=request.user)
        
        # 根據用戶密碼狀態選擇表單
        has_usable_password = request.user.has_usable_password()
        if has_usable_password:
            password_form = CustomPasswordChangeForm(user=request.user)
            password_form_type = 'change'
        else:
            password_form = CustomSetPasswordForm(user=request.user)
            password_form_type = 'set'
        
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, '個人資料已成功更新！')
            return redirect('profile')
        else:
            messages.error(request, '個人資料更新失敗，請檢查輸入的資料。')
        
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
            'password_form_type': password_form_type,
            'has_usable_password': has_usable_password,
            'user': request.user,
        }
        return render(request, self.template_name, context)
    
    def _handle_password_change(self, request):
        """處理密碼修改（適用於已有密碼的用戶）"""
        profile_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # 重要：更新會話，避免用戶被登出
            messages.success(request, '密碼已成功修改！')
            return redirect('profile')
        else:
            messages.error(request, '密碼修改失敗，請檢查輸入的密碼。')
        
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
            'password_form_type': 'change',
            'has_usable_password': True,
            'user': request.user,
        }
        return render(request, self.template_name, context)
    
    def _handle_password_set(self, request):
        """處理密碼設定（適用於沒有密碼的用戶，如 Google 登入用戶）"""
        profile_form = UserProfileForm(instance=request.user)
        password_form = CustomSetPasswordForm(user=request.user, data=request.POST)
        
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # 重要：更新會話，避免用戶被登出
            messages.success(request, '🎉 密碼設定成功！您現在可以使用 username + 密碼的方式登入了。')
            return redirect('profile')
        else:
            messages.error(request, '密碼設定失敗，請檢查輸入的密碼。')
        
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
            'password_form_type': 'set',
            'has_usable_password': False,
            'user': request.user,
        }
        return render(request, self.template_name, context)
    
    def _handle_account_deletion(self, request):
        """處理帳號刪除"""
        confirmation = request.POST.get('confirmation', '').strip()
        
        if confirmation != request.user.username:
            messages.error(request, '確認文字不正確，帳號刪除失敗。')
            return redirect('profile')
        
        # 刪除使用者帳號
        username = request.user.username
        request.user.delete()
        logout(request)
        
        messages.success(request, f'帳號 {username} 已成功刪除。感謝您的使用！')
        return redirect('home')
