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
MIN_FACE_WIDTH_RATIO = 0.11
MIN_FACE_HEIGHT_RATIO = 0.11
MIN_FACE_AREA_RATIO = 0.015
MIN_PROMINENT_FACE_AREA_RATIO = 0.015
MIN_PROMINENT_FACE_WIDTH_RATIO = 0.14
MIN_PROMINENT_FACE_HEIGHT_RATIO = 0.14
FACE_OVERLAP_IOU_THRESHOLD = 0.35
SECONDARY_FACE_AREA_SHARE = 0.5
FACE_DETECTION_MAX_DIMENSION = 1280


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

    original_height, original_width = decoded.shape[:2]
    detection_image = decoded
    largest_dimension = max(original_width, original_height)
    if largest_dimension > FACE_DETECTION_MAX_DIMENSION:
        scale = FACE_DETECTION_MAX_DIMENSION / float(largest_dimension)
        detection_image = cv2.resize(
            decoded,
            (
                max(1, int(round(original_width * scale))),
                max(1, int(round(original_height * scale))),
            ),
            interpolation=cv2.INTER_AREA,
        )

    height, width = detection_image.shape[:2]
    grayscale = cv2.cvtColor(detection_image, cv2.COLOR_BGR2GRAY)
    grayscale = cv2.equalizeHist(grayscale)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    min_size = (max(64, int(width * 0.08)), max(64, int(height * 0.08)))
    faces = cascade.detectMultiScale(
        grayscale,
        scaleFactor=1.08,
        minNeighbors=6,
        minSize=min_size,
    )

    if height == original_height and width == original_width:
        return tuple(tuple(int(value) for value in face) for face in faces)

    scale_x = original_width / float(width)
    scale_y = original_height / float(height)
    restored_faces: list[tuple[int, int, int, int]] = []
    for x, y, face_width, face_height in faces:
        restored_faces.append(
            (
                int(round(x * scale_x)),
                int(round(y * scale_y)),
                int(round(face_width * scale_x)),
                int(round(face_height * scale_y)),
            )
        )
    return tuple(restored_faces)


def _face_area(face: tuple[int, int, int, int]) -> int:
    return face[2] * face[3]


def _face_iou(
    left: tuple[int, int, int, int], right: tuple[int, int, int, int]
) -> float:
    left_x1, left_y1, left_w, left_h = left
    right_x1, right_y1, right_w, right_h = right
    left_x2 = left_x1 + left_w
    left_y2 = left_y1 + left_h
    right_x2 = right_x1 + right_w
    right_y2 = right_y1 + right_h

    overlap_x1 = max(left_x1, right_x1)
    overlap_y1 = max(left_y1, right_y1)
    overlap_x2 = min(left_x2, right_x2)
    overlap_y2 = min(left_y2, right_y2)

    overlap_w = max(0, overlap_x2 - overlap_x1)
    overlap_h = max(0, overlap_y2 - overlap_y1)
    overlap_area = overlap_w * overlap_h
    if overlap_area == 0:
        return 0.0

    union_area = _face_area(left) + _face_area(right) - overlap_area
    if union_area <= 0:
        return 0.0
    return overlap_area / float(union_area)


def _normalize_detected_faces(
    faces: tuple[tuple[int, int, int, int], ...], width: int, height: int
) -> tuple[tuple[int, int, int, int], ...]:
    if not faces:
        return ()

    image_area = float(width * height)
    deduplicated: list[tuple[int, int, int, int]] = []
    for face in sorted(faces, key=_face_area, reverse=True):
        area_ratio = _face_area(face) / image_area
        if area_ratio < (MIN_PROMINENT_FACE_AREA_RATIO * 0.45):
            continue
        if any(_face_iou(face, kept) >= FACE_OVERLAP_IOU_THRESHOLD for kept in deduplicated):
            continue
        deduplicated.append(face)

    if not deduplicated:
        largest_face = max(faces, key=_face_area)
        deduplicated = [largest_face]

    if len(deduplicated) <= 1:
        return tuple(deduplicated)

    largest_area = float(_face_area(deduplicated[0]))
    prominent_faces = []
    for face in deduplicated:
        area_ratio = _face_area(face) / image_area
        width_ratio = face[2] / float(width)
        height_ratio = face[3] / float(height)
        area_share = _face_area(face) / largest_area if largest_area > 0 else 0.0

        is_similarly_large_face = area_share >= SECONDARY_FACE_AREA_SHARE
        is_independently_prominent_face = (
            area_ratio >= MIN_PROMINENT_FACE_AREA_RATIO
            and width_ratio >= MIN_PROMINENT_FACE_WIDTH_RATIO
            and height_ratio >= MIN_PROMINENT_FACE_HEIGHT_RATIO
        )

        if is_similarly_large_face or is_independently_prominent_face:
            prominent_faces.append(face)

    if not prominent_faces:
        return (deduplicated[0],)

    return tuple(prominent_faces)


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


