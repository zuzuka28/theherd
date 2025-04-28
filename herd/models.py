from django.db import models


class Video(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.AutoField(primary_key=True)
    video_file = models.FileField(upload_to="uploads/%Y/%m/%d")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class Detection(models.Model):
    id = models.AutoField(primary_key=True)
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="detections"
    )
    timestamp = models.FloatField()
    confidence = models.FloatField()
    x = models.FloatField()
    y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=["video", "timestamp"]),
        ]
