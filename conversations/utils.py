from django.utils import timezone
from .models import Message, SenderChoices


def format_message_data(message):
    message_data = {
        'id': message.id,
        'type': f"{message.sender}_message",
        'sender': message.sender,
        'text': message.text or '',
        'message': message.text or '',
        'status': message.status,
                'timestamp': message.updated_at.astimezone(timezone.get_fixed_timezone(480)).strftime('%H:%M:%S'),
        'updated_at_timestamp': message.updated_at.timestamp()
    }
    
    if message.sender == SenderChoices.AI:
        tool_messages = message.get_related_tool_messages()
        message_data['has_tool_calls'] = tool_messages.exists()
        message_data['tool_calls_count'] = tool_messages.count()
        message_data['references'] = message.references or []
    
    return message_data


def get_recent_messages(session, limit=20):
    return Message.objects.filter(
        session=session,
        is_deleted=False
    ).exclude(sender=SenderChoices.TOOL).order_by('-updated_at')[:limit] 