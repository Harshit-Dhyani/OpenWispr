"""Main window UI for desktop application.

Provides the primary Qt-based main window interface for OpenWispr,
including session management, transcript display, audio device controls,
and settings configuration.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AudioDeviceInfo, SessionHealth, SessionState, TranscriptSegment
from app.core.session_manager import SessionManager
from app.core.settings.config import AppSettings


class MainWindow(QMainWindow):
    def __init__(self, *, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.manager = SessionManager(settings)
        self.manager.set_callbacks(
            on_segment=self.on_segment,
            on_health=self.on_health,
            on_state=self.on_state,
        )
        self.current_output_root = settings.export_root
        self.setWindowTitle(settings.app_name)
        self.resize(1100, 760)
        self._build_ui()
        self._load_devices()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self._refresh_devices_if_idle)
        self.refresh_timer.start()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        form = QFormLayout()
        self.title_input = QLineEdit("Study Session")
        form.addRow("Session Title", self.title_input)

        self.device_combo = QComboBox()
        form.addRow("Audio Device", self.device_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.model_combo.setCurrentText(self.settings.default_model)
        form.addRow("Whisper Model", self.model_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["auto", "hi", "en"])
        self.language_combo.setCurrentText(self.settings.default_language)
        form.addRow("Language Mode", self.language_combo)

        self.live_mode_combo = QComboBox()
        self.live_mode_combo.addItems(["low_latency", "balanced", "high_accuracy"])
        self.live_mode_combo.setCurrentText(self.settings.default_live_mode)
        form.addRow("Live Mode", self.live_mode_combo)

        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.addItems(["auto", "gpu_only", "cpu_only"])
        self.execution_mode_combo.setCurrentText(self.settings.default_execution_mode)
        form.addRow("Execution Mode", self.execution_mode_combo)

        export_row = QHBoxLayout()
        self.export_label = QLabel(str(self.current_output_root))
        self.export_button = QPushButton("Choose Folder")
        self.export_button.clicked.connect(self.choose_export_folder)
        export_row.addWidget(self.export_label, stretch=1)
        export_row.addWidget(self.export_button)
        export_widget = QWidget()
        export_widget.setLayout(export_row)
        form.addRow("Export Root", export_widget)
        layout.addLayout(form)

        meter_row = QHBoxLayout()
        self.level_meter = QProgressBar()
        self.level_meter.setRange(0, 100)
        self.status_label = QLabel("Idle")
        meter_row.addWidget(QLabel("Signal"))
        meter_row.addWidget(self.level_meter, stretch=1)
        meter_row.addWidget(self.status_label)
        layout.addLayout(meter_row)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.start_session)
        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)
        self.attach_pdf_button = QPushButton("Attach PDF")
        self.attach_pdf_button.clicked.connect(self.attach_pdf)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.attach_pdf_button)
        layout.addLayout(button_row)

        self.tabs = QTabWidget()
        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        self.review_list = QListWidget()
        self.health_view = QPlainTextEdit()
        self.health_view.setReadOnly(True)
        self.tabs.addTab(self.transcript_view, "Live Transcript")
        self.tabs.addTab(self.review_list, "Needs Review")
        self.tabs.addTab(self.health_view, "Health")
        layout.addWidget(self.tabs, stretch=1)

    def _load_devices(self) -> None:
        self.device_combo.clear()
        for device in self.manager.list_devices():
            label = device.name if not device.is_loopback else f"{device.name} [recommended]"
            self.device_combo.addItem(label, userData=device)

    def _refresh_devices_if_idle(self) -> None:
        if not self.stop_button.isEnabled():
            self._load_devices()

    def choose_export_folder(self) -> None:
        base_dir = self.current_output_root
        if not base_dir.exists():
            base_dir = Path.cwd()

        dialog = QFileDialog(self, "Choose export folder", str(base_dir))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        # Native Windows folder dialogs can crash on some systems because of shell extensions.
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        self.refresh_timer.stop()
        try:
            if dialog.exec():
                selected = dialog.selectedFiles()
                if selected:
                    self.current_output_root = Path(selected[0])
                    self.export_label.setText(str(self.current_output_root))
        except Exception as exc:
            QMessageBox.critical(self, "Folder picker failed", str(exc))
        finally:
            self.refresh_timer.start()

    def start_session(self) -> None:
        device = self.device_combo.currentData()
        try:
            session = self.manager.start_session(
                title=self.title_input.text().strip() or "Study Session",
                output_root=self.current_output_root,
                model_name=self.model_combo.currentText(),
                language_mode=self.language_combo.currentText(),
                device_id=device.id if isinstance(device, AudioDeviceInfo) else None,
                live_mode=self.live_mode_combo.currentText(),
                execution_mode=self.execution_mode_combo.currentText(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Unable to start session", str(exc))
            return
        self.transcript_view.clear()
        self.review_list.clear()
        self.status_label.setText(f"Running: {session.output_dir}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_session(self) -> None:
        self.manager.stop_session()
        self.status_label.setText("Stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def attach_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach PDF", "", "PDF Files (*.pdf)")
        if path:
            self.manager.attach_pdf(path)

    def on_segment(self, segment: TranscriptSegment) -> None:
        self.transcript_view.appendPlainText(
            f"[{segment.start:.2f} - {segment.end:.2f}] {segment.display_text}"
        )

    def on_health(self, health: SessionHealth, meter_value: float) -> None:
        self.level_meter.setValue(min(100, int(meter_value * 220)))
        self.health_view.setPlainText(
            "\n".join(
                [
                    f"Audio stream active: {health.audio_stream_active}",
                    f"GPU mode: {health.gpu_mode}",
                    f"Execution mode: {health.execution_mode}",
                    f"Runtime device: {health.model_runtime_device}",
                    f"Last transcript at: {health.last_transcript_at.isoformat() if health.last_transcript_at else 'n/a'}",
                    f"Dropped frames: {health.dropped_frames}",
                    f"Queue depth: {health.queue_depth}",
                    f"Dropped STT chunks: {health.dropped_stt_chunks}",
                    f"Backpressure: {health.stt_backpressure_state}",
                    f"Last warning: {health.last_warning or 'none'}",
                    f"Last error: {health.last_error or 'none'}",
                ]
            )
        )

    def on_state(self, session: SessionState) -> None:
        self.review_list.clear()
        for segment in session.needs_review:
            self.review_list.addItem(
                f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text} :: {', '.join(segment.review_reasons)}"
            )
