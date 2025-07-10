from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from home.mixins import UserPlanContextMixin, TermsRequiredMixin
from ..models import Source, SourceFile, SourceFileFormat
from profiles.models import Limit, Profile
import os
import uuid


class SourceListView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, ListView):
    """自建資料源列表視圖"""
    model = Source
    template_name = 'sources/source_list.html'
    context_object_name = 'sources'
    paginate_by = 10
    
    def get_queryset(self):
        # 只顯示當前用戶的資料源
        return Source.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        
        # 獲取用戶的限制資訊
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        
        # 計算私有資料源數量
        private_source_count = Source.objects.filter(
            user=self.request.user
        ).count()
        
        # 檢查用戶權限層級
        is_superuser = self.request.user.is_superuser
        has_unlimited_source = is_superuser
        
        # 檢查是否可以建立新資料源
        can_create_source = has_unlimited_source or private_source_count < limit.private_source_limit
        
        context.update({
            'private_source_count': private_source_count,
            'private_source_limit': limit.private_source_limit,
            'remaining_source_count': max(0, limit.private_source_limit - private_source_count) if not has_unlimited_source else 999,
            'has_unlimited_source': has_unlimited_source,
            'can_create_source': can_create_source,
        })
        
        return context


class SourceCreateView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, TemplateView):
    """建立新資料源視圖"""
    template_name = 'sources/source_create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        
        # 檢查是否可以建立新資料源
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        
        private_source_count = Source.objects.filter(
            user=self.request.user
        ).count()
        
        is_superuser = self.request.user.is_superuser
        has_unlimited_source = is_superuser
        can_create_source = has_unlimited_source or private_source_count < limit.private_source_limit
        
        context.update({
            'private_source_count': private_source_count,
            'private_source_limit': limit.private_source_limit,
            'remaining_source_count': max(0, limit.private_source_limit - private_source_count) if not has_unlimited_source else 999,
            'has_unlimited_source': has_unlimited_source,
            'can_create_source': can_create_source,
        })
        
        return context
    
    def dispatch(self, request, *args, **kwargs):
        # 檢查是否可以建立新資料源
        limit, _ = Limit.objects.get_or_create(user=request.user)
        private_source_count = Source.objects.filter(
            user=request.user
        ).count()
        
        is_superuser = request.user.is_superuser
        has_unlimited_source = is_superuser
        can_create_source = has_unlimited_source or private_source_count < limit.private_source_limit
        
        if not can_create_source:
            messages.error(request, f'您已達到私有資料源數量上限（{limit.private_source_limit} 個）。請刪除現有資料源或聯繫管理員提升限制。')
            return redirect('home')
        
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        # 再次檢查限制（防止併發建立）
        limit, _ = Limit.objects.get_or_create(user=request.user)
        private_source_count = Source.objects.filter(
            user=request.user
        ).count()
        
        is_superuser = request.user.is_superuser
        has_unlimited_source = is_superuser
        can_create_source = has_unlimited_source or private_source_count < limit.private_source_limit
        
        if not can_create_source:
            messages.error(request, f'您已達到私有資料源數量上限（{limit.private_source_limit} 個）。請刪除現有資料源或聯繫管理員提升限制。')
            return redirect('home')
        
        # 處理表單提交
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name or not description:
            messages.error(request, '請填寫所有必要欄位。')
            return self.get(request, *args, **kwargs)
        
        # 檢查名稱是否重複
        if Source.objects.filter(user=request.user, name=name).exists():
            messages.error(request, f'資料源名稱「{name}」已存在，請使用不同的名稱。')
            return self.get(request, *args, **kwargs)
        
        # 建立資料源
        source = Source.objects.create(
            user=request.user,
            name=name,
            description=description,
            is_public=False  # 預設為私有
        )
        
        messages.success(request, f'資料源「{name}」建立成功！')
        return redirect('source_detail', pk=source.id)


class SourceDetailView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, DetailView):
    """資料源詳細視圖"""
    model = Source
    template_name = 'sources/source_detail.html'
    context_object_name = 'source'
    
    def get_object(self, queryset=None):
        # 只允許用戶查看自己的資料源
        source = get_object_or_404(
            Source, 
            pk=self.kwargs['pk'], 
            user=self.request.user
        )
        return source
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        
        source = self.get_object()
        
        # 獲取真實的檔案列表
        files = SourceFile.objects.filter(
            source=source
        ).order_by('-created_at')
        
        # 計算處理狀態統計
        from sources.models import ProcessingStatus
        status_stats = {
            'pending': files.filter(status=ProcessingStatus.PENDING).count(),
            'processing': files.filter(status=ProcessingStatus.PROCESSING).count(),
            'completed': files.filter(status=ProcessingStatus.COMPLETED).count(),
            'failed': files.filter(status=ProcessingStatus.FAILED).count(),
        }
        
        # 檢查限制資訊（為了在 source-description 中顯示）
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        is_superuser = self.request.user.is_superuser
        has_unlimited_source = is_superuser
        has_unlimited_files = is_superuser
        current_file_count = files.count()
        
        # 計算私有資料源數量
        private_source_count = Source.objects.filter(
            user=self.request.user
        ).count()
        
        context.update({
            'files': files,
            'file_count': current_file_count,
            'current_file_count': current_file_count,
            'file_limit_per_source': limit.file_limit_per_source,
            'has_unlimited_files': has_unlimited_files,
            'has_unlimited_source': has_unlimited_source,
            'private_source_count': private_source_count,
            'private_source_limit': limit.private_source_limit,
            'status_stats': status_stats,
        })
        
        return context


