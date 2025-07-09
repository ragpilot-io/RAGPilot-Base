from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.conf import settings
from home.mixins import UserPlanContextMixin, TermsRequiredMixin
from .models import Source, SourceFile, SourceFileFormat
from profiles.models import Limit, Profile
import os
import uuid
import pandas as pd
import mimetypes
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from celery_app.extractors.extract_pdf import extract_pdf_soruce_file_content
from celery_app.extractors.extract_structured_file import extract_structured_file_content
from django.views import View


class SourceListView(TermsRequiredMixin, UserPlanContextMixin, ListView):
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


class SourceCreateView(TermsRequiredMixin, UserPlanContextMixin, TemplateView):
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
            return redirect('source_list')
        
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
            return redirect('source_list')
        
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


class SourceDetailView(TermsRequiredMixin, UserPlanContextMixin, DetailView):
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


class SourceEditView(TermsRequiredMixin, UserPlanContextMixin, TemplateView):
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


class SourceDeleteView(TermsRequiredMixin, UserPlanContextMixin, TemplateView):
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
        
        return redirect('source_list')


class SourceUploadView(TermsRequiredMixin, UserPlanContextMixin, TemplateView):
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
    
    def _get_file_format(self, filename):
        """根據檔案名稱獲取檔案格式"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        format_mapping = {
            'pdf': SourceFileFormat.PDF,
            'csv': SourceFileFormat.CSV,
            'json': SourceFileFormat.JSON,
            'xml': SourceFileFormat.XML,
        }
        
        return format_mapping.get(extension, None)  # 不支援的格式返回 None
    
    def _save_file(self, uploaded_file, username, file_uuid, file_format):
        """儲存檔案到指定路徑"""
        # 從設定獲取指定目錄
        base_dir = settings.SOURCE_FILES_DIR
        
        # 根據模型說明建立路徑：/<指定目錄>/<a~z>(username 首字小寫)/<username>/<uuid>.<format>
        first_letter = username[0].lower() if username else 'u'
        file_path = os.path.join(
            base_dir,
            first_letter,
            username,
            f"{file_uuid}.{file_format}"
        )
        print(file_path)
        
        # 建立目錄
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)
        
        # 儲存檔案
        with open(file_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        return file_path
    
    def post(self, request, *args, **kwargs):
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


@method_decorator(csrf_exempt, name='dispatch')
class FilePreviewView(LoginRequiredMixin, TemplateView):
    """檔案預覽視圖"""
    
    def get_file(self):
        """獲取檔案物件，確保用戶權限"""
        return get_object_or_404(
            SourceFile,
            pk=self.kwargs['file_id'],
            user=self.request.user
        )
    
    def get(self, request, *args, **kwargs):
        """處理檔案預覽請求"""
        file_obj = self.get_file()
        
        try:
            # 檢查檔案是否存在
            if not file_obj.path or not os.path.exists(file_obj.path):
                return JsonResponse({
                    'success': False,
                    'error': '檔案不存在或已被移動'
                }, status=404)
            
            # 根據檔案格式處理預覽
            if file_obj.format == SourceFileFormat.PDF:
                return self._preview_pdf(file_obj)
            elif file_obj.format == SourceFileFormat.CSV:
                return self._preview_structured_data(file_obj, 'csv')
            elif file_obj.format == SourceFileFormat.JSON:
                return self._preview_structured_data(file_obj, 'json')
            elif file_obj.format == SourceFileFormat.XML:
                return self._preview_structured_data(file_obj, 'xml')
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'不支援的檔案格式：{file_obj.format}'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'預覽檔案時發生錯誤：{str(e)}'
            }, status=500)
    
    def _preview_pdf(self, file_obj):
        """預覽 PDF 檔案"""
        try:
            # 只保留必要的說明文字，避免與下方檔案資訊重複
            content_info = "此為 PDF 檔案，建議下載後使用 PDF 閱讀器查看完整內容。"
            
            return JsonResponse({
                'success': True,
                'file_type': 'pdf',
                'filename': file_obj.filename,
                'size': f"{file_obj.size} MB",
                'status': file_obj.get_status_display(),
                'summary': file_obj.summary or '暫無摘要',
                'failed_reason': file_obj.failed_reason if file_obj.status == 'failed' else None,
                'message': 'PDF 檔案預覽需要下載檔案查看完整內容',
                'preview_type': 'info',
                'content': content_info
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'PDF 預覽失敗：{str(e)}'
            }, status=500)
    
    def _preview_structured_data(self, file_obj, file_type):
        """預覽結構化資料檔案（從資料庫表格讀取）"""
        try:
            from sources.models import SourceFileTable
            import psycopg2
            from django.conf import settings
            
            # 準備基本信息
            basic_info = {
                'filename': file_obj.filename,
                'size': f"{file_obj.size} MB",
                'status': file_obj.get_status_display(),
                'summary': file_obj.summary or '暫無摘要',
                'failed_reason': file_obj.failed_reason if file_obj.status == 'failed' else None
            }
            
            # 如果檔案處理失敗，只顯示基本信息和失敗原因
            if file_obj.status == 'failed':
                return JsonResponse({
                    'success': True,
                    'file_type': file_type,
                    'preview_type': 'error',
                    'message': f'檔案處理失敗：{file_obj.failed_reason or "未知錯誤"}',
                    **basic_info
                })
            
            # 查找對應的資料表
            try:
                source_file_table = SourceFileTable.objects.get(source_file=file_obj)
            except SourceFileTable.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'找不到 {file_type.upper()} 檔案對應的資料表，檔案可能尚未處理完成'
                }, status=404)
            
            # 連接到對應的資料庫並讀取資料
            db_config = settings.DATABASES['default']
            conn = psycopg2.connect(
                host=db_config['HOST'],
                port=db_config['PORT'],
                database=source_file_table.database_name,
                user=db_config['USER'],
                password=db_config['PASSWORD']
            )
            
            # 讀取前10行資料
            query = f'SELECT * FROM "{source_file_table.table_name}" LIMIT 10'
            df = pd.read_sql_query(query, conn)
            
            # 獲取總行數
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{source_file_table.table_name}"')
            total_rows = cursor.fetchone()[0]
            conn.close()
            
            # 轉換為 HTML 表格
            html_table = df.to_html(
                classes='table table-sm table-striped', 
                table_id=f'{file_type}-preview-table',
                escape=False,
                index=False
            )
            
            # 添加表頭置中對齊的樣式
            html_table = f'<style>#{file_type}-preview-table th {{ text-align: center !important; }}</style>' + html_table
            
            return JsonResponse({
                'success': True,
                'file_type': file_type,
                'preview_type': 'table',
                'content': html_table,
                'total_rows': total_rows,
                'total_columns': len(df.columns),
                'message': f'顯示前 {len(df)} 行，共 {total_rows} 行 {len(df.columns)} 欄',
                **basic_info
            })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'{file_type.upper()} 預覽失敗：{str(e)}'
            }, status=500)




class FileDownloadView(LoginRequiredMixin, TemplateView):
    """檔案下載視圖"""
    
    def get_file(self):
        """獲取檔案物件，確保用戶權限"""
        return get_object_or_404(
            SourceFile,
            pk=self.kwargs['file_id'],
            user=self.request.user
        )
    
    def get(self, request, *args, **kwargs):
        """處理檔案下載請求"""
        file_obj = self.get_file()
        
        try:
            # 檢查檔案是否存在
            if not file_obj.path or not os.path.exists(file_obj.path):
                messages.error(request, '檔案不存在或已被移動')
                return redirect('source_detail', pk=file_obj.source.id)
            
            # 獲取檔案的 MIME 類型
            mime_type, _ = mimetypes.guess_type(file_obj.filename)
            if not mime_type:
                # 根據檔案格式設定 MIME 類型
                mime_mapping = {
                    SourceFileFormat.PDF: 'application/pdf',
                    SourceFileFormat.CSV: 'text/csv',
                    SourceFileFormat.JSON: 'application/json',
                    SourceFileFormat.XML: 'application/xml',
                }
                mime_type = mime_mapping.get(file_obj.format, 'application/octet-stream')
            
            # 使用 FileResponse 回傳檔案
            response = FileResponse(
                open(file_obj.path, 'rb'),
                content_type=mime_type,
                as_attachment=True,
                filename=file_obj.filename
            )
            
            return response
            
        except Exception as e:
            messages.error(request, f'下載檔案時發生錯誤：{str(e)}')
            return redirect('source_detail', pk=file_obj.source.id)


class FileDeleteView(LoginRequiredMixin, TemplateView):
    """檔案刪除視圖（真正刪除，包括實體檔案）"""
    
    def get_file(self):
        """獲取檔案物件，確保用戶權限"""
        return get_object_or_404(
            SourceFile,
            pk=self.kwargs['file_id'],
            user=self.request.user
        )
    
    def post(self, request, *args, **kwargs):
        """處理檔案刪除請求"""
        file_obj = self.get_file()
        source_id = file_obj.source.id
        filename = file_obj.filename
        
        try:
            # 直接刪除資料庫記錄，讓信號處理器處理實體檔案刪除
            # 這樣避免重複刪除實體檔案
            file_obj.delete()
            
            messages.success(request, f'檔案「{filename}」已成功刪除。')
            
        except Exception as e:
            messages.error(request, f'刪除檔案時發生錯誤：{str(e)}')
        
        return redirect('source_detail', pk=source_id)


class SourceSuggestView(TermsRequiredMixin, View):
    
    def get(self, request):
        """使用重構後的工具生成自建資料源建議問題"""
        from utils.question_suggestions import generate_source_suggestions
        
        return generate_source_suggestions(request.user)
