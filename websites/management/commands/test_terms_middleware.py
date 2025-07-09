"""
測試條款檢查middleware的Django管理命令
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from websites.models import Terms, UserTermsAgreement
import json

User = get_user_model()


class Command(BaseCommand):
    help = '測試條款檢查middleware的功能'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='testuser',
            help='用於測試的用戶名稱'
        )
        parser.add_argument(
            '--create-terms',
            action='store_true',
            help='創建測試條款'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        self.stdout.write(
            self.style.SUCCESS(f'🔧 開始測試條款檢查middleware...')
        )
        
        # 創建測試條款
        if options['create_terms']:
            self.create_test_terms()
        
        # 確保有測試用戶
        user = self.get_or_create_test_user(username)
        
        # 創建測試客戶端
        client = Client()
        
        # 測試未登入用戶
        self.test_anonymous_user(client)
        
        # 登入用戶
        client.force_login(user)
        
        # 測試未同意條款的用戶
        self.test_user_without_terms_agreement(client, user)
        
        # 同意條款
        self.agree_to_terms(client)
        
        # 測試已同意條款的用戶
        self.test_user_with_terms_agreement(client, user)
        
        self.stdout.write(
            self.style.SUCCESS('✅ 條款檢查middleware測試完成！')
        )

    def create_test_terms(self):
        """創建測試條款"""
        terms, created = Terms.objects.get_or_create(
            version='test_v1.0',
            defaults={
                'title': '測試使用條款',
                'content': '這是一個測試條款內容。',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'📋 已創建測試條款: {terms.title} v{terms.version}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'📋 測試條款已存在: {terms.title} v{terms.version}')
            )

    def get_or_create_test_user(self, username):
        """獲取或創建測試用戶"""
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@test.com',
                'is_active': True
            }
        )
        
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'👤 已創建測試用戶: {username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'👤 測試用戶已存在: {username}')
            )
        
        # 清除該用戶的所有條款同意記錄
        UserTermsAgreement.objects.filter(user=user).delete()
        self.stdout.write(
            self.style.SUCCESS(f'🗑️  已清除用戶 {username} 的條款同意記錄')
        )
        
        return user

    def test_anonymous_user(self, client):
        """測試未登入用戶"""
        self.stdout.write('\n🔍 測試未登入用戶...')
        
        # 測試首頁（應該可以訪問）
        response = client.get('/')
        self.stdout.write(
            f'   - 首頁訪問: {response.status_code} (預期: 200)'
        )
        
        # 測試需要登入的頁面（應該重定向到登入頁面）
        response = client.get('/sources/list/', follow=False)
        self.stdout.write(
            f'   - 資料源頁面: {response.status_code} (預期: 302重定向)'
        )

    def test_user_without_terms_agreement(self, client, user):
        """測試未同意條款的已登入用戶"""
        self.stdout.write(f'\n🔍 測試未同意條款的用戶 ({user.username})...')
        
        # 測試一般頁面（應該重定向到首頁）
        response = client.get('/sources/list/', follow=False)
        self.stdout.write(
            f'   - 資料源頁面: {response.status_code} (預期: 302重定向到首頁)'
        )
        
        # 測試AJAX請求（應該返回403錯誤）
        response = client.get(
            '/conversations/api/messages/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.stdout.write(
            f'   - AJAX請求: {response.status_code} (預期: 403)'
        )
        
        if response.status_code == 403:
            try:
                data = json.loads(response.content)
                if data.get('error') == 'terms_not_agreed':
                    self.stdout.write(
                        self.style.SUCCESS('   ✅ 正確返回條款未同意錯誤')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ 錯誤類型不正確: {data.get("error")}')
                    )
            except json.JSONDecodeError:
                self.stdout.write(
                    self.style.ERROR('   ❌ 響應不是有效的JSON')
                )

    def agree_to_terms(self, client):
        """讓用戶同意條款"""
        self.stdout.write('\n📝 同意條款...')
        
        # 模擬同意條款的POST請求
        response = client.post(
            '/websites/agree-to-terms/',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.stdout.write(
            f'   - 同意條款請求: {response.status_code} (預期: 200)'
        )
        
        if response.status_code == 200:
            try:
                data = json.loads(response.content)
                if data.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS('   ✅ 條款同意成功')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ 條款同意失敗: {data.get("message")}')
                    )
            except json.JSONDecodeError:
                self.stdout.write(
                    self.style.ERROR('   ❌ 響應不是有效的JSON')
                )

    def test_user_with_terms_agreement(self, client, user):
        """測試已同意條款的用戶"""
        self.stdout.write(f'\n🔍 測試已同意條款的用戶 ({user.username})...')
        
        # 測試一般頁面（應該可以正常訪問）
        response = client.get('/sources/list/')
        self.stdout.write(
            f'   - 資料源頁面: {response.status_code} (預期: 200)'
        )
        
        # 測試AJAX請求（應該可以正常訪問）
        response = client.get(
            '/websites/check-terms-status/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.stdout.write(
            f'   - AJAX請求: {response.status_code} (預期: 200)'
        )
        
        if response.status_code == 200:
            try:
                data = json.loads(response.content)
                if not data.get('needs_agreement'):
                    self.stdout.write(
                        self.style.SUCCESS('   ✅ 正確顯示已同意條款狀態')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('   ❌ 仍顯示需要同意條款')
                    )
            except json.JSONDecodeError:
                self.stdout.write(
                    self.style.ERROR('   ❌ 響應不是有效的JSON')
                )

    def style_message(self, level, message):
        """格式化訊息"""
        if level == 'success':
            return self.style.SUCCESS(message)
        elif level == 'warning':
            return self.style.WARNING(message)
        elif level == 'error':
            return self.style.ERROR(message)
        else:
            return message 