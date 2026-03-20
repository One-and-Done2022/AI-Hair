from __future__ import annotations

import io
import shutil
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from app.config import get_settings

try:
    import cv2  # type: ignore
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None

try:
    import oss2  # type: ignore
except ImportError:  # pragma: no cover
    oss2 = None


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


class ObjectStorageBackend:
    is_local = False

    def write_bytes(self, object_key: str, data: bytes) -> str:
        raise NotImplementedError

    def read_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        raise NotImplementedError

    def list_keys(self, prefix: str) -> list[str]:
        raise NotImplementedError

    def public_url(self, object_key: str, *, base_url: str | None = None) -> str:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorageBackend):
    is_local = True

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def write_bytes(self, object_key: str, data: bytes) -> str:
        destination = self.root_dir / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return object_key

    def read_bytes(self, object_key: str) -> bytes:
        return (self.root_dir / object_key).read_bytes()

    def delete_prefix(self, prefix: str) -> None:
        base_path = self.root_dir / prefix
        if base_path.is_file():
            base_path.unlink()
            return

        if base_path.exists():
            shutil.rmtree(base_path)
            return

        parent = base_path.parent
        if not parent.exists():
            return
        for path in parent.iterdir():
            if path.is_file() and path.name.startswith(base_path.name):
                path.unlink()

    def list_keys(self, prefix: str) -> list[str]:
        base_path = self.root_dir / prefix
        if base_path.is_dir():
            return sorted(
                path.relative_to(self.root_dir).as_posix()
                for path in base_path.iterdir()
                if path.is_file()
            )

        parent = base_path.parent
        if not parent.exists():
            return []
        return sorted(
            path.relative_to(self.root_dir).as_posix()
            for path in parent.iterdir()
            if path.is_file() and path.name.startswith(base_path.name)
        )

    def public_url(self, object_key: str, *, base_url: str | None = None) -> str:
        if not base_url:
            raise ValueError("base_url is required when resolving local media URLs.")
        return f"{base_url.rstrip('/')}/media/{object_key}"


class AliyunOssObjectStorage(ObjectStorageBackend):
    def __init__(
        self,
        *,
        endpoint: str,
        bucket_name: str,
        access_key_id: str,
        access_key_secret: str,
        public_base_url: str,
        prefix: str,
    ) -> None:
        if oss2 is None:
            raise RuntimeError("oss2 must be installed when using aliyun_oss storage backend.")
        if not endpoint or not bucket_name or not access_key_id or not access_key_secret:
            raise RuntimeError("Aliyun OSS settings are incomplete.")

        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self.public_base_url = public_base_url.strip().rstrip("/")
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self.endpoint = endpoint.rstrip("/")

    def write_bytes(self, object_key: str, data: bytes) -> str:
        self.bucket.put_object(object_key, data)
        return object_key

    def read_bytes(self, object_key: str) -> bytes:
        return self.bucket.get_object(object_key).read()

    def delete_prefix(self, prefix: str) -> None:
        iterator = oss2.ObjectIteratorV2(self.bucket, prefix=prefix)
        for object_info in iterator:
            self.bucket.delete_object(object_info.key)

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(
            object_info.key
            for object_info in oss2.ObjectIteratorV2(self.bucket, prefix=prefix)
        )

    def public_url(self, object_key: str, *, base_url: str | None = None) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{object_key}"

        parsed = urlparse(self.endpoint if "://" in self.endpoint else f"https://{self.endpoint}")
        host = parsed.netloc or parsed.path
        scheme = parsed.scheme or "https"
        return f"{scheme}://{self.bucket_name}.{host}/{object_key}"


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


@lru_cache
def get_object_storage() -> ObjectStorageBackend:
    settings = get_settings()
    settings.ensure_directories()

    if settings.object_storage_backend == "local":
        return LocalObjectStorage(settings.storage_dir)

    if settings.object_storage_backend == "aliyun_oss":
        return AliyunOssObjectStorage(
            endpoint=settings.oss_endpoint,
            bucket_name=settings.oss_bucket_name,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            public_base_url=settings.object_storage_public_base_url,
            prefix=settings.oss_prefix,
        )

    raise RuntimeError(
        f"Unsupported OBJECT_STORAGE_BACKEND: {settings.object_storage_backend}"
    )


def is_local_media_backend() -> bool:
    return get_object_storage().is_local


def media_url(object_key: str | None, *, base_url: str | None = None) -> str | None:
    if not object_key:
        return None
    return get_object_storage().public_url(object_key, base_url=base_url)


def read_file_bytes(object_key: str) -> bytes:
    return get_object_storage().read_bytes(object_key)


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


def _object_key(*parts: str) -> str:
    settings = get_settings()
    normalized = [part.strip("/") for part in parts if part.strip("/")]
    joined = "/".join(normalized)
    if settings.object_storage_backend == "aliyun_oss" and settings.oss_prefix:
        return f"{settings.oss_prefix}/{joined}"
    return joined


def save_upload_file(image_bytes: bytes, extension: str) -> str:
    filename = f"{uuid.uuid4().hex}{extension}"
    object_key = _object_key("uploads", filename)
    return get_object_storage().write_bytes(object_key, image_bytes)


def save_preview_result(job_id: str, image_bytes: bytes) -> str:
    extension = _detect_result_extension(image_bytes)
    prefix = _object_key("results", job_id)
    get_object_storage().delete_prefix(prefix)
    object_key = _object_key("results", job_id, f"preview{extension}")
    return get_object_storage().write_bytes(object_key, image_bytes)


def save_result_bundle(job_id: str, candidate_images: list[bytes]) -> SavedResultBundle:
    if not candidate_images:
        raise ValueError("candidate_images cannot be empty")

    prefix = _object_key("results", job_id)
    get_object_storage().delete_prefix(prefix)

    candidate_paths: list[str] = []
    for index, image_bytes in enumerate(candidate_images, start=1):
        extension = _detect_result_extension(image_bytes)
        object_key = _object_key("results", job_id, f"candidate-{index}{extension}")
        candidate_paths.append(get_object_storage().write_bytes(object_key, image_bytes))

    return SavedResultBundle(
        primary_path=candidate_paths[0],
        candidate_paths=candidate_paths,
    )


def list_result_candidates(job_id: str, primary_path: str | None = None) -> list[str]:
    prefix = _object_key("results", job_id, "candidate-")
    keys = get_object_storage().list_keys(prefix)
    if keys:
        return keys
    return [primary_path] if primary_path else []
