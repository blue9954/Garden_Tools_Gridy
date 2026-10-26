"""Persist the last valid output options independently of imported photos."""
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import tempfile

from .config import GridyError, Options

LOG = logging.getLogger(__name__)


def preferences_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GardenTools" / "Gridy" / "settings.json"


def load_options(path: Path) -> Options:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Settings must be an object")
        defaults = asdict(Options())
        values = {key: data.get(key, value) for key, value in defaults.items()}
        if any(type(values[key]) is not type(value) for key, value in defaults.items()):
            raise ValueError("Invalid setting type")
        options = Options(**values)
        options.validate()
        return options
    except FileNotFoundError:
        return Options()
    except (OSError, ValueError, GridyError) as exc:
        LOG.warning("Could not restore settings from %s: %s", path, exc)
        return Options()


def save_options(path: Path, options: Options) -> None:
    options.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="settings-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(asdict(options), stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
