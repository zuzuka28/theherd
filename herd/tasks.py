import os
import logging
from typing import Dict, List, Tuple

import cv2
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.core.files.base import File

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

    if not os.path.exists(video.source_file.path):
        raise FileNotFoundError(
            f"Video file not found for video_id {video_id}")

    try:
        update_video_status(video, "processing", success=False)

        detections = make_detections(video.source_file.path)

        saved_count = save_detections(video, detections)

        filename = os.path.basename(video.source_file.path)
        filename, ext = filename.split(".")
        processed_filename = f"{filename}_processed.{ext}"
        temp_file = f"/tmp/{processed_filename}"

        draw_detections_on_video(
            video.source_file.path,
            temp_file,
            detections,
        )

        with open(temp_file, "rb") as f:
            video.processed_file.save(processed_filename, File(f))

        os.remove(temp_file)

        update_video_status(video, "completed", success=True)

        logger.info(f"video {video_id} processed, {saved_count} detections")
    except Exception as exc:
        update_video_status(video, "failed", success=False)

        logger.info(f"video {video_id} failed, error: {exc}")


def make_detections(
    video_path: str, confidence_threshold: float = 0.5
) -> List[DetectionResult]:
    detections = []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"can't open video: {video_path}")

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
                if int(box.cls) == HORSE_CLASS_ID and box.conf >= confidence_threshold:
                    x, y, w, h = box.xywh[0].tolist()

                    detections.append(
                        {
                            "timestamp": timestamp,
                            "confidence": float(box.conf),
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h,
                            "frame_num": frame_count,
                        }
                    )

        frame_count += 1

    cap.release()

    return detections


def draw_detections_on_video(
    input_video_path: str,
    output_video_path: str,
    detections: List[Dict],
    confidence_threshold: float = 0.5,
    box_color: tuple = (0, 255, 0),
    text_color: tuple = (0, 0, 255),
) -> None:
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {input_video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = 0

    fourcc = cv2.VideoWriter_fourcc(*"MP4V")
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    if not out.isOpened():
        raise ValueError(f"can't create video: {output_video_path}")

    detections_by_frame = {}
    for det in detections:
        frame_num = det.get("frame_num", int(det["timestamp"] * fps))
        if frame_num not in detections_by_frame:
            detections_by_frame[frame_num] = []
        detections_by_frame[frame_num].append(det)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_detections = detections_by_frame.get(frame_count, [])

        for det in current_detections:
            if det["confidence"] >= confidence_threshold:
                x, y, w, h = det["x"], det["y"], det["width"], det["height"]
                x1, y1 = int(x - w / 2), int(y - h / 2)
                x2, y2 = int(x + w / 2), int(y + h / 2)

                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

                label = f"Horse: {det['confidence']:.2f}"
                (text_width, text_height), _ = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                )

                cv2.rectangle(
                    frame,
                    (x1, y1 - text_height - 10),
                    (x1 + text_width, y1 - 10),
                    box_color,
                    -1,
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    text_color,
                    2,
                )

        out.write(frame)
        frame_count += 1

    cap.release()
    out.release()


def save_detections(video: Video, detections: List[DetectionResult]) -> int:
    created_count = 0
    for detection in detections:
        _, created = Detection.objects.get_or_create(
            video=video,
            timestamp=detection["timestamp"],
            x=detection["x"],
            y=detection["y"],
            width=detection["width"],
            height=detection["height"],
            defaults={
                "confidence": detection["confidence"],
                "x": detection["x"],
                "y": detection["y"],
                "width": detection["width"],
                "height": detection["height"],
                "frame": detection["frame_num"],
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
