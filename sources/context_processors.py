from .models import Source

def sources_context(request):
    """
    Makes all Source objects available to all templates.
    """
    sources = Source.objects.all()
    return {'sources': sources}
