from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Terms, UserTermsAgreement, Announcement


@login_required
@require_POST
def agree_to_terms(request):
    """處理使用者同意條款的 AJAX 請求"""
    try:
        latest_terms = Terms.get_latest()
        if not latest_terms:
            return JsonResponse({
                'success': False,
                'message': '目前沒有有效的條款'
            })

        # 獲取客戶端資訊（不記錄 IP 地址）
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # 建立同意記錄（不記錄 IP 地址）
        agreement, created = UserTermsAgreement.create_agreement(
            user=request.user,
            terms=latest_terms,
            user_agent=user_agent
        )

        if created:
            return JsonResponse({
                'success': True,
                'message': '條款同意已記錄'
            })
        else:
            return JsonResponse({
                'success': True,
                'message': '您已經同意過此條款'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'處理失敗：{str(e)}'
        })


@login_required
def check_terms_status(request):
    """檢查使用者是否需要同意條款"""
    latest_terms = Terms.get_latest()
    if not latest_terms:
        return JsonResponse({
            'needs_agreement': False,
            'terms_content': None
        })

    needs_agreement = not UserTermsAgreement.has_agreed_to_latest(request.user)
    
    return JsonResponse({
        'needs_agreement': needs_agreement,
        'terms_content': latest_terms.content if needs_agreement else None,
        'terms_title': latest_terms.title if needs_agreement else None,
        'terms_version': latest_terms.version if needs_agreement else None
    })


def get_latest_terms_content(request):
    """獲取最新條款內容（用於顯示用途）"""
    latest_terms = Terms.get_latest()
    if not latest_terms:
        return JsonResponse({
            'success': False,
            'message': '目前沒有有效的條款',
            'terms_content': None
        })
    
    return JsonResponse({
        'success': True,
        'terms_content': latest_terms.content,
        'terms_title': latest_terms.title,
        'terms_version': latest_terms.version,
        'updated_at': latest_terms.updated_at.isoformat()
    })


def get_latest_announcement(request):
    """獲取最新的活躍公告"""
    try:
        announcement = Announcement.get_latest_active()
        if not announcement:
            return JsonResponse({
                'has_announcement': False,
                'announcement': None
            })

        return JsonResponse({
            'has_announcement': True,
            'announcement': {
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content,
                'is_important': announcement.is_important,
                'created_at': announcement.created_at.isoformat(),
                'created_by': announcement.created_by.username
            }
        })

    except Exception as e:
        return JsonResponse({
            'has_announcement': False,
            'error': f'獲取公告失敗：{str(e)}'
        })


def announcement_detail(request, announcement_id):
    """獲取特定公告的詳細內容"""
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        
        # 檢查公告是否仍然活躍
        if not announcement.is_currently_active:
            return JsonResponse({
                'success': False,
                'message': '此公告已失效'
            })

        return JsonResponse({
            'success': True,
            'announcement': {
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content,
                'is_important': announcement.is_important,
                'created_at': announcement.created_at.isoformat(),
                'updated_at': announcement.updated_at.isoformat(),
                'created_by': announcement.created_by.username
            }
        })

    except Announcement.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '公告不存在'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'獲取公告失敗：{str(e)}'
        })
