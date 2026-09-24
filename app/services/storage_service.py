"""Local-filesystem storage backend.

The public functions here (`save_file`, `read_bytes`, `build_path`) are the
only surface the rest of the app talks to. Swapping to S3/MinIO in a later
phase means reimplementing this module only.
"""
import hashlib
import re
import uuid
from pathlib import Path

from app.config import get_settings

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name  # strips any directory components (path traversal)
    name = _SAFE_NAME_RE.sub("_", name)
    return name or "upload"


def build_path(dataset_id: int, version_number: int, filename: str) -> Path:
    settings = get_settings()
    safe_name = sanitize_filename(filename)
    directory = settings.storage_dir / str(dataset_id)
    directory.mkdir(parents=True, exist_ok=True)
    unique_name = f"v{version_number}_{uuid.uuid4().hex[:8]}_{safe_name}"
    path = directory / unique_name
    # Defense in depth: ensure the resolved path is still inside storage_dir.
    resolved = path.resolve()
    if settings.storage_dir.resolve() not in resolved.parents:
        raise ValueError("Resolved storage path escapes storage directory")
    return path


def save_file(path: Path, content: bytes) -> str:
    path.write_bytes(content)
    return checksum_bytes(content)


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def checksum_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def delete_file(path: Path) -> None:
    path.unlink(missing_ok=True)
