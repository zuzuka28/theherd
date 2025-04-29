from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Video, Detection
from .tasks import process_video_detections


class VideoUploadView(View):
    template_name = "video_upload.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        if not request.FILES.get("video"):
            return render(request, self.template_name, {"error": "No video file"})

        video = Video.objects.create(
            source_file=request.FILES["video"], status="uploaded"
        )
        process_video_detections.delay(video.id)

        return redirect("video_status", video_id=video.id)


class VideoStatusView(View):
    template_name = "video_status.html"

    def get(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)
        context = {
            "video": video,
            "processed_at": video.processed_at.isoformat()
            if video.processed_at
            else None,
        }
        return render(request, self.template_name, context)


class DetectionResultsView(View):
    template_name = "detection_results.html"
    per_page = 10

    def get(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)

        if video.status != "completed":
            return render(request, "processing.html", {"video": video})

        page = int(request.GET.get("page", 1))
        detections = Detection.objects.filter(video_id=video.id)
        paginator = Paginator(detections, self.per_page)
        page_obj = paginator.get_page(page)

        context = {
            "video": video,
            "detections": page_obj,
            "pagination": {
                "total": paginator.count,
                "pages": paginator.num_pages,
                "current": page,
            },
        }
        return render(request, self.template_name, context)


class VideoList(View):
    template_name = "video_list.html"

    def get(self, request):
        status_filter = request.GET.get("status", "")

        videos = Video.objects.all().order_by("-uploaded_at")

        if status_filter:
            videos = videos.filter(status=status_filter)

        paginator = Paginator(videos, 10)
        page = request.GET.get("page")

        try:
            videos_page = paginator.page(page)
        except PageNotAnInteger:
            videos_page = paginator.page(1)
        except EmptyPage:
            videos_page = paginator.page(paginator.num_pages)

        context = {
            "videos": videos_page,
            "status_filter": status_filter,
            "status_choices": Video.STATUS_CHOICES,
        }

        return render(request, self.template_name, context)


class HomeView(View):
    template_name = "index.html"

    def get(self, request):
        recent_videos = Video.objects.order_by("-uploaded_at")[:5]
        return render(request, self.template_name, {"recent_videos": recent_videos})