class SourceEditView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, TemplateView):
    """編輯資料源視圖"""
    template_name = 'sources/source_edit.html'
    
    def get_source(self):
        # 只允許用戶編輯自己的資料源
        return get_object_or_404(
            Source, 
            pk=self.kwargs['pk'], 
            user=self.request.user
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        source = self.get_source()
        context['source'] = source
        
        # 添加限制資訊
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        is_superuser = self.request.user.is_superuser
        has_unlimited_source = is_superuser
        has_unlimited_files = is_superuser
        
        # 計算私有資料源數量
        private_source_count = Source.objects.filter(
            user=self.request.user
        ).count()
        
        # 獲取當前資料源的檔案數量
        current_file_count = source.file_count
        
        context.update({
            'private_source_count': private_source_count,
            'private_source_limit': limit.private_source_limit,
            'has_unlimited_source': has_unlimited_source,
            'current_file_count': current_file_count,
            'file_limit_per_source': limit.file_limit_per_source,
            'has_unlimited_files': has_unlimited_files,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        source = self.get_source()
        
        # 處理表單提交
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name or not description:
            messages.error(request, '請填寫所有必要欄位。')
            return self.get(request, *args, **kwargs)
        
        # 檢查名稱是否重複（排除自己）
        if Source.objects.filter(
            user=request.user, 
            name=name
        ).exclude(pk=source.pk).exists():
            messages.error(request, f'資料源名稱「{name}」已存在，請使用不同的名稱。')
            return self.get(request, *args, **kwargs)
        
        # 更新資料源
        source.name = name
        source.description = description
        source.save()
        
        messages.success(request, f'資料源「{name}」更新成功！')
        return redirect('source_detail', pk=source.id)


class SourceDeleteView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, TemplateView):
    """刪除資料源視圖"""
    template_name = 'sources/source_delete.html'
    
    def get_source(self):
        # 只允許用戶刪除自己的資料源
        return get_object_or_404(
            Source, 
            pk=self.kwargs['pk'], 
            user=self.request.user
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        context['source'] = self.get_source()
        
        # 添加限制資訊
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        is_superuser = self.request.user.is_superuser
        has_unlimited_source = is_superuser
        has_unlimited_files = is_superuser
        
        # 計算私有資料源數量
        private_source_count = Source.objects.filter(
            user=self.request.user
        ).count()
        
        # 獲取當前資料源的檔案數量
        current_file_count = self.get_source().file_count
        
        context.update({
            'private_source_count': private_source_count,
            'private_source_limit': limit.private_source_limit,
            'has_unlimited_source': has_unlimited_source,
            'current_file_count': current_file_count,
            'file_limit_per_source': limit.file_limit_per_source,
            'has_unlimited_files': has_unlimited_files,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        source = self.get_source()
        source_name = source.name
        
        try:
            # 真正刪除資料源（包括所有相關檔案）
            # Django 的 CASCADE 會自動刪除相關的 SourceFile
            # 而信號處理器會處理實體檔案的刪除
            source.delete()
            
            messages.success(request, f'資料源「{source_name}」已成功刪除。')
            
        except Exception as e:
            messages.error(request, f'刪除資料源時發生錯誤：{str(e)}')
        
        return redirect('home')


class SourceUploadView(LoginRequiredMixin, TermsRequiredMixin, UserPlanContextMixin, TemplateView):
    """檔案上傳視圖"""
    template_name = 'sources/source_upload.html'
    
    def get_source(self):
        # 只允許用戶操作自己的資料源
        return get_object_or_404(
            Source, 
            pk=self.kwargs['pk'], 
            user=self.request.user
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['request_path'] = self.request.path
        context['source'] = self.get_source()
        
        # 檢查檔案上傳限制
        limit, _ = Limit.objects.get_or_create(user=self.request.user)
        is_superuser = self.request.user.is_superuser
        has_unlimited_files = is_superuser
        
        # 獲取當前資料源的真實檔案數量
        current_file_count = self.get_source().file_count
        
        can_upload_files = has_unlimited_files or current_file_count < limit.file_limit_per_source
        
        context.update({
            'current_file_count': current_file_count,
            'file_limit_per_source': limit.file_limit_per_source,
            'remaining_file_count': max(0, limit.file_limit_per_source - current_file_count) if not has_unlimited_files else 999,
            'has_unlimited_files': has_unlimited_files,
            'can_upload_files': can_upload_files,
        })
        
        return context

    @staticmethod
    def _get_file_format(filename) -> str | None:
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        format_mapping = {
            'pdf': SourceFileFormat.PDF,
            'csv': SourceFileFormat.CSV,
            'json': SourceFileFormat.JSON,
            'xml': SourceFileFormat.XML,
        }
        
        return format_mapping.get(extension, None)  # 不支援的格式返回 None

    @staticmethod
    def _save_file(uploaded_file, username, file_uuid, file_format):
        first_letter = username[0].lower() if username else 'u'
        file_path = f"/Volumes/RAGPilot/{first_letter}/{username}/{file_uuid}.{file_format}"

        # 建立目錄
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)
        
        # 儲存檔案
        with open(file_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        return file_path
    
    def post(self, request, *args, **kwargs):
        from celery_app.extractors.extract_pdf import extract_pdf_soruce_file_content
        from celery_app.extractors.extract_structured_file import extract_structured_file_content
        
        source = self.get_source()
        
        # 檢查檔案上傳限制
        limit, _ = Limit.objects.get_or_create(user=request.user)
        is_superuser = request.user.is_superuser
        has_unlimited_files = is_superuser
        
        # 獲取當前資料源的真實檔案數量
        current_file_count = source.file_count
        
        uploaded_files = request.FILES.getlist('files')
        
        if not uploaded_files:
            messages.error(request, '請選擇要上傳的檔案。')
            return self.get(request, *args, **kwargs)
        
        # 檢查一次上傳檔案數量限制（最多5個）
        if len(uploaded_files) > 5:
            messages.error(request, '一次最多只能上傳 5 個檔案，請分批上傳。')
            return self.get(request, *args, **kwargs)
        
        # 檢查檔案大小限制（每個檔案最大20MB）
        max_file_size = 20 * 1024 * 1024  # 20MB in bytes
        oversized_files = []
        for uploaded_file in uploaded_files:
            if uploaded_file.size > max_file_size:
                oversized_files.append(f"{uploaded_file.name} ({uploaded_file.size / (1024*1024):.1f} MB)")
        
        if oversized_files:
            messages.error(
                request, 
                f'以下檔案超過 20MB 限制：{", ".join(oversized_files)}。請壓縮檔案後重新上傳。'
            )
            return self.get(request, *args, **kwargs)
        
        # 檢查檔案格式
        unsupported_files = []
        for uploaded_file in uploaded_files:
            file_format = self._get_file_format(uploaded_file.name)
            if file_format is None:
                unsupported_files.append(uploaded_file.name)
        
        if unsupported_files:
            messages.error(
                request, 
                f'不支援的檔案格式：{", ".join(unsupported_files)}。目前僅支援 PDF、CSV、JSON、XML 格式。'
            )
            return self.get(request, *args, **kwargs)
        
        if not has_unlimited_files and current_file_count + len(uploaded_files) > limit.file_limit_per_source:
            remaining_slots = limit.file_limit_per_source - current_file_count
            messages.error(
                request, 
                f'檔案數量超過限制！此資料源最多可上傳 {limit.file_limit_per_source} 個檔案，'
                f'目前已有 {current_file_count} 個檔案，還可以上傳 {remaining_slots} 個檔案。'
            )
            return self.get(request, *args, **kwargs)
        
        # 處理檔案上傳
        successful_uploads = []
        failed_uploads = []
        
        for uploaded_file in uploaded_files:
            # 檢查檔案名稱是否重複
            if SourceFile.objects.filter(
                source=source, 
                filename=uploaded_file.name
            ).exists():
                failed_uploads.append(f"{uploaded_file.name}（檔案名稱重複）")
                continue
            
            # 獲取檔案資訊
            file_format = self._get_file_format(uploaded_file.name)
            file_size = uploaded_file.size / (1024 * 1024)  # 轉換為 MB
            file_uuid = uuid.uuid4()
            
            # 儲存檔案
            file_path = self._save_file(
                uploaded_file, 
                request.user.username, 
                file_uuid, 
                file_format
            )
            
            # 建立 SourceFile 物件
            source_file = SourceFile.objects.create(
                user=request.user,
                source=source,
                filename=uploaded_file.name,
                size=round(file_size, 2),
                format=file_format,
                path=file_path,
                uuid=file_uuid,
                summary_embedding=[0.0] * 1536  # 暫時使用零向量，後續可由背景任務處理
            )
            
            successful_uploads.append(source_file)
                            
        if successful_uploads:
            for file in successful_uploads:
                if file.format == SourceFileFormat.PDF:
                    extract_pdf_soruce_file_content.delay(file.id)
                else:
                    extract_structured_file_content.delay(file.id)
            messages.success(
                request, 
                f'成功上傳 {len(successful_uploads)} 個檔案：{", ".join([file.filename for file in successful_uploads])}'
            )
        
        return redirect('source_detail', pk=source.id)


class SourceSuggestView(LoginRequiredMixin, TermsRequiredMixin, View):
    
    def get(self, request):
        from utils.question_suggestions import generate_source_suggestions
        
        return generate_source_suggestions(request.user)