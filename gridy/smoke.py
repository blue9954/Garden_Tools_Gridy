"""Opt-in Qt end-to-end smoke check, also callable from the frozen executable."""
from datetime import datetime
from pathlib import Path
from time import monotonic
import json
import traceback

from PIL import Image, ImageDraw
from PySide6.QtCore import QMimeData, QPoint, QPointF, QTimer, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtTest import QTest


def make_fixtures(folder: Path) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    palettes = [("#D3DED0", "#8AAB8E", "#365D45"),
                ("#E9D8BB", "#C39F73", "#775E46"),
                ("#CDDDE0", "#8FAFB6", "#395C63")]
    for i, (sky, hill, front) in enumerate(palettes, 1):
        image = Image.new("RGB", (1800, 900), sky)
        draw = ImageDraw.Draw(image)
        draw.ellipse((1320, 120, 1470, 270), fill="#FBF6DA")
        draw.polygon([(0, 730), (440, 250), (1000, 760), (1430, 410), (1800, 710), (1800, 900), (0, 900)], fill=hill)
        draw.polygon([(0, 900), (0, 800), (780, 600), (1180, 800), (1800, 570), (1800, 900)], fill=front)
        draw.text((65, 60), f"GRIDY / TEST PHOTO 0{i}", fill=front, font_size=32)
        path = folder / f"사진 {i:02d}.png"
        image.save(path)
        paths.append(str(path))
    return paths


def run_smoke(app, window, folder: Path):
    from PySide6 import __version__ as qt_version
    from . import __version__
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    started = monotonic()
    report = {"schema_version": 1, "app_version": __version__, "qt_version": qt_version,
              "started_at": datetime.now().astimezone().isoformat(), "checks": [], "status": "RUNNING"}
    phase = 0
    paths = make_fixtures(folder / "사진 원본")
    timer = QTimer(window)
    timer.setInterval(40)
    window._smoke_timer = timer

    def check(condition, text):
        if not condition:
            raise AssertionError(text)
        report["checks"].append({"name": text, "status": "PASS"})

    def tick():
        nonlocal phase
        try:
            if monotonic() - started > 30:
                raise TimeoutError(f"phase {phase}: {window.status.text()}")
            if phase == 0:
                check(not window.save_button.isEnabled(), "empty state prevents save")
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
                enter = QDragEnterEvent(QPoint(100, 100), Qt.DropAction.CopyAction, mime,
                                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(window, enter)
                check(enter.isAccepted(), "Qt local file drag accepted")
                drop = QDropEvent(QPointF(100, 100), Qt.DropAction.CopyAction, mime,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(window, drop)
                phase = 1
            elif phase == 1 and window.save_button.isEnabled():
                check(len(window.sources) == 3, "three files imported through drop event")
                window.photo_list.setCurrentRow(0)
                QTest.mouseClick(window.down_button, Qt.MouseButton.LeftButton)
                check(window.sources[0].path.name == "사진 02.png", "reorder button changes source order")
                icon = window.photo_list.item(1).icon()
                icon_size = window.photo_list.iconSize()
                normal = icon.pixmap(icon_size, QIcon.Mode.Normal).toImage()
                selected = icon.pixmap(icon_size, QIcon.Mode.Selected).toImage()
                check(normal == selected, "selected thumbnail retains original colors")
                for value in (0, 200, 80, 32):
                    window.margin.setValue(value)
                window.gap.setValue(24)
                window.color_text.setText("#EDE5D5")
                window.fit.setCurrentIndex(1)
                window.file_format.setCurrentIndex(1)
                phase = 2
            elif phase == 2 and window.save_button.isEnabled():
                from .ui import MainWindow
                reopened = MainWindow(settings_path=window.settings_path)
                check(reopened.options() == window.options(), "all output options restored in new window")
                check(not reopened.sources, "preferences do not restore photos")
                reopened.close()
                check(window.preview_revision == window.revision, "latest preview wins after rapid changes")
                check(window.options().margin == 32, "last margin applied")
                window.grab().save(str(folder / "ui-filled.png"))
                window.color_text.setText("#XX")
                check(not window.save_button.isEnabled(), "invalid color prevents stale save")
                window.color_text.setText("#EDE5D5")
                phase = 3
            elif phase == 3 and window.save_button.isEnabled():
                QTest.mouseClick(window.save_button, Qt.MouseButton.LeftButton)
                window.save()
                check(window.busy and not window.save_button.isEnabled(), "duplicate save guarded")
                phase = 4
            elif phase == 4 and not window.busy:
                check(window.result_path is not None, "GUI save finished")
                with Image.open(window.result_path) as output:
                    check(output.size == (1080, 1350), "saved dimensions")
                    check(output.getpixel((0, 0)) == (237, 229, 213), "saved background color")
                report["output"] = str(window.result_path)
                order = [s.path for s in window.sources]
                window.reset_options()
                from .config import Options
                from .preferences import load_options
                check(load_options(window.settings_path) == Options(), "reset persists default options")
                check([s.path for s in window.sources] == order, "reset retains order")
                window.photo_list.setCurrentRow(2)
                window.remove_photo()
                phase = 5
            elif phase == 5 and window.save_button.isEnabled():
                check(len(window.sources) == 2, "two-photo preview supports save")
                window.grab().save(str(folder / "ui-two-photos.png"))
                window.remove_photo()
                check(len(window.sources) == 1 and not window.save_button.isEnabled(), "one photo prevents save")
                window.clear_photos()
                phase = 6
            elif phase == 6 and not window.rendering and not window.timer.isActive():
                check(not window.sources and window.preview.image is None, "clear resets preview")
                window.grab().save(str(folder / "ui-empty.png"))
                report["status"] = "PASS"
                finish(0)
        except Exception:
            report["status"] = "FAIL"
            report["error"] = traceback.format_exc()
            finish(1)

    def finish(code):
        timer.stop()
        window.timer.stop()
        window.pool.waitForDone()
        report["elapsed_seconds"] = round(monotonic() - started, 3)
        report["finished_at"] = datetime.now().astimezone().isoformat()
        (folder / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        app.exit(code)

    timer.timeout.connect(tick)
    timer.start()
