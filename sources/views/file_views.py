from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from ..models import SourceFile, SourceFileFormat
import os
import pandas as pd
import mimetypes


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