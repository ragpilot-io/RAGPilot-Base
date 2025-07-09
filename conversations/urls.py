from django.urls import path
from . import views

app_name = 'conversations'

urlpatterns = [
    path('api/messages/<int:message_id>/tool-calls/', views.MessageToolCallsView.as_view(), name='message_tool_calls'),
    path('api/conversation/session/', views.UserSessionView.as_view(), name='get_user_session'),
    path('api/conversations/session/<int:session_id>/messages/', views.ConversationMessageView.as_view(), name='conversation_messages'),
] 