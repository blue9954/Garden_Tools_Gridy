from datetime import datetime
from pathlib import Path
import os
import tempfile

from PIL import Image

from .config import GridyError, JPEG_QUALITY, Options
from .images import Source, SRGB_BYTES, source_anchor
from .render import compose


def verify_output(path: Path, options: Options) -> None:
    with Image.open(path) as image:
        image.load()
        if image.size != (options.width, options.height) or image.mode != "RGB":
            raise GridyError("저장된 이미지의 크기 또는 색상 모드가 올바르지 않습니다.")
        if image.format != options.format or not image.info.get("icc_profile"):
            raise GridyError("저장 형식 또는 sRGB 프로파일 확인에 실패했습니다.")


def _publish(temp: Path, destination: Path) -> None:
    # Windows rename is atomic and refuses an existing destination. POSIX rename
    # replaces it, so use an exclusive hard link on that platform instead.
    if os.name == "nt":
        os.rename(temp, destination)
    else:
        os.link(temp, destination)
        temp.unlink()


def save_collage(sources: list[Source], options: Options, *, now: datetime | None = None) -> Path:
    options.validate()
    if len(sources) not in (2, 3):
        raise GridyError("저장하려면 사진 2~3장이 필요합니다.")
    folder = source_anchor(sources).path.parent
    temp = None
    try:
        canvas, _ = compose(sources, options, full_resolution=True)
        descriptor, name = tempfile.mkstemp(prefix=".gridy-", suffix=".tmp", dir=folder)
        temp = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            kwargs = {"icc_profile": SRGB_BYTES}
            if options.format == "JPEG":
                kwargs.update(quality=JPEG_QUALITY, subsampling=0)
            canvas.save(stream, format=options.format, **kwargs)
            stream.flush()
            os.fsync(stream.fileno())
        verify_output(temp, options)
        stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
        stem = f"Gridy_{stamp}_{len(sources)}장"
        suffix = ".jpg" if options.format == "JPEG" else ".png"
        for number in range(10000):
            tail = f"_{number:03d}" if number else ""
            destination = folder / f"{stem}{tail}{suffix}"
            try:
                _publish(temp, destination)
                return destination
            except FileExistsError:
                continue
        raise GridyError("사용 가능한 파일명을 찾을 수 없습니다.")
    except OSError as exc:
        raise GridyError(f"저장하지 못했습니다. 폴더 권한과 여유 공간을 확인하세요.\n{folder}\n{exc}") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)

