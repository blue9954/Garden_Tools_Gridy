from pathlib import Path
import logging

from PIL import Image
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool, QTimer, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImage, QPainter, QPixmap, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog, QColorDialog,
    QSlider, QSpinBox, QComboBox, QLineEdit, QScrollArea, QSizePolicy,
)

from . import __version__
from .config import GridyError, Options, PRESETS
from .export import save_collage
from .images import Source, import_batch, source_anchor
from .render import compose
from .preferences import load_options, preferences_path, save_options

LOG = logging.getLogger(__name__)

STYLE = """
QWidget { color: #293B32; font-family: 'Malgun Gothic'; font-size: 12px; }
QMainWindow, QWidget#root { background: #F5F5F0; }
QFrame#panel { background: #FFFFFF; border: 1px solid #E1E6DE; border-radius: 14px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 26px; font-weight: 700; letter-spacing: -1px; }
QLabel#eyebrow { font-size: 10px; font-weight: 700; color: #698274; }
QLabel#title { font-size: 15px; font-weight: 700; }
QLabel#muted { color: #738076; }
QLabel#badge { background: #E8EFE7; color: #41634E; border-radius: 10px; padding: 5px 12px; }
QPushButton { background: #FFFFFF; border: 1px solid #D6DFD5; border-radius: 8px; padding: 9px 12px; }
QPushButton:hover { background: #F0F5ED; border-color: #8BA18C; }
QPushButton:pressed { background: #E3EBE0; }
QPushButton:disabled { color: #9FA9A0; background: #F1F3EE; border-color: #E1E5DD; }
QPushButton#primary { background: #2E5940; color: white; border: none; font-weight: 700; padding: 13px; }
QPushButton#primary:hover { background: #3C6C4F; }
QPushButton#primary:disabled { background: #DCE4D8; color: #879782; }
QPushButton#quiet { border: none; color: #6E7D70; background: transparent; }
QPushButton#quiet:hover { background: #F0F5ED; }
QComboBox, QSpinBox, QLineEdit { border: 1px solid #D9E0D6; background: #FAFBF8; border-radius: 7px; padding: 8px; selection-background-color: #51765B; }
QComboBox { padding-right: 22px; min-height: 20px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #E7EFE2; selection-color: #25432F; }
QSlider::groove:horizontal { height: 4px; background: #E5EADF; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #6E8C6C; border-radius: 2px; }
QSlider::handle:horizontal { background: #386046; border: 3px solid white; width: 14px; height: 14px; margin: -8px 0; border-radius: 10px; }
QListWidget { background: #FFFFFF; border: none; outline: none; }
QListWidget::item { padding: 10px 4px; margin: 3px 0; border: 1px solid #E8ECE4; border-radius: 9px; }
QListWidget::item:selected { color: #244631; background: #EDF3E8; border: 1px solid #9CB294; }
QListWidget::item:hover { background: #F5F8F1; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 7px; background: transparent; }
QScrollBar::handle:vertical { background: #CCD7C8; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def pixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    qimage = QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4,
                    QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def app_icon() -> QIcon:
    return QIcon(str(Path(__file__).resolve().parent / "assets" / "app-icon.png"))


class WorkerSignals(QObject):
    done = Signal(int, str, object, str)


class Worker(QRunnable):
    def __init__(self, revision, kind, function):
        super().__init__()
        self.revision, self.kind, self.function = revision, kind, function
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.done.emit(self.revision, self.kind, self.function(), "")
        except Exception as exc:
            LOG.exception("%s failed", self.kind)
            message = str(exc) if isinstance(exc, GridyError) else f"처리하지 못했습니다.\n{exc}"
            self.signals.done.emit(self.revision, self.kind, None, message)


class PhotoList(QListWidget):
    filesDropped = Signal(list)
    reordered = Signal()

    def __init__(self):
        super().__init__()
        self.setIconSize(QSize(76, 62))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setWordWrap(False)
        self.setAccessibleName("사진 목록")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if all(url.isLocalFile() for url in urls):
                self.filesDropped.emit([url.toLocalFile() for url in urls])
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            super().dropEvent(event)
            self.reordered.emit()


class Preview(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.setMinimumSize(300, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor("#E1E6DD"), 1))
        p.setBrush(QColor("#EAEDE5"))
        p.drawRoundedRect(area, 14, 14)
        if self.image is not None:
            target = self.image.size().scaled(self.size() - QSize(52, 52), Qt.AspectRatioMode.KeepAspectRatio)
            x, y = (self.width() - target.width()) // 2, (self.height() - target.height()) // 2
            p.fillRect(x + 4, y + 6, target.width(), target.height(), QColor("#D7DDD2"))
            p.drawPixmap(x, y, target.width(), target.height(), self.image)
        else:
            w = min(260, self.width() - 80)
            h = int(w * 1.25)
            x, y = (self.width() - w) // 2, (self.height() - h) // 2 - 26
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FCFCF8"))
            p.drawRoundedRect(x, y, w, h, 3, 3)
            p.setBrush(QColor("#E2E9D9"))
            margin, gap = 18, 10
            row_h = (h - margin * 2 - gap * 2) // 3
            for i in range(3):
                p.drawRect(x + margin, y + margin + i * (row_h + gap), w - 2 * margin, row_h)
            p.setPen(QColor("#6D7C69"))
            p.drawText(x - 20, y + h + 25, w + 40, 30, Qt.AlignmentFlag.AlignCenter, "사진을 넣으면 여기에 미리보기가 나타납니다")
        p.end()


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    result.setWordWrap(True)
    return result


class MainWindow(QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__()
        self.settings_path = Path(settings_path) if settings_path is not None else preferences_path()
        self._saved_options = load_options(self.settings_path)
        self._applying_options = False
        self.sources: list[Source] = []
        self.revision = 0
        self.preview_revision = -1
        self.rendering = False
        self.busy = False
        self.result_path = None
        self.jobs = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._start_preview)
        self.setWindowTitle(f"Garden Tools Gridy  {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1260, 830)
        self.setMinimumSize(1080, 740)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        self._build()
        self._apply_options(self._saved_options)
        self._sync()

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 18)
        outer.setSpacing(18)
        header = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(self.windowIcon().pixmap(44, 44))
        header.addWidget(mark)
        name = QVBoxLayout()
        name.setSpacing(0)
        name.addWidget(label("GARDEN TOOLS", "eyebrow"))
        name.addWidget(label("Gridy", "brand"))
        header.addLayout(name)
        header.addSpacing(20)
        tagline = label("사진 사이에, 여유를 더하세요.", "muted")
        tagline.setWordWrap(False)
        header.addWidget(tagline)
        header.addStretch()
        header.addWidget(label("로컬에서 안전하게", "badge"))
        outer.addLayout(header)
        columns = QHBoxLayout()
        columns.setSpacing(18)
        outer.addLayout(columns, 1)

        self.left, left = self._panel(254)
        columns.addWidget(self.left)
        line = QHBoxLayout()
        line.addWidget(label("01  사진", "title"))
        line.addStretch()
        self.count = label("0 / 3", "muted")
        line.addWidget(self.count)
        left.addLayout(line)
        left.addWidget(label("사진 2~3장을 여기에 끌어 놓으세요", "muted"))
        self.add_button = QPushButton("＋  사진 추가")
        self.add_button.clicked.connect(self.choose_files)
        left.addWidget(self.add_button)
        self.photo_list = PhotoList()
        self.photo_list.filesDropped.connect(self.add_files)
        self.photo_list.reordered.connect(self._reordered)
        self.photo_list.currentRowChanged.connect(lambda _: self._sync())
        left.addWidget(self.photo_list, 1)
        actions = QHBoxLayout()
        self.up_button = QPushButton("↑")
        self.up_button.setAccessibleName("사진 위로")
        self.down_button = QPushButton("↓")
        self.down_button.setAccessibleName("사진 아래로")
        self.remove_button = QPushButton("제거")
        self.up_button.clicked.connect(lambda: self.move_photo(-1))
        self.down_button.clicked.connect(lambda: self.move_photo(1))
        self.remove_button.clicked.connect(self.remove_photo)
        for button in [self.up_button, self.down_button, self.remove_button]:
            actions.addWidget(button)
        left.addLayout(actions)
        clear = QPushButton("사진 모두 비우기")
        clear.setObjectName("quiet")
        clear.clicked.connect(self.clear_photos)
        left.addWidget(clear)
        left.addWidget(label("JPG · PNG\n최대 100MB / 60MP · 원본 보존", "muted"))

        center = QVBoxLayout()
        center.setSpacing(10)
        line = QHBoxLayout()
        line.addWidget(label("02  미리보기", "title"))
        line.addStretch()
        self.size_label = label("1080 × 1350 px", "muted")
        line.addWidget(self.size_label)
        center.addLayout(line)
        self.preview = Preview()
        center.addWidget(self.preview, 1)
        self.preview_hint = label("사진은 위에서 아래 순서로 배치됩니다.", "muted")
        self.preview_hint.setMinimumHeight(38)
        center.addWidget(self.preview_hint)
        columns.addLayout(center, 1)

        self.right, right = self._panel(290)
        columns.addWidget(self.right)
        right.addWidget(label("03  여백과 출력", "title"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings = QWidget()
        settings.setStyleSheet("background: transparent;")
        form = QVBoxLayout(settings)
        form.setContentsMargins(0, 0, 5, 0)
        form.setSpacing(13)
        self.margin = self._spacing_control(form, "바깥 여백", 40)
        self.gap = self._spacing_control(form, "사진 사이 간격", 20)
        form.addWidget(label("여백 색상"))
        color_row = QHBoxLayout()
        self.color_button = QPushButton()
        self.color_button.setFixedWidth(42)
        self.color_button.setAccessibleName("여백 색상 선택")
        self.color_button.clicked.connect(self.choose_color)
        self.color_text = QLineEdit("#FFFFFF")
        self.color_text.setMaxLength(7)
        self.color_text.setAccessibleName("여백 색상 HEX")
        self.color_text.textChanged.connect(self.invalidate)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.color_text)
        form.addLayout(color_row)
        form.addWidget(label("사진 맞춤"))
        self.fit = QComboBox()
        self.fit.addItem("전체 보이기", "contain")
        self.fit.addItem("영역 채우기", "cover")
        self.fit.currentIndexChanged.connect(self.invalidate)
        form.addWidget(self.fit)
        self.fit_hint = label("사진 전체를 유지합니다. 비율에 따라 추가 여백이 생깁니다.", "muted")
        form.addWidget(self.fit_hint)
        form.addWidget(label("출력 크기"))
        self.preset = QComboBox()
        self.preset.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.preset.setMinimumContentsLength(15)
        for name, size in PRESETS.items():
            self.preset.addItem(name, size)
        self.preset.currentIndexChanged.connect(self.invalidate)
        form.addWidget(self.preset)
        form.addWidget(label("파일 형식"))
        self.file_format = QComboBox()
        self.file_format.addItem("JPG · 고화질", "JPEG")
        self.file_format.addItem("PNG · 무손실", "PNG")
        self.file_format.currentIndexChanged.connect(self.invalidate)
        form.addWidget(self.file_format)
        reset = QPushButton("설정 초기화")
        reset.setObjectName("quiet")
        reset.clicked.connect(self.reset_options)
        form.addWidget(reset)
        form.addStretch()
        scroll.setWidget(settings)
        right.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        details = QVBoxLayout()
        details.setSpacing(5)
        self.path_label = label("저장 위치  ·  사진을 추가하면 표시됩니다", "muted")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setMinimumWidth(0)
        self.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        details.addWidget(self.path_label)
        self.status = label("사진 2~3장으로 첫 콜라주를 만들어 보세요.")
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        details.addWidget(self.status)
        bottom.addLayout(details, 1)
        self.open_result = QPushButton("결과 열기")
        self.open_folder = QPushButton("폴더 열기")
        self.open_result.clicked.connect(lambda: self._open(False))
        self.open_folder.clicked.connect(lambda: self._open(True))
        bottom.addWidget(self.open_result)
        bottom.addWidget(self.open_folder)
        self.save_button = QPushButton("이미지 저장")
        self.save_button.setObjectName("primary")
        self.save_button.setMinimumWidth(170)
        self.save_button.clicked.connect(self.save)
        bottom.addWidget(self.save_button)
        outer.addLayout(bottom)

    @staticmethod
    def _panel(width):
        frame = QFrame()
        frame.setObjectName("panel")
        frame.setFixedWidth(width)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(17, 19, 17, 16)
        layout.setSpacing(14)
        return frame, layout

    def _spacing_control(self, layout, title, value):
        row = QHBoxLayout()
        row.addWidget(label(title))
        row.addStretch()
        spin = QSpinBox()
        spin.setRange(0, 200)
        spin.setSuffix(" px")
        spin.setValue(value)
        spin.setFixedWidth(95)
        spin.setAccessibleName(title)
        row.addWidget(spin)
        layout.addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 200)
        slider.setValue(value)
        slider.setAccessibleName(title + " 슬라이더")
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        spin.valueChanged.connect(self.invalidate)
        layout.addWidget(slider)
        return spin

    def options(self):
        width, height = self.preset.currentData()
        options = Options(width, height, self.margin.value(), self.gap.value(),
                          self.color_text.text().upper(), self.fit.currentData(), self.file_format.currentData())
        options.validate()
        return options

    def message(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet("color: #A13D2D;" if error else "color: #48604D;")

    def _sync(self):
        self.count.setText(f"{len(self.sources)} / 3")
        selected = self.photo_list.currentRow()
        self.left.setEnabled(not self.busy)
        self.right.setEnabled(not self.busy)
        self.up_button.setEnabled(selected > 0)
        self.down_button.setEnabled(0 <= selected < len(self.sources) - 1)
        self.remove_button.setEnabled(selected >= 0)
        self.save_button.setEnabled(not self.busy and 2 <= len(self.sources) <= 3
                                    and self.preview_revision == self.revision)
        self.open_result.setVisible(self.result_path is not None)
        self.open_folder.setVisible(self.result_path is not None)
        if self.sources:
            anchor = source_anchor(self.sources)
            text = f"저장 위치  ·  {anchor.path.parent}"
            if len({s.path.parent for s in self.sources}) > 1:
                text += f"  (기준: {anchor.path.name})"
            self.path_label.setText(text)
            self.path_label.setToolTip(text)
        else:
            self.path_label.setText("저장 위치  ·  사진을 추가하면 표시됩니다")

    def _list_refresh(self, selected=0):
        self.photo_list.blockSignals(True)
        self.photo_list.clear()
        for i, source in enumerate(self.sources):
            thumbnail = pixmap(source.preview)
            icon = QIcon(thumbnail)
            # Qt tints the generated Selected icon with the system accent.
            # Photo content must keep its original color when selected.
            icon.addPixmap(thumbnail, QIcon.Mode.Selected)
            icon.addPixmap(thumbnail, QIcon.Mode.Active)
            item = QListWidgetItem(icon,
                                   f"{i + 1}  {source.path.name}\n{source.size[0]} × {source.size[1]}")
            item.setData(Qt.ItemDataRole.UserRole, str(source.path))
            item.setToolTip(str(source.path))
            item.setSizeHint(QSize(204, 92))
            self.photo_list.addItem(item)
        self.photo_list.setCurrentRow(min(selected, len(self.sources) - 1))
        self.photo_list.blockSignals(False)
        self._sync()

    def _submit(self, kind, function, revision=None):
        job = Worker(self.revision if revision is None else revision, kind, function)
        self.jobs.add(job)
        job.signals.done.connect(self._done)
        job.signals.done.connect(lambda *args, retained=job: self.jobs.discard(retained))
        self.pool.start(job)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "사진 2~3장 선택", "", "사진 (*.jpg *.jpeg *.png)")
        if paths:
            self.add_files(paths)

    def add_files(self, paths):
        if self.busy or not paths:
            return
        self.busy = True
        self.message("사진을 읽고 있습니다…")
        self._sync()
        existing = self.sources.copy()
        self._submit("import", lambda: import_batch(paths, existing))

    def invalidate(self, *_):
        if self._applying_options:
            return
        self.revision += 1
        self.preview_revision = -1
        self.result_path = None
        self.fit_hint.setText("사진 가장자리가 잘릴 수 있습니다." if self.fit.currentData() == "cover"
                              else "사진 전체를 유지합니다. 비율에 따라 추가 여백이 생깁니다.")
        try:
            options = self.options()
            self.color_button.setStyleSheet(f"background: {options.background}; border: 1px solid #B6C3B0;")
            self.size_label.setText(f"{options.width} × {options.height} px")
            self.message("미리보기를 갱신하고 있습니다…" if self.sources else "사진 2~3장을 추가하세요.")
            self.timer.start()
            if options != self._saved_options:
                try:
                    save_options(self.settings_path, options)
                    self._saved_options = options
                except OSError:
                    LOG.exception("Could not save output settings")
                    self.message("설정을 기록하지 못했습니다. 다음 실행에는 이전 설정이 사용됩니다.", True)
        except GridyError as exc:
            self.message(str(exc), True)
            self.timer.stop()
        self._sync()

    def _start_preview(self):
        if self.rendering or self.busy:
            return
        if not self.sources:
            self.preview.image = None
            self.preview.update()
            self.preview_hint.setText("사진은 위에서 아래 순서로 배치됩니다.")
            return
        try:
            options = self.options()
        except GridyError:
            return
        sources = self.sources.copy()
        self.rendering = True
        self._submit("preview", lambda: compose(sources, options))

    def _done(self, revision, kind, result, error):
        if kind == "preview":
            self.rendering = False
            if revision != self.revision:
                self.timer.start()
                return
            if error:
                self.message(error, True)
            else:
                image, low = result
                self.preview.image = pixmap(image)
                self.preview.update()
                self.preview_revision = revision
                self.preview_hint.setText("원본 해상도가 낮아 선명도가 떨어질 수 있습니다: " + ", ".join(low)
                                          if low else "현재 미리보기의 배치와 여백으로 저장됩니다.")
                if not self.busy:
                    self.message("저장할 준비가 되었습니다." if len(self.sources) >= 2 else "사진을 한 장 더 추가하세요.")
        else:
            self.busy = False
            self.save_button.setText("이미지 저장")
            if error:
                self.message(error, True)
                if kind == "save":
                    self.preview_hint.setText("저장 실패: 원본 위치·변경 여부와 폴더 권한을 확인하세요.")
            elif kind == "import":
                added, duplicates = result
                self.sources.extend(added)
                self._list_refresh()
                self.invalidate()
                if duplicates:
                    self.message(f"중복 사진 {duplicates}장은 건너뛰었습니다.")
            elif kind == "save":
                self.result_path = result
                self.message(f"저장 완료  ·  {result.name}")
                self.path_label.setToolTip(str(result))
            if self.preview_revision != self.revision:
                self.timer.start()
        self._sync()

    def _reordered(self):
        by_path = {str(source.path): source for source in self.sources}
        self.sources = [by_path[self.photo_list.item(i).data(Qt.ItemDataRole.UserRole)]
                        for i in range(self.photo_list.count())]
        self._list_refresh(self.photo_list.currentRow())
        self.invalidate()

    def move_photo(self, direction):
        index = self.photo_list.currentRow()
        target = index + direction
        if not self.busy and 0 <= index < len(self.sources) and 0 <= target < len(self.sources):
            self.sources[index], self.sources[target] = self.sources[target], self.sources[index]
            self._list_refresh(target)
            self.invalidate()

    def remove_photo(self):
        index = self.photo_list.currentRow()
        if not self.busy and 0 <= index < len(self.sources):
            self.sources.pop(index)
            self._list_refresh(index)
            self.invalidate()

    def clear_photos(self):
        if not self.busy:
            self.sources.clear()
            self._list_refresh()
            self.invalidate()

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_text.text()), self, "여백 색상")
        if color.isValid():
            self.color_text.setText(color.name().upper())

    def reset_options(self):
        self._apply_options(Options())

    def _apply_options(self, options):
        # Keep slider synchronization, but avoid saving intermediate combinations.
        self._applying_options = True
        try:
            self.margin.setValue(options.margin)
            self.gap.setValue(options.gap)
            self.color_text.setText(options.background)
            self.fit.setCurrentIndex(self.fit.findData(options.fit))
            self.preset.setCurrentIndex(list(PRESETS.values()).index((options.width, options.height)))
            self.file_format.setCurrentIndex(self.file_format.findData(options.format))
        finally:
            self._applying_options = False
        self.invalidate()

    def save(self):
        if self.busy or len(self.sources) < 2 or self.preview_revision != self.revision:
            return
        try:
            options = self.options()
        except GridyError as exc:
            self.message(str(exc), True)
            return
        self.busy = True
        self.result_path = None
        self.save_button.setText("저장 중…")
        self.message("원본을 확인하고 이미지를 저장합니다…")
        self._sync()
        sources = self.sources.copy()
        self._submit("save", lambda: save_collage(sources, options))

    def _open(self, folder):
        if self.result_path:
            path = self.result_path.parent if folder else self.result_path
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                self.message(f"파일을 열지 못했습니다. 직접 확인하세요.\n{path}", True)

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            self.add_files([u.toLocalFile() for u in event.mimeData().urls()])
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy:
            self.message("현재 처리를 마친 뒤 창을 닫아 주세요.")
            event.ignore()
        else:
            self.timer.stop()
            self.pool.waitForDone()
            event.accept()

