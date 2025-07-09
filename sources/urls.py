from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.SourceListView.as_view(), name='source_list'),
    path('create/', views.SourceCreateView.as_view(), name='source_create'),
    path('<int:pk>/', views.SourceDetailView.as_view(), name='source_detail'),
    path('<int:pk>/edit/', views.SourceEditView.as_view(), name='source_edit'),
    path('<int:pk>/upload/', views.SourceUploadView.as_view(), name='source_upload'),
    path('<int:pk>/delete/', views.SourceDeleteView.as_view(), name='source_delete'),
    path('file/<int:file_id>/preview/', views.FilePreviewView.as_view(), name='file_preview'),
    path('file/<int:file_id>/download/', views.FileDownloadView.as_view(), name='file_download'),
    path('file/<int:file_id>/delete/', views.FileDeleteView.as_view(), name='file_delete'),
    path('api/sources-suggestions/', views.SourceSuggestView.as_view(), name='source_suggestions'),
] 