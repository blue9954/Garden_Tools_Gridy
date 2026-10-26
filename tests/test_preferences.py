from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

from gridy.config import Options
from gridy.preferences import load_options, save_options


def test_settings_round_trip_and_reset(tmp_path):
    path = tmp_path / "설정 폴더" / "settings.json"
    assert load_options(path) == Options()
    options = Options(height=1080, margin=0, gap=200, background="#123ABC", fit="cover", format="PNG")
    save_options(path, options)
    assert load_options(path) == options
    save_options(path, Options())
    assert load_options(path) == Options()
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("content", ['{', 'null', '[]', '{"margin":true}', '{"gap":201}',
                                    '{"background":null}', '{"height":99}', '{"format":"GIF"}'])
def test_bad_settings_fall_back(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    assert load_options(path) == Options()
    assert path.read_text(encoding="utf-8") == content


def test_failed_replace_preserves_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_options(path, Options())

    def denied(*args):
        raise PermissionError("test write failure")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        save_options(path, replace(Options(), margin=90))
    assert load_options(path) == Options()
    assert list(tmp_path.iterdir()) == [path]


def test_ui_settings_survive_process_restart(tmp_path):
    script = '''
import sys
from PySide6.QtWidgets import QApplication
from gridy.ui import MainWindow
from gridy.config import Options
app = QApplication([])
window = MainWindow(settings_path=sys.argv[1])
expected = Options(height=1080, margin=17, gap=31, background="#123ABC", fit="cover", format="PNG")
if sys.argv[2] == "write":
    window.margin.setValue(17)
    window.gap.setValue(31)
    window.color_text.setText("#123abc")
    window.fit.setCurrentIndex(1)
    window.preset.setCurrentIndex(2)
    window.file_format.setCurrentIndex(1)
assert window.options() == expected
assert not window.sources
if sys.argv[2] == "write":
    window.color_text.setText("#BAD")
window.close()
'''
    for mode in ("write", "read"):
        subprocess.run([sys.executable, "-c", script, str(tmp_path / "settings.json"), mode],
                       cwd=Path(__file__).resolve().parents[1],
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, timeout=30)
