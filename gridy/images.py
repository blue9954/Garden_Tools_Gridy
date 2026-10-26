from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os
import re
import warnings

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from .config import GridyError, MAX_FILE_BYTES, MAX_IMAGES, MAX_PIXELS, PREVIEW_LONG_EDGE

SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
SRGB_BYTES = SRGB.tobytes()


@dataclass(frozen=True)
class Source:
    path: Path
    digest: str
    stamp: tuple[int, int]
    size: tuple[int, int]
    import_order: int
    preview: Image.Image = field(repr=False, compare=False)


def path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def natural_key(path: Path):
    parts = tuple((1, int(s)) if s.isdigit() else (0, s.casefold())
                  for s in re.split(r"(\d+)", path.name))
    return parts, str(path).casefold()


def _stamp(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def read_source(path: Path) -> tuple[Image.Image, str, tuple[int, int]]:
    """Read one stable snapshot. Returned RGBA pixels are oriented sRGB."""
    try:
        expected = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(path.suffix.lower())
        if not path.exists():
            raise GridyError("원본 파일을 찾을 수 없습니다. 위치를 확인하고 다시 추가하세요.")
        if not path.is_file() or not expected:
            raise GridyError("JPG 또는 정지 PNG 파일을 선택하세요.")
        stamp = _stamp(path)
        if stamp[0] > MAX_FILE_BYTES:
            raise GridyError("파일 크기가 100MB 제한을 초과합니다.")
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise GridyError("파일 크기가 100MB 제한을 초과합니다.")
        if _stamp(path) != stamp:
            raise GridyError("읽는 동안 원본이 변경되었습니다. 다시 추가하세요.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as raw:
                if raw.format != expected:
                    raise GridyError("파일 확장자와 실제 이미지 형식이 다릅니다.")
                if raw.width * raw.height > MAX_PIXELS:
                    raise GridyError("이미지가 60MP 제한을 초과합니다.")
                if getattr(raw, "n_frames", 1) != 1:
                    raise GridyError("애니메이션 이미지는 지원하지 않습니다.")
                raw.load()
                oriented = ImageOps.exif_transpose(raw)
                profile = oriented.info.get("icc_profile")
                if oriented.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK"}:
                    raise GridyError(f"지원하지 않는 색상 모드입니다: {oriented.mode}")
                if oriented.mode == "CMYK" and not profile:
                    raise GridyError("CMYK 사진에는 유효한 ICC 프로파일이 필요합니다.")
                alpha = oriented.convert("RGBA").getchannel("A")
                color = oriented
                if oriented.mode in {"P", "RGBA", "1"}:
                    color = oriented.convert("RGB")
                elif oriented.mode == "LA":
                    color = oriented.getchannel("L")
                if profile:
                    color = ImageCms.profileToProfile(color, ImageCms.ImageCmsProfile(BytesIO(profile)),
                                                      SRGB, outputMode="RGB")
                else:
                    color = color.convert("RGB")
                image = color.convert("RGBA")
                image.putalpha(alpha)
                image.info.clear()
        return image, sha256(data).hexdigest(), stamp
    except GridyError as exc:
        raise GridyError(f"{path.name}\n{exc}") from exc
    except (OSError, ValueError, UnidentifiedImageError, ImageCms.PyCMSError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise GridyError(f"{path.name}\n이미지를 읽거나 색상을 변환할 수 없습니다.\n{exc}") from exc


def import_batch(paths: list[str], existing: list[Source]) -> tuple[list[Source], int]:
    known = {path_key(source.path) for source in existing}
    pending = []
    duplicates = 0
    for name in paths:
        path = Path(name).resolve()
        key = path_key(path)
        if key in known:
            duplicates += 1
        else:
            known.add(key)
            pending.append(path)
    if len(existing) + len(pending) > MAX_IMAGES:
        raise GridyError("한 번에 합칠 사진은 2~3장입니다. 이번 추가 작업은 적용하지 않았습니다.")
    next_order = max((source.import_order for source in existing), default=-1) + 1
    added = []
    for index, path in enumerate(sorted(pending, key=natural_key)):
        image, digest, stamp = read_source(path)
        size = image.size
        image.thumbnail((PREVIEW_LONG_EDGE, PREVIEW_LONG_EDGE), Image.Resampling.LANCZOS)
        added.append(Source(path, digest, stamp, size, next_order + index, image))
    return added, duplicates


def source_anchor(sources: list[Source]) -> Source:
    if not sources:
        raise GridyError("사진을 먼저 추가하세요.")
    return min(sources, key=lambda source: source.import_order)


def reload_unchanged(source: Source) -> Image.Image:
    image, digest, stamp = read_source(source.path)
    if digest != source.digest or stamp != source.stamp:
        raise GridyError(f"{source.path.name}\n원본이 변경되었습니다. 사진을 제거한 뒤 다시 추가하세요.")
    return image

