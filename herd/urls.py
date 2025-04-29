from django.urls import path
from .views import (
    HomeView,
    VideoList,
    VideoUploadView,
    VideoStatusView,
    DetectionResultsView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("/", VideoList.as_view(), name="video_list"),
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
]
