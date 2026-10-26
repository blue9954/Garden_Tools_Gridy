import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Garden Tools Gridy")
    parser.add_argument("photos", nargs="*", help="Optional JPG/PNG paths to open")
    parser.add_argument("--smoke-test", type=Path, help="Write test fixtures and UI smoke evidence to this folder")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtCore import QTimer
    from gridy import __version__
    from gridy.ui import MainWindow, app_icon

    folder = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GardenTools" / "Gridy"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / "gridy.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s %(message)s")
    except OSError:
        logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv[:1])
    if args.smoke_test:
        # The offscreen Qt platform does not enumerate Windows fonts itself.
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("malgun.ttf", "malgunbd.ttf"):
            QFontDatabase.addApplicationFont(str(font_dir / filename))
    app.setFont(QFont("Malgun Gothic", 10))
    app.setApplicationName("Garden Tools Gridy")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("GardenTools")
    app.setWindowIcon(app_icon())
    # Smoke checks must never read or replace the user's preferences.
    window = MainWindow(settings_path=args.smoke_test / "settings.json" if args.smoke_test else None)
    window.show()
    if args.smoke_test:
        from gridy.smoke import run_smoke
        QTimer.singleShot(0, lambda: run_smoke(app, window, args.smoke_test))
    elif args.photos:
        QTimer.singleShot(0, lambda: window.add_files(args.photos))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
