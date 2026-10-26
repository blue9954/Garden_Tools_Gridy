# Third party components

Garden Tools Gridy uses these components, bundled as dynamically loaded libraries in the Windows directory distribution.

- PySide6 Essentials and Qt 6.12.0: Qt for Python, available under LGPLv3/GPLv3 or commercial terms. Upstream: https://www.qt.io/qt-for-python and https://code.qt.io/pyside/pyside-setup.git/
- Shiboken6 6.12.0: Qt binding runtime, included with Qt for Python.
- Pillow 12.3.0: HPND license and bundled image libraries. Upstream: https://github.com/python-pillow/Pillow
- Python 3.14.7: Python Software Foundation License. Upstream: https://www.python.org/
- PyInstaller 6.22.3: GPL with the PyInstaller bootloader exception. Upstream: https://pyinstaller.org/

Installed component license files, GNU LGPLv3/GPLv3 texts and the Python license are copied into the distribution's `licenses` folder by `tools/build.py`. Qt/PySide6 libraries remain separate files under `_internal`; they are not statically linked into the app. The application source is provided in the project with its build instructions. The installed PySide6 wheel declares LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; its metadata also includes a separate commercial-license notice. The public PyPI release describes both open source and commercial availability: https://pypi.org/project/PySide6-Essentials/6.12.0/

Documentation consulted for implementation: [Qt for Python](https://doc.qt.io/qtforpython-6/gettingstarted.html), [Pillow ImageCms](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html), [PyInstaller](https://pyinstaller.org/en/stable/usage.html).
