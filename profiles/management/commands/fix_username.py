import re
import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.socialaccount.models import SocialAccount

User = get_user_model()


class Command(BaseCommand):
    help = '修復過短的 username 問題'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='只檢查問題，不進行修復',
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='修復所有過短的 username',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='修復指定的 username',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Username 修復工具 ===\n')
        )

        if options['check_only']:
            self.check_problematic_usernames()
        elif options['fix_all']:
            self.fix_all_problematic_usernames()
        elif options['username']:
            self.fix_specific_username(options['username'])
        else:
            self.check_problematic_usernames()
            self.stdout.write('\n使用參數：')
            self.stdout.write('  --check-only : 只檢查問題')
            self.stdout.write('  --fix-all : 修復所有問題')
            self.stdout.write('  --username [用戶名] : 修復指定用戶')

    def check_problematic_usernames(self):
        """檢查有問題的 username"""
        self.stdout.write(self.style.WARNING('🔍 檢查過短的 username...'))
        
        # 查找長度小於 3 的 username
        short_usernames = User.objects.filter(username__regex=r'^.{1,2}$')
        
        if not short_usernames.exists():
            self.stdout.write(self.style.SUCCESS('✅ 沒有找到過短的 username'))
            return
        
        self.stdout.write(f'❌ 找到 {short_usernames.count()} 個過短的 username：')
        
        for user in short_usernames:
            # 查找相關的社交帳戶
            social_accounts = SocialAccount.objects.filter(user=user)
            
            self.stdout.write(f'   • 用戶 ID: {user.id}')
            self.stdout.write(f'     Username: "{user.username}"')
            self.stdout.write(f'     Email: {user.email}')
            self.stdout.write(f'     註冊時間: {user.date_joined}')
            
            for social_account in social_accounts:
                self.stdout.write(f'     社交帳戶: {social_account.provider}')
                if social_account.extra_data:
                    email = social_account.extra_data.get('email', '')
                    name = social_account.extra_data.get('name', '')
                    given_name = social_account.extra_data.get('given_name', '')
                    family_name = social_account.extra_data.get('family_name', '')
                    
                    self.stdout.write(f'       Email: {email}')
                    self.stdout.write(f'       Name: {name}')
                    self.stdout.write(f'       Given name: {given_name}')
                    self.stdout.write(f'       Family name: {family_name}')
            
            self.stdout.write('')

    def fix_all_problematic_usernames(self):
        """修復所有有問題的 username"""
        self.stdout.write(self.style.WARNING('🔧 開始修復所有過短的 username...'))
        
        short_usernames = User.objects.filter(username__regex=r'^.{1,2}$')
        
        if not short_usernames.exists():
            self.stdout.write(self.style.SUCCESS('✅ 沒有找到需要修復的 username'))
            return
        
        for user in short_usernames:
            self.fix_user_username(user)

    def fix_specific_username(self, username):
        """修復指定的 username"""
        try:
            user = User.objects.get(username=username)
            self.stdout.write(f'🔧 修復用戶 "{username}" 的 username...')
            self.fix_user_username(user)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ 找不到用戶 "{username}"'))

    def fix_user_username(self, user):
        """修復單個用戶的 username"""
        old_username = user.username
        
        # 嘗試從社交帳戶取得資料
        social_accounts = SocialAccount.objects.filter(user=user)
        
        username_candidates = []
        
        for social_account in social_accounts:
            if social_account.extra_data:
                email = social_account.extra_data.get('email', '')
                name = social_account.extra_data.get('name', '')
                given_name = social_account.extra_data.get('given_name', '')
                family_name = social_account.extra_data.get('family_name', '')
                
                # 按照新的優先順序添加候選項
                if email:
                    local_part = email.split('@')[0]
                    username_candidates.append(local_part)
                
                if name:
                    username_candidates.append(name.replace(' ', ''))
                
                if given_name and family_name:
                    username_candidates.append(f"{given_name}{family_name}")
                
                if given_name:
                    username_candidates.append(given_name)
        
        # 如果沒有社交帳戶資料，使用用戶的 email
        if not username_candidates and user.email:
            local_part = user.email.split('@')[0]
            username_candidates.append(local_part)
        
        # 生成新的 username
        new_username = self.generate_unique_username(username_candidates)
        
        # 更新用戶
        user.username = new_username
        user.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ 用戶 ID {user.id}: "{old_username}" → "{new_username}"'
            )
        )

    def generate_unique_username(self, txts):
        """生成唯一的 username"""
        base_username = ""
        
        for txt in txts:
            if txt:
                # 只保留字母數字和底線
                clean_txt = re.sub(r'[^a-zA-Z0-9_]', '', str(txt))
                
                # 檢查清理後的文本長度，至少需要2個字符
                if clean_txt and len(clean_txt) >= 2:
                    base_username = clean_txt.lower()
                    break
        
        # 如果沒有有效的文字，使用 user 加上隨機字符
        if not base_username:
            base_username = f"user{uuid.uuid4().hex[:8]}"
        
        # 確保 username 長度合理
        if len(base_username) > 25:
            base_username = base_username[:25]
        
        # 檢查唯一性
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            if counter > 9999:
                username = f"user{uuid.uuid4().hex[:8]}"
                break
        
        return username 