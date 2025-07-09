from django.urls import path
from . import views

urlpatterns = [
    path('agree-to-terms/', views.agree_to_terms, name='agree_to_terms'),
    path('check-terms-status/', views.check_terms_status, name='check_terms_status'),
    path('terms-content/', views.get_latest_terms_content, name='get_latest_terms_content'),
    
    # 公告相關 URLs
    path('announcement/latest/', views.get_latest_announcement, name='get_latest_announcement'),
    path('announcement/<int:announcement_id>/', views.announcement_detail, name='announcement_detail'),
] 