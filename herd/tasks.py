import os
import logging
from typing import Dict, List, Tuple

import cv2
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from ultralytics import YOLO

from .models import Detection, Video

logger = logging.getLogger(__name__)

BoundingBox = Tuple[float, float, float, float]
DetectionResult = Dict[str, float]

YOLO_MODEL = YOLO("yolov8n.pt")
HORSE_CLASS_ID = 17


@shared_task
def process_video_detections(video_id: int) -> None:
    logger.info(f"start processing {video_id}")

    try:
        video: Video = Video.objects.get(id=video_id)
    except ObjectDoesNotExist:
        return None

    if not os.path.exists(video.video_file.path):
        raise FileNotFoundError(
            f"Video file not found for video_id {video_id}")

    try:
        update_video_status(video, "processing")

        detections = process_video_with_yolo(video.video_file.path)

        saved_count = save_detections(video, detections)

        update_video_status(video, "completed", success=True)

        logger.info(f"video {video_id} processed, {saved_count} detections")
    except Exception as exc:
        update_video_status(video, "failed", success=False)

        logger.info(f"video {video_id} failed, error: {exc}")


def process_video_with_yolo(
    video_path: str, confidence_threshold: float = 0.5
) -> List[DetectionResult]:
    detections = []
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_count / fps

        results = YOLO_MODEL(frame, verbose=False)

        for result in results:
            for box in result.boxes:
                is_horce_class = int(box.cls) == HORSE_CLASS_ID
                is_confident = box.conf >= confidence_threshold
                if is_horce_class and is_confident:
                    detections.append(
                        {
                            "timestamp": timestamp,
                            "confidence": float(box.conf),
                            "x": float(box.xywh[0][0]),
                            "y": float(box.xywh[0][1]),
                            "width": float(box.xywh[0][2]),
                            "height": float(box.xywh[0][3]),
                        }
                    )

        frame_count += 1

    cap.release()

    return detections


def save_detections(video: Video, detections: List[DetectionResult]) -> int:
    created_count = 0
    for detection in detections:
        _, created = Detection.objects.get_or_create(
            video=video,
            timestamp=detection["timestamp"],
            defaults={
                "confidence": detection["confidence"],
                "x": detection["x"],
                "y": detection["y"],
                "width": detection["width"],
                "height": detection["height"],
            },
        )
        if created:
            created_count += 1

    return created_count


def update_video_status(
    video: Video,
    status: str,
    success: bool = True,
) -> None:
    video.status = status
    video.processed_at = timezone.now() if success else None
    video.save()
