from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings

try:
    import cv2  # type: ignore
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None


ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class UploadValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ImageMetadata:
    width: int
    height: int
    extension: str


def _detect_face_count(image_bytes: bytes) -> int | None:
    if cv2 is None or np is None:
        return None

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        return None

    grayscale = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(grayscale, scaleFactor=1.1, minNeighbors=5)
    return len(faces)


def validate_upload_bytes(image_bytes: bytes, mime_type: str | None) -> ImageMetadata:
    settings = get_settings()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError("invalid_type", "Only JPG and PNG images are allowed.")

    size_limit_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(image_bytes) > size_limit_bytes:
        raise UploadValidationError("file_too_large", "Uploaded image exceeds the size limit.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise UploadValidationError("invalid_image", "Cannot decode the uploaded image.") from exc

    if width < 512 or height < 512:
        raise UploadValidationError(
            "image_too_small", "Please upload an image that is at least 512px on each side."
        )

    ratio = width / height
    if ratio < 0.5 or ratio > 2.0:
        raise UploadValidationError(
            "bad_aspect_ratio", "Please upload a standard portrait or everyday photo."
        )

    face_count = _detect_face_count(image_bytes)
    if settings.enforce_face_detection and face_count == 0:
        raise UploadValidationError("no_face", "No clear face was detected in the image.")
    if settings.enforce_face_detection and face_count and face_count > 1:
        raise UploadValidationError("multiple_faces", "Please upload a photo with only one person.")

    return ImageMetadata(width=width, height=height, extension=ALLOWED_MIME_TYPES[mime_type])


def _write_file(data: bytes, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    settings = get_settings()
    return str(destination.relative_to(settings.storage_dir))


def save_upload_file(image_bytes: bytes, extension: str) -> str:
    settings = get_settings()
    filename = f"{uuid.uuid4().hex}{extension}"
    return _write_file(image_bytes, settings.upload_dir / filename)


def save_result_file(job_id: str, image_bytes: bytes) -> str:
    settings = get_settings()
    extension = ".png"
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = (image.format or "").lower()
        if image_format in {"jpeg", "jpg"}:
            extension = ".jpg"
        elif image_format == "png":
            extension = ".png"
        elif image_format == "webp":
            extension = ".webp"
    except UnidentifiedImageError:
        extension = ".png"

    filename = f"{job_id}{extension}"
    return _write_file(image_bytes, settings.result_dir / filename)
