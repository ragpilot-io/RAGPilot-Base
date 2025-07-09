from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfileForm(forms.ModelForm):
    """
    用戶個人資料編輯表單
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 將 username 和 email 欄位設為不可編輯
        if self.instance and self.instance.pk:
            self.fields['username'].disabled = True
            self.fields['username'].help_text = '使用者名稱不可更改，以確保系統穩定性'
            self.fields['email'].disabled = True
            self.fields['email'].help_text = 'Email 不可更改，以確保帳號安全性'
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        labels = {
            'username': '使用者名稱',
            'email': 'Email',
            'first_name': '名',
            'last_name': '姓',
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input input-bordered w-full bg-gray-100',
                'placeholder': '使用者名稱不可更改',
                'readonly': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input input-bordered w-full bg-gray-100',
                'placeholder': 'Email 不可更改',
                'readonly': True
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': '請輸入名'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': '請輸入姓'
            }),
        }
    
    def clean_username(self):
        """
        確保 username 不會被更改
        """
        if self.instance and self.instance.pk:
            # 如果是編輯現有用戶，返回原始的 username
            return self.instance.username
        return self.cleaned_data.get('username')
    
    def clean_email(self):
        """
        確保 email 不會被更改
        """
        if self.instance and self.instance.pk:
            # 如果是編輯現有用戶，返回原始的 email
            return self.instance.email
        return self.cleaned_data.get('email')


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    自定義密碼修改表單（適用於已有密碼的用戶）
    """
    old_password = forms.CharField(
        label='當前密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '請輸入當前密碼'
        })
    )
    new_password1 = forms.CharField(
        label='新密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '請輸入新密碼'
        })
    )
    new_password2 = forms.CharField(
        label='確認新密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '請再次輸入新密碼'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    """
    自定義設定密碼表單（適用於沒有密碼的用戶，如 Google 登入用戶）
    """
    new_password1 = forms.CharField(
        label='設定密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '請設定您的登入密碼'
        }),
        help_text='設定密碼後，您可以使用 username + 密碼的方式登入'
    )
    new_password2 = forms.CharField(
        label='確認密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '請再次輸入密碼'
        })
    ) 