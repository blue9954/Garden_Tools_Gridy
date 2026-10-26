"""Run a five-pass reproducible 24 MP JPEG processing benchmark."""
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter
import json
import platform
import random

from PIL import Image

from gridy.config import Options
from gridy.images import import_batch
from gridy.render import compose
from gridy.export import save_collage


def main():
    folder = Path("artifacts/benchmark").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    paths = []
    for i in range(3):
        texture = Image.frombytes("RGB", (600, 400), rng.randbytes(600 * 400 * 3))
        image = texture.resize((6000, 4000), Image.Resampling.BILINEAR)
        path = folder / f"source-{i + 1}.jpg"
        image.save(path, quality=95)
        paths.append(str(path))
    timings = {"initial_preview": [], "option_preview": [], "save_and_reopen": []}
    for _ in range(5):
        start = perf_counter()
        sources, _ = import_batch(paths, [])
        compose(sources, Options())
        timings["initial_preview"].append(perf_counter() - start)
        start = perf_counter()
        compose(sources, replace(Options(), margin=60, gap=35))
        timings["option_preview"].append(perf_counter() - start)
        start = perf_counter()
        save_collage(sources, Options())
        timings["save_and_reopen"].append(perf_counter() - start)
    limits = {"initial_preview": 3, "option_preview": .3, "save_and_reopen": 5}
    report = {"schema_version": 1, "date": datetime.now().astimezone().isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "fixture": "3 seeded synthetic JPEG images, 6000x4000 each; warm filesystem cache; UI scheduling excluded",
              "seed": 42, "checks": {key: {"runs_seconds": values,
                  "median_seconds": median(values), "limit_seconds": limits[key],
                  "status": "PASS" if median(values) <= limits[key] else "FAIL"}
                  for key, values in timings.items()},
              "inputs": [{"path": p, "sha256": sha256(Path(p).read_bytes()).hexdigest()} for p in paths]}
    (folder / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["checks"], indent=2))


if __name__ == "__main__":
    main()