def delete_media_object(object_key: str | None) -> None:
    if not object_key:
        return
    get_object_storage().delete_prefix(object_key)


def delete_result_bundle(job_id: str) -> None:
    get_object_storage().delete_prefix(_object_key("results", job_id))


def validate_upload_bytes(image_bytes: bytes, mime_type: str | None) -> ImageMetadata:
    settings = get_settings()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError("invalid_type", "仅支持上传 JPG/JPEG 或 PNG 图片。")

    size_limit_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(image_bytes) > size_limit_bytes:
        raise UploadValidationError(
            "file_too_large",
            f"图片大小不能超过 {settings.max_upload_size_mb}MB，请压缩后重试。",
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise UploadValidationError("invalid_image", "图片无法解析，请换一张正常导出的照片。") from exc

    if width < 512 or height < 512:
        raise UploadValidationError(
            "image_too_small", "图片分辨率过低，请上传宽高至少 512px 的清晰照片。"
        )

    ratio = width / height
    if ratio < 0.5 or ratio > 2.0:
        raise UploadValidationError(
            "bad_aspect_ratio",
            "图片比例不合适，请上传常见的人像照或生活照，避免过窄长图和全景图。",
        )

    if settings.enforce_face_detection:
        faces = _detect_faces(image_bytes)
        if faces is None:
            raise UploadValidationError(
                "face_detection_unavailable",
                "人脸检测暂时不可用，请稍后再试。",
            )
        faces = _normalize_detected_faces(faces, width, height)
        if len(faces) == 0:
            raise UploadValidationError(
                "no_face",
                "没有检测到清晰单人脸部，请上传正脸或半侧脸自拍，避免遮挡、逆光和过暗。",
            )
        if len(faces) > 1:
            raise UploadValidationError(
                "multiple_faces",
                "检测到多张明显人脸，请上传仅包含一位人物的自拍或单人照。",
            )

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
                "人脸占比太小，请上传胸口以上近景或更靠近镜头的人像照片。",
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


def save_hair_preview_result(job_id: str, image_bytes: bytes) -> str:
    extension = _detect_result_extension(image_bytes)
    prefix = _object_key("results", job_id, "hair-preview")
    get_object_storage().delete_prefix(prefix)
    object_key = _object_key("results", job_id, f"hair-preview{extension}")
    return get_object_storage().write_bytes(object_key, image_bytes)


def get_hair_preview_path(job_id: str) -> str | None:
    prefix = _object_key("results", job_id, "hair-preview")
    keys = get_object_storage().list_keys(prefix)
    return keys[0] if keys else None


def save_scene_result(job_id: str, image_bytes: bytes, *, index: int) -> str:
    extension = _detect_result_extension(image_bytes)
    prefix = _object_key("results", job_id, f"scene-{index}")
    get_object_storage().delete_prefix(prefix)
    object_key = _object_key("results", job_id, f"scene-{index}{extension}")
    return get_object_storage().write_bytes(object_key, image_bytes)


def list_scene_results(job_id: str) -> list[str]:
    prefix = _object_key("results", job_id, "scene-")
    return get_object_storage().list_keys(prefix)


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


def save_template_asset(category: str, template_id: str, image_bytes: bytes) -> str:
    extension = _detect_result_extension(image_bytes)
    prefix = _object_key("template_assets", category, template_id)
    get_object_storage().delete_prefix(prefix)
    object_key = _object_key("template_assets", category, f"{template_id}{extension}")
    return get_object_storage().write_bytes(object_key, image_bytes)


def delete_template_asset(category: str, template_id: str) -> None:
    get_object_storage().delete_prefix(_object_key("template_assets", category, template_id))


def list_result_candidates(job_id: str, primary_path: str | None = None) -> list[str]:
    prefix = _object_key("results", job_id, "candidate-")
    keys = get_object_storage().list_keys(prefix)
    if keys:
        return keys
    return [primary_path] if primary_path else []
