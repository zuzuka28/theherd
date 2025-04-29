import base64
from io import BytesIO

import matplotlib.pyplot as plt
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.views.generic import View

import cv2
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from .models import Detection, Video
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


class PDFRendererMixin:
    template_name = ""
    pdf_filename = "report.pdf"
    font_config = FontConfiguration()

    def render_to_pdf(self, context):
        html_string = render_to_string(self.template_name, context)
        html = HTML(string=html_string)
        return html.write_pdf(font_config=self.font_config)

    def get_pdf_response(self, pdf_content, filename=None):
        response = HttpResponse(pdf_content, content_type="application/pdf")
        filename = filename or self.pdf_filename
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ChartGeneratorMixin:
    @staticmethod
    def generate_line_chart(x_data, y_data, title, x_label, y_label):
        plt.figure(figsize=(8, 4))
        plt.plot(x_data, y_data, "b-")
        plt.title(title)
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.grid(True)

        buffer = BytesIO()
        plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
        plt.close()

        return base64.b64encode(buffer.getvalue()).decode("utf-8")


class BaseReportView(PDFRendererMixin, ChartGeneratorMixin, View):
    context_object_name = None

    def get_report_context(self, **kwargs):
        raise NotImplementedError

    def get_pdf_filename(self, context):
        return self.pdf_filename

    def get(self, request, *args, **kwargs):
        try:
            context = self.get_report_context(**kwargs)
            pdf_content = self.render_to_pdf(context)
            filename = self.get_pdf_filename(context)
            return self.get_pdf_response(pdf_content, filename)

        except Exception as e:
            return HttpResponse(f"Error generating report: {str(e)}", status=500)


class VideoReportPDFView(BaseReportView):
    template_name = "reports/video_report.html"
    context_object_name = "video"
    max_detections_per_page = 50

    def get_report_context(self, **kwargs):
        video_id = kwargs.get("video_id")

        video = Video.objects.get(pk=video_id)
        detections = Detection.objects.filter(video_id=video_id)

        stats = self.calculate_detection_stats(detections)

        charts = {
            "confidence_chart": self.generate_confidence_chart(detections),
            "objects_per_frame_chart": self.generate_objects_per_frame_chart(
                detections
            ),
        }

        sample_frames = []
        sample_frames = self.get_sample_frames(video, detections)

        return {
            "video": video,
            "detections": detections,
            "generated_at": now(),
            "stats": stats,
            "charts": charts,
            "sample_frames": sample_frames,
            "paginate_by": self.max_detections_per_page,
        }

    def calculate_detection_stats(self, detections):
        if not detections:
            return {}

        confidences = [d.confidence for d in detections]
        frames = {}

        for d in detections:
            frames.setdefault(d.frame, 0)
            frames[d.frame] += 1

        objects_per_frame = list(frames.values())

        return {
            "total": len(detections),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "max_objects_frame": max(frames.items(), key=lambda x: x[1]),
            "min_objects_frame": min(frames.items(), key=lambda x: x[1]),
            "avg_objects_per_frame": sum(objects_per_frame) / len(objects_per_frame),
            "frames_with_objects": len(frames),
        }

    def generate_objects_per_frame_chart(self, detections):
        if not detections:
            return None

        frames = {}
        for d in detections:
            frames.setdefault(d.frame, 0)
            frames[d.frame] += 1

        frame_numbers = sorted(frames.keys())
        objects_count = [frames[f] for f in frame_numbers]

        return self.generate_line_chart(
            frame_numbers,
            objects_count,
            "Количество объектов по кадрам",
            "Номер кадра",
            "Количество объектов",
        )

    def get_sample_frames(self, video, detections, num_samples=3):
        if not detections or not video.processed_file:
            return []

        video_path = video.processed_file.path

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"can't open video: {video_path}")

        frame_detections = {}
        for d in detections:
            frame_detections.setdefault(d.frame, []).append(d)

        top_frames = sorted(
            frame_detections.items(), key=lambda x: len(x[1]), reverse=True
        )[:num_samples]

        sample_images = []

        for frame_num, detections in top_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            timestamp = detections[0].timestamp
            cv2.putText(
                frame_rgb,
                f"{timestamp:.2f}s",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            _, buffer = cv2.imencode(".png", frame_rgb)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
            sample_images.append(img_base64)

        return sample_images

    def generate_confidence_chart(self, detections):
        timestamps = [d.timestamp for d in detections]
        confidences = [d.confidence for d in detections]
        return self.generate_line_chart(
            timestamps,
            confidences,
            "Уверенность обнаружений по времени",
            "Время (с)",
            "Уверенность (%)",
        )

    def get_pdf_filename(self, context):
        return f"video_report_{context['video'].id}.pdf"


class HomeView(View):
    template_name = "index.html"

    def get(self, request):
        recent_videos = Video.objects.order_by("-uploaded_at")[:5]
        return render(request, self.template_name, {"recent_videos": recent_videos})
