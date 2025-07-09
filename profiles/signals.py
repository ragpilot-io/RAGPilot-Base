from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Limit, Profile


@receiver(post_save, sender=User)
def create_user_profile_and_limit(sender, instance, created, **kwargs):
    """
    當用戶被創建時，自動為該用戶創建 Profile 和 Limit 記錄
    """
    if created:
        # 創建 Profile 記錄
        if not hasattr(instance, 'profile'):
            Profile.objects.create(user=instance)
        
        # 創建 Limit 記錄
        if not hasattr(instance, 'limit'):
            Limit.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile_and_limit(sender, instance, **kwargs):
    """
    當用戶被保存時，確保 Profile 和 Limit 記錄存在
    """
    # 確保 Profile 記錄存在
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        Profile.objects.get_or_create(user=instance)
    
    # 確保 Limit 記錄存在
    if hasattr(instance, 'limit'):
        instance.limit.save()
    else:
        Limit.objects.get_or_create(user=instance) 