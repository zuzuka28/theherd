from django.urls import path
from .views import (
    VideoList,
    VideoUploadView,
    VideoStatusView,
    VideoReportPDFView,
    DetectionResultsView,
)

urlpatterns = [
    path("", VideoList.as_view(), name="video_list"),
    path(
        "upload/",
        VideoUploadView.as_view(),
        name="video_upload",
    ),
    path(
        "status/<int:video_id>/",
        VideoStatusView.as_view(),
        name="video_status",
    ),
    path(
        "results/<int:video_id>/",
        DetectionResultsView.as_view(),
        name="detection_results",
    ),
    path(
        "results/<int:video_id>/report/",
        VideoReportPDFView.as_view(),
        name="video_report_pdf",
    ),
]
