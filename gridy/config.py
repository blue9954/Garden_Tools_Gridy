from dataclasses import dataclass
import re

MAX_IMAGES = 3
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 60_000_000
PREVIEW_LONG_EDGE = 2160
JPEG_QUALITY = 95
PRESETS = {
    "세로 4:5 · 1080 × 1350": (1080, 1350),
    "세로 3:4 · 1080 × 1440": (1080, 1440),
    "정사각형 · 1080 × 1080": (1080, 1080),
}


class GridyError(Exception):
    """An actionable error safe to display to the user."""


@dataclass(frozen=True)
class Options:
    width: int = 1080
    height: int = 1350
    margin: int = 40
    gap: int = 20
    background: str = "#FFFFFF"
    fit: str = "contain"
    format: str = "JPEG"

    def validate(self) -> None:
        if (self.width, self.height) not in PRESETS.values():
            raise GridyError("지원하지 않는 출력 크기입니다.")
        if any(type(v) is not int or not 0 <= v <= 200 for v in (self.margin, self.gap)):
            raise GridyError("여백은 0~200 사이의 정수여야 합니다.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.background):
            raise GridyError("색상을 #RRGGBB 형식으로 입력하세요. 예: #FFFFFF")
        if self.fit not in {"contain", "cover"} or self.format not in {"JPEG", "PNG"}:
            raise GridyError("지원하지 않는 맞춤 방식 또는 저장 형식입니다.")

