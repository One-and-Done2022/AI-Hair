from __future__ import annotations

import io
import shutil
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
MIN_FACE_WIDTH_RATIO = 0.14
MIN_FACE_HEIGHT_RATIO = 0.14
MIN_FACE_AREA_RATIO = 0.025


class UploadValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ImageMetadata:
    width: int
    height: int
    extension: str


@dataclass(slots=True)
class SavedResultBundle:
    primary_path: str
    candidate_paths: list[str]


def _detect_faces(image_bytes: bytes) -> tuple[tuple[int, int, int, int], ...] | None:
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
    return tuple(tuple(int(value) for value in face) for face in faces)


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

    if settings.enforce_face_detection:
        faces = _detect_faces(image_bytes)
        if faces is None:
            raise UploadValidationError(
                "face_detection_unavailable",
                "Face detection is temporarily unavailable. Please try again later.",
            )
        if len(faces) == 0:
            raise UploadValidationError("no_face", "No clear face was detected in the image.")
        if len(faces) > 1:
            raise UploadValidationError("multiple_faces", "Please upload a photo with only one person.")

        _, _, face_width, face_height = faces[0]
        face_area_ratio = (face_width * face_height) / float(width * height)
        face_width_ratio = face_width / float(width)
        face_height_ratio = face_height / float(height)
        if (
            face_width_ratio < MIN_FACE_WIDTH_RATIO
            or face_height_ratio < MIN_FACE_HEIGHT_RATIO
            or face_area_ratio < MIN_FACE_AREA_RATIO
        ):
            raise UploadValidationError(
                "face_too_small",
                "Please upload a chest-up or close-up portrait with one clear face.",
            )

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


def _detect_result_extension(image_bytes: bytes) -> str:
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
    return extension


def _remove_primary_result_files(job_id: str) -> None:
    settings = get_settings()
    for path in settings.result_dir.glob(f"{job_id}.*"):
        if path.is_file():
            path.unlink()


def save_preview_result(job_id: str, image_bytes: bytes) -> str:
    settings = get_settings()
    extension = _detect_result_extension(image_bytes)
    _remove_primary_result_files(job_id)
    return _write_file(
        image_bytes,
        settings.result_dir / f"{job_id}{extension}",
    )


def save_result_bundle(job_id: str, candidate_images: list[bytes]) -> SavedResultBundle:
    if not candidate_images:
        raise ValueError("candidate_images cannot be empty")

    settings = get_settings()
    primary_extension = _detect_result_extension(candidate_images[0])
    _remove_primary_result_files(job_id)
    primary_path = _write_file(
        candidate_images[0],
        settings.result_dir / f"{job_id}{primary_extension}",
    )

    candidate_dir = settings.result_dir / job_id
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)

    candidate_paths: list[str] = []
    for index, image_bytes in enumerate(candidate_images, start=1):
        extension = _detect_result_extension(image_bytes)
        candidate_paths.append(
            _write_file(
                image_bytes,
                candidate_dir / f"candidate-{index}{extension}",
            )
        )

    return SavedResultBundle(primary_path=primary_path, candidate_paths=candidate_paths)


def list_result_candidates(job_id: str, primary_path: str | None = None) -> list[str]:
    settings = get_settings()
    candidate_dir = settings.result_dir / job_id
    if candidate_dir.exists():
        paths = sorted(
            path.relative_to(settings.storage_dir).as_posix()
            for path in candidate_dir.iterdir()
            if path.is_file()
        )
        if paths:
            return paths
    return [primary_path] if primary_path else []
