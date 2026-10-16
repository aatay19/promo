from core.models import Announcement

def historial_noticias(request):
    return {
        'todas_las_noticias': Announcement.objects.all().order_by('-created_at'),
    }
