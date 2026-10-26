from dataclasses import dataclass
import math

from .config import GridyError, Options


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


def rows(count: int, options: Options) -> list[Rect]:
    options.validate()
    if count not in (1, 2, 3):
        raise GridyError("사진은 최대 3장까지 배치할 수 있습니다.")
    available = options.height - 2 * options.margin - (count - 1) * options.gap
    height, remainder = divmod(available, count)
    width = options.width - 2 * options.margin
    if height < 1 or width < 1:
        raise GridyError("여백이 너무 커서 사진을 배치할 공간이 없습니다.")
    result = []
    y = options.margin
    for index in range(count):
        h = height + (index < remainder)
        result.append(Rect(options.margin, y, width, h))
        y += h + options.gap
    return result


def placement(size: tuple[int, int], rect: Rect, fit: str):
    """Return destination size, source crop box and enlargement factor.

    Cover crops in source coordinates, avoiding giant intermediate images
    for extremely narrow or wide sources.
    """
    w, h = size
    if fit == "cover":
        scale = max(rect.width / w, rect.height / h)
        crop_w, crop_h = rect.width / scale, rect.height / scale
        left, top = (w - crop_w) / 2, (h - crop_h) / 2
        return (rect.width, rect.height), (left, top, left + crop_w, top + crop_h), scale
    scale = min(rect.width / w, rect.height / h)
    dest = (max(1, math.floor(w * scale + 0.5)), max(1, math.floor(h * scale + 0.5)))
    return dest, None, scale

