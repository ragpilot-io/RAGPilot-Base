from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class UsernameAuthenticationForm(AuthenticationForm):
    """
    自定義登入表單，允許用戶使用 username 登入
    """
    username = forms.CharField(
        label='使用者名稱',
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full pl-10',
            'placeholder': '請輸入您的使用者名稱'
        })
    )
    
    password = forms.CharField(
        label='密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full pl-10',
            'placeholder': '請輸入密碼'
        })
    ) 