from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from profiles.models import Profile, Limit


class Command(BaseCommand):
    help = '為現有用戶創建 Profile 和 Limit 記錄'

    def handle(self, *args, **options):
        users = User.objects.all()
        created_profiles = 0
        created_limits = 0
        
        for user in users:
            # 創建 Profile 記錄
            profile, created = Profile.objects.get_or_create(user=user)
            if created:
                created_profiles += 1
                self.stdout.write(f'為用戶 {user.username} 創建了 Profile 記錄')
            
            # 創建 Limit 記錄
            limit, created = Limit.objects.get_or_create(user=user)
            if created:
                created_limits += 1
                self.stdout.write(f'為用戶 {user.username} 創建了 Limit 記錄')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'完成！創建了 {created_profiles} 個 Profile 記錄和 {created_limits} 個 Limit 記錄'
            )
        ) 