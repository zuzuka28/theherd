from .models import Video

def recent_videos(request):
    return {
        'recent_videos': Video.objects.all().order_by('-uploaded_at')[:5]
    }
