import logging
from .celery import app as celery_app

logging.basicConfig(encoding="utf-8", level=logging.INFO)

__all__ = ["celery_app"]
