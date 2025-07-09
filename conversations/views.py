from django.views import View
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Message, SenderChoices, Session, MessageStatusChoices
from .utils import format_message_data, get_recent_messages
import json


@method_decorator(login_required, name='dispatch')
class MessageToolCallsView(View):
    def get(self, request, message_id):
        try:
            ai_message = get_object_or_404(
                Message, 
                id=message_id, 
                sender=SenderChoices.AI, 
                user=request.user,
                is_deleted=False
            )
            
            tool_messages = ai_message.get_related_tool_messages().order_by('created_at')
            
            tool_calls = [
                {
                    'id': tool_msg.id,
                    'tool_name': tool_msg.tool_name,
                    'tool_keywords': tool_msg.tool_keywords,
                    'text': tool_msg.text,
                    'timestamp': tool_msg.created_at.strftime('%H:%M:%S'),
                    'created_at': tool_msg.created_at.isoformat()
                }
                for tool_msg in tool_messages
            ]
            
            return JsonResponse(tool_calls, safe=False)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator([csrf_exempt, login_required], name='dispatch')
class ConversationMessageView(ListView):
    model = Message
    paginate_by = 20
    context_object_name = 'messages'
    
    def get_queryset(self):
        session_id = self.kwargs['session_id']
        session = get_object_or_404(Session, id=session_id, user=self.request.user)
        
        return Message.objects.filter(
            session=session,
            is_deleted=False
        ).exclude(sender=SenderChoices.TOOL).order_by('-updated_at')
    
    def get_paginate_by(self, queryset):
        return min(int(self.request.GET.get('limit', 20)), 50)
    
    def get(self, request, *args, **kwargs):
        session_id = kwargs['session_id']
        session = get_object_or_404(Session, id=session_id, user=request.user)
        
        # 檢查是否只需要狀態檢查（用於輪詢）
        status_check = request.GET.get('status_only', 'false').lower() == 'true'
        
        if status_check:
            # 輪詢模式：檢查是否有待處理訊息
            pending_messages = Message.objects.filter(
                session=session,
                sender=SenderChoices.AI,
                status__in=[MessageStatusChoices.PENDING, MessageStatusChoices.PROCESSING],
                is_deleted=False
            ).order_by('-updated_at')
            
            recent_messages = get_recent_messages(session)
            formatted_messages = [format_message_data(msg) for msg in reversed(recent_messages)]
            
            if not pending_messages.exists():
                return JsonResponse({
                    'should_poll': False,
                    'message': '沒有待處理的訊息',
                    'messages': formatted_messages
                })
            
            return JsonResponse({
                'should_poll': True,
                'messages': formatted_messages,
                'pending_count': pending_messages.count()
            })
        
        # 檢查是否需要分頁
        page = request.GET.get('page')
        limit = request.GET.get('limit')
        
        if page or limit:
            # 分頁模式：使用 ListView 的分頁功能
            return super().get(request, *args, **kwargs)
        else:
            # 一般模式：獲取最近的訊息
            recent_messages = get_recent_messages(session)
            formatted_messages = [format_message_data(msg) for msg in reversed(recent_messages)]
            
            return JsonResponse({
                'messages': formatted_messages,
                'session_id': session.id
            })
    
    def render_to_response(self, context, **response_kwargs):
        # 這個方法只在分頁模式下被調用
        messages = context['messages']
        page_obj = context['page_obj']
        paginator = context['paginator']
        session_id = self.kwargs['session_id']
        
        formatted_messages = [format_message_data(msg) for msg in reversed(messages)]
        
        data = {
            'messages': formatted_messages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'session_id': session_id
        }
        
        return JsonResponse(data)
    
    def post(self, request, session_id):
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            reference_id_list = data.get('reference_id_list', [])
            data_type = data.get('data_type', 'Mixed')
            
            if not user_message:
                return JsonResponse({'error': '訊息內容不能為空'}, status=400)
            
            session = get_object_or_404(Session, id=session_id, user=request.user)
            
            user_msg = Message.create_user_message(session, request.user, user_message)
            ai_msg = Message.create_ai_message(session, request.user, "正在思考中...", MessageStatusChoices.PENDING)
            
            from celery_app.tasks.conversations import process_conversation_async
            process_conversation_async.delay(
                user_id=request.user.id,
                user_question=user_message,
                reference_id_list=reference_id_list,
                data_type=data_type,
                ai_message_id=ai_msg.id
            )
            
            recent_messages = get_recent_messages(session)
            formatted_messages = [format_message_data(msg) for msg in reversed(recent_messages)]
            
            return JsonResponse({
                'success': True,
                'user_message_id': user_msg.id,
                'ai_message_id': ai_msg.id,
                'messages': formatted_messages,
                'should_poll': True
            })
            
        except Exception as e:
            return JsonResponse({'error': f'建立對話失敗：{str(e)}'}, status=500)
    
    def delete(self, request, session_id):
        try:
            session = get_object_or_404(Session, id=session_id, user=request.user)
            deleted_count = Message.clear_conversation(session)
            
            return JsonResponse({
                'success': True,
                'message': f'已清空 {deleted_count} 筆對話記錄',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            return JsonResponse({'error': f'清空對話失敗：{str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class UserSessionView(View):
    def get(self, request):
        try:
            session = Session.get_or_create_user_session(request.user)
            
            return JsonResponse({
                'success': True,
                'session_id': session.id,
                'session_uuid': str(session.session_uuid)
            })
            
        except Exception as e:
            return JsonResponse({'error': f'獲取 Session 失敗：{str(e)}'}, status=500)
