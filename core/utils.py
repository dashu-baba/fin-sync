from __future__ import annotations
from pathlib import Path
import hashlib
from typing import BinaryIO
import hashlib

def human_size(num_bytes: int) -> str:
    units = ["B","KB","MB","GB","TB"]
    size, idx = float(num_bytes), 0
    while size >= 1024 and idx < len(units)-1:
        size /= 1024; idx += 1
    return f"{size:.1f} {units[idx]}"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def safe_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(data)

def make_id(*parts: str) -> str:
    joined = "||".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]
