from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = '查看用戶數量統計和系統限制狀態'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='設定新的用戶數量上限（需要重啟服務才能生效）'
        )
        parser.add_argument(
            '--recent',
            type=int,
            default=7,
            help='顯示最近 N 天的註冊用戶數（預設 7 天）'
        )

    def handle(self, *args, **options):
        # 獲取基本統計
        total_users = User.objects.count()
        max_users_limit = getattr(settings, 'MAX_USERS_LIMIT', 200)
        remaining_slots = max_users_limit - total_users
        usage_percentage = (total_users / max_users_limit) * 100 if max_users_limit > 0 else 0
        
        # 獲取最近註冊的用戶
        recent_days = options['recent']
        recent_date = timezone.now() - timedelta(days=recent_days)
        recent_users = User.objects.filter(date_joined__gte=recent_date).count()
        
        # 獲取今日註冊用戶
        today = timezone.now().date()
        today_users = User.objects.filter(date_joined__date=today).count()
        
        # 獲取管理員和一般用戶數量
        admin_users = User.objects.filter(is_superuser=True).count()
        regular_users = total_users - admin_users
        
        # 輸出統計資訊
        self.stdout.write(self.style.SUCCESS('\n📊 用戶數量統計報告'))
        self.stdout.write('=' * 50)
        
        # 基本統計
        self.stdout.write(f'📈 總用戶數量：{total_users}')
        self.stdout.write(f'👥 一般用戶：{regular_users}')
        self.stdout.write(f'🔧 管理員用戶：{admin_users}')
        self.stdout.write(f'📝 用戶上限：{max_users_limit}')
        self.stdout.write(f'🎯 剩餘名額：{remaining_slots}')
        self.stdout.write(f'📊 使用率：{usage_percentage:.1f}%')
        
        # 時間相關統計
        self.stdout.write('\n⏰ 時間統計')
        self.stdout.write('-' * 20)
        self.stdout.write(f'📅 今日新增：{today_users} 人')
        self.stdout.write(f'📆 最近 {recent_days} 天新增：{recent_users} 人')
        
        # 狀態判斷
        self.stdout.write('\n🚦 系統狀態')
        self.stdout.write('-' * 20)
        
        if usage_percentage >= 100:
            status = self.style.ERROR('🔴 已達上限')
            message = '新用戶無法通過 Google 註冊'
        elif usage_percentage >= 90:
            status = self.style.WARNING('🟠 接近上限')
            message = '建議密切關注註冊情況'
        elif usage_percentage >= 80:
            status = self.style.WARNING('🟡 使用偏高')
            message = '建議開始監控用戶增長'
        else:
            status = self.style.SUCCESS('🟢 正常')
            message = '系統運行正常'
        
        self.stdout.write(f'狀態：{status}')
        self.stdout.write(f'說明：{message}')
        
        # 進度條
        self.stdout.write('\n📈 使用進度')
        self.stdout.write('-' * 20)
        bar_length = 30
        filled_length = int(bar_length * usage_percentage / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        self.stdout.write(f'[{bar}] {usage_percentage:.1f}%')
        
        # 警告訊息
        if usage_percentage >= 90:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  警告：系統用戶數量已接近或達到上限！'
                )
            )
            if usage_percentage >= 100:
                self.stdout.write(
                    self.style.ERROR(
                        '🚫 新用戶將無法通過 Google 登入註冊'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'📢 還有 {remaining_slots} 個名額，請密切關注'
                    )
                )
        
        # 設定新的限制
        if options['limit']:
            new_limit = options['limit']
            if new_limit < total_users:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n❌ 錯誤：新的限制 ({new_limit}) 不能小於目前用戶數量 ({total_users})'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ 建議將 MAX_USERS_LIMIT 設定為 {new_limit}'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️  注意：需要在 .env 文件中設定 MAX_USERS_LIMIT={} 並重啟服務才能生效'.format(new_limit)
                    )
                )
        
        # 最新註冊用戶
        if recent_users > 0:
            self.stdout.write(f'\n👥 最近 {recent_days} 天註冊的用戶')
            self.stdout.write('-' * 30)
            recent_user_list = User.objects.filter(
                date_joined__gte=recent_date
            ).order_by('-date_joined')[:10]
            
            for user in recent_user_list:
                join_date = user.date_joined.strftime('%Y-%m-%d %H:%M')
                user_type = '👑 管理員' if user.is_superuser else '👤 一般用戶'
                self.stdout.write(f'{join_date} | {user_type} | {user.username} ({user.email})')
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('✅ 統計報告完成'))
        
        # 使用說明
        self.stdout.write('\n💡 使用說明')
        self.stdout.write('-' * 20)
        self.stdout.write('• 查看統計：python manage.py user_stats')
        self.stdout.write('• 設定上限：python manage.py user_stats --limit 300')
        self.stdout.write('• 查看最近 30 天：python manage.py user_stats --recent 30')
        self.stdout.write('• 在 .env 文件中設定：MAX_USERS_LIMIT=200')
        self.stdout.write('') 