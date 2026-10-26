"""Build, smoke-test and package a new Windows release without replacing old builds."""
from datetime import datetime
from importlib.metadata import distribution
from pathlib import Path
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tomllib
import zipfile

from PIL import Image
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if version != runpy.run_path(str(root / "gridy" / "__init__.py"))["__version__"]:
        raise RuntimeError("Project version and application version must match")
    started = datetime.now().astimezone()
    build_id = f"{version}-{started:%Y%m%d-%H%M%S-%f}"
    release_dir = root / "dist" / build_id
    release_dir.mkdir(parents=True, exist_ok=False)
    output = release_dir / "GardenToolsGridy"
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(root / "build" / "pyinstaller-cache")
    icon_path = root / "build" / "gridy.ico"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_source = root / "gridy" / "assets" / "app-icon.png"
    with Image.open(icon_source) as source:
        if source.width != source.height:
            raise ValueError("The application icon must be square")
        source.convert("RGBA").save(icon_path, format="ICO",
                                    sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    version_parts = tuple(int(part) for part in version.split("."))
    if len(version_parts) != 3:
        raise ValueError("Expected MAJOR.MINOR.PATCH version")
    version_file = root / "build" / "version-info.txt"
    version_resource = VSVersionInfo(
        ffi=FixedFileInfo(filevers=version_parts + (0,), prodvers=version_parts + (0,)),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "GardenTools"),
            StringStruct("FileDescription", "Garden Tools Gridy"),
            StringStruct("FileVersion", version),
            StringStruct("InternalName", "GardenToolsGridy"),
            StringStruct("OriginalFilename", "GardenToolsGridy.exe"),
            StringStruct("ProductName", "Garden Tools Gridy"),
            StringStruct("ProductVersion", version),
        ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])])
    version_file.write_text(str(version_resource), encoding="utf-8")
    build_env = os.environ.copy()
    windows = Path(os.environ["WINDIR"])
    # Host tools (e.g. Poppler) can ship an incompatible ICU with the same DLL
    # name as Windows ICU. Do not let those PATH entries enter the distribution.
    build_env["PATH"] = os.pathsep.join(str(p) for p in (
        Path(sys.executable).parent, Path(sys.base_prefix), Path(sys.base_prefix) / "DLLs",
        windows / "System32", windows))
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--windowed", "--onedir",
                    "--icon", str(icon_path),
                    "--version-file", str(version_file),
                    "--add-data", f"{icon_source}:gridy/assets",
                    "--name", "GardenToolsGridy", "--distpath", str(release_dir),
                    "--workpath", str(root / "build" / "pyinstaller"),
                    "--specpath", str(root / "build"), str(root / "main.py")], cwd=root, env=build_env, check=True)
    for filename in ("README.md", "작업명세서.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md"):
        if (root / filename).is_file():
            shutil.copy2(root / filename, output / filename)
    license_dir = output / "licenses"
    if (root / "licenses").is_dir():
        shutil.copytree(root / "licenses", license_dir, dirs_exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        (license_dir / "Python").mkdir(parents=True, exist_ok=True)
        shutil.copy2(python_license, license_dir / "Python" / "LICENSE.txt")
    for name in ("Pillow", "PySide6-Essentials", "shiboken6"):
        dist = distribution(name)
        for file in dist.files or []:
            if "license" in str(file).lower() or "copying" in str(file).lower():
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = license_dir / name / Path(str(file))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    executable = output / "GardenToolsGridy.exe"
    evidence = root / "artifacts" / f"release-{build_id}"
    subprocess.run([str(executable), "--smoke-test", str(evidence)], cwd=root,
                   check=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
    smoke = json.loads((evidence / "smoke.json").read_text(encoding="utf-8"))
    if smoke["status"] != "PASS" or smoke["app_version"] != version:
        raise RuntimeError("The built application did not pass its smoke test")
    source_paths = [root / "main.py", root / "pyproject.toml", root / "requirements-lock.txt"]
    source_paths += sorted((root / "gridy").glob("*.py"))
    source_paths += [Path(__file__).resolve(), icon_source]
    manifest = {
        "schema_version": 1, "version": version, "build_id": build_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().astimezone().isoformat(),
        "python": sys.version.split()[0],
        "packages": {name: distribution(name).version for name in
                     ("Pillow", "PySide6-Essentials", "shiboken6", "PyInstaller")},
        "source_sha256": {p.relative_to(root).as_posix(): sha256(p) for p in source_paths},
        "executable_sha256": sha256(executable),
        "smoke_test": {"status": smoke["status"], "checks": len(smoke["checks"]),
                       "evidence": evidence.relative_to(root).as_posix()},
    }
    (output / "build-info.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_base = root / "dist" / f"GardenToolsGridy-{build_id}-win64"
    archive = Path(shutil.make_archive(str(archive_base), "zip", release_dir, output.name))
    with zipfile.ZipFile(archive) as package:
        bad_member = package.testzip()
        if bad_member:
            raise RuntimeError(f"Corrupt ZIP member: {bad_member}")
    archive.with_suffix(".zip.sha256").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="ascii")
    relative_exe = str(executable.relative_to(root))
    (root / "Gridy.cmd").write_text(
        '@echo off\nsetlocal\n'
        f'set "GRIDY_APP=%~dp0{relative_exe}"\n'
        'if exist "%GRIDY_APP%" (\n'
        '    start "" /D "%~dp0" "%GRIDY_APP%"\n'
        ') else (\n'
        '    echo Gridy build not found. See README.md for build instructions.\n'
        '    pause\n)\n', encoding="ascii")
    print(f"Built: {executable}\nZIP: {archive}\nSmoke test: PASS ({len(smoke['checks'])} checks)")


if __name__ == "__main__":
    main()
