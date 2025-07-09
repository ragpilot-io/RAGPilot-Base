from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Profile(models.Model):
    """
    用戶個人資料擴展模型
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_collaborator = models.BooleanField(default=False, verbose_name='是否為協作者')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '用戶個人資料'
        verbose_name_plural = '用戶個人資料'
    
    def __str__(self):
        return f"{self.user.username} - {'協作者' if self.is_collaborator else '一般用戶'}"


class Limit(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    chat_limit_per_month = models.IntegerField(default=100)
    private_source_limit = models.IntegerField(default=2)
    file_limit_per_source = models.IntegerField(default=5)
    
    class Meta:
        verbose_name = '使用方案'
        verbose_name_plural = '使用方案'
    
    def __str__(self):
        return f"{self.user.username} - 使用方案"