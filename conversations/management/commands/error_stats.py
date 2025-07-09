from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from conversations.models import Message, SenderChoices
from django.db.models import Count, Q

User = get_user_model()


class Command(BaseCommand):
    help = '顯示對話錯誤統計報告'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='統計過去 N 天的數據（預設：7）'
        )
        parser.add_argument(
            '--detail',
            action='store_true',
            help='顯示詳細的錯誤資訊'
        )

    def handle(self, *args, **options):
        days = options['days']
        show_detail = options['detail']
        
        # 計算時間範圍
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 對話錯誤統計報告'))
        self.stdout.write(self.style.SUCCESS(f'📅 統計期間：{start_date.strftime("%Y-%m-%d %H:%M")} ~ {end_date.strftime("%Y-%m-%d %H:%M")}'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # 基本統計
        total_messages = Message.objects.filter(
            created_at__range=[start_date, end_date],
            sender=SenderChoices.AI
        ).count()
        
        error_messages = Message.objects.filter(
            created_at__range=[start_date, end_date],
            sender=SenderChoices.AI,
            traceback__isnull=False
        ).exclude(traceback='').count()
        
        success_rate = ((total_messages - error_messages) / total_messages * 100) if total_messages > 0 else 0
        
        self.stdout.write(f'\n📈 總體統計：')
        self.stdout.write(f'   總 AI 訊息數：{total_messages}')
        self.stdout.write(f'   錯誤訊息數：{error_messages}')
        self.stdout.write(f'   成功率：{success_rate:.2f}%')
        
        if error_messages == 0:
            self.stdout.write(self.style.SUCCESS(f'\n🎉 太棒了！在過去 {days} 天內沒有發生任何錯誤！'))
            return
        
        # 按日期統計錯誤
        self.stdout.write(f'\n📅 每日錯誤統計：')
        daily_errors = Message.objects.filter(
            created_at__range=[start_date, end_date],
            sender=SenderChoices.AI,
            traceback__isnull=False
        ).exclude(traceback='').extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            error_count=Count('id')
        ).order_by('date')
        
        for day_stat in daily_errors:
            self.stdout.write(f'   {day_stat["date"]}: {day_stat["error_count"]} 個錯誤')
        
        # 按用戶統計錯誤
        self.stdout.write(f'\n👥 用戶錯誤統計（前10名）：')
        user_errors = Message.objects.filter(
            created_at__range=[start_date, end_date],
            sender=SenderChoices.AI,
            traceback__isnull=False,
            user__isnull=False
        ).exclude(traceback='').values(
            'user__email', 'user__username'
        ).annotate(
            error_count=Count('id')
        ).order_by('-error_count')[:10]
        
        for user_stat in user_errors:
            user_display = user_stat['user__email'] or user_stat['user__username'] or '未知用戶'
            self.stdout.write(f'   {user_display}: {user_stat["error_count"]} 個錯誤')
        
        # 顯示詳細錯誤資訊
        if show_detail:
            self.stdout.write(f'\n🔍 最近的錯誤詳情（最近5個）：')
            recent_errors = Message.objects.filter(
                created_at__range=[start_date, end_date],
                sender=SenderChoices.AI,
                traceback__isnull=False
            ).exclude(traceback='').order_by('-created_at')[:5]
            
            for i, error_msg in enumerate(recent_errors, 1):
                user_display = error_msg.user.email if error_msg.user else '匿名用戶'
                self.stdout.write(f'\n   錯誤 #{i}:')
                self.stdout.write(f'     時間：{error_msg.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
                self.stdout.write(f'     用戶：{user_display}')
                self.stdout.write(f'     訊息ID：{error_msg.id}')
                
                # 提取錯誤類型（通常在 traceback 的最後一行）
                if error_msg.traceback:
                    error_lines = error_msg.traceback.strip().split('\n')
                    if error_lines:
                        error_type = error_lines[-1] if len(error_lines) == 1 else error_lines[-1]
                        self.stdout.write(f'     錯誤類型：{error_type}')
        
        # 健康建議
        self.stdout.write(f'\n💡 健康建議：')
        if success_rate < 95:
            self.stdout.write(self.style.WARNING(f'   ⚠️  成功率 ({success_rate:.2f}%) 低於建議值 95%，建議檢查系統狀態'))
        if error_messages > total_messages * 0.1:
            self.stdout.write(self.style.WARNING(f'   ⚠️  錯誤率較高，建議深入分析錯誤原因'))
        if error_messages == 0:
            self.stdout.write(self.style.SUCCESS(f'   ✅ 系統運行良好，無錯誤發生'))
        elif success_rate >= 99:
            self.stdout.write(self.style.SUCCESS(f'   ✅ 系統運行優秀，成功率超過 99%'))
        elif success_rate >= 95:
            self.stdout.write(self.style.SUCCESS(f'   ✅ 系統運行良好，成功率在合理範圍內'))
        
        self.stdout.write(f'\n📋 詳細錯誤資訊請前往 Django Admin 查看：')
        self.stdout.write(f'   過濾條件：錯誤狀態 = "有錯誤"')
        self.stdout.write(self.style.SUCCESS('=' * 70)) 