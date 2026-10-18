"""Скачивает веса YOLOX (Apache-2.0, официальные релизы Megvii) и проверяет SHA-256.

После скачивания сервису интернет не нужен — веса можно перенести во внутренний контур.

    python scripts/download_models.py                 # tiny + s в ./models
    python scripts/download_models.py --models tiny   # только tiny
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

RELEASE = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0"
MODELS = {
    "tiny": ("yolox_tiny.onnx", "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"),
    "s": ("yolox_s.onnx", "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, expected: str, destination: Path) -> None:
    target = destination / name
    if target.is_file() and sha256(target) == expected:
        print(f"[ok] {name} уже скачан")
        return
    partial = target.with_suffix(".part")
    print(f"[..] {name} ← {RELEASE}/{name}")
    with urllib.request.urlopen(f"{RELEASE}/{name}", timeout=120) as response, partial.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    actual = sha256(partial)
    if actual != expected:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"[!!] {name}: контрольная сумма не совпала ({actual})")
    partial.replace(target)
    print(f"[ok] {name} ({target.stat().st_size / 1e6:.1f} МБ)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", type=Path, default=Path(__file__).resolve().parents[1] / "models")
    parser.add_argument("--models", nargs="+", choices=sorted(MODELS), default=["tiny", "s"])
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    for key in args.models:
        download(*MODELS[key], args.dest)


if __name__ == "__main__":
    sys.exit(main())
