from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QListWidget, QProgressBar, QLabel, QGridLayout
)
from utils.file_handler import FileHandler
from core.video_processor import VideoProcessor
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TeslaDashcam")
        self.setMinimumSize(800, 600)
        self.file_handler = FileHandler()
        self.video_processor = VideoProcessor()
        self.input_dir: Path | None = None
        self.conversion_count = 0
        self.completed_cameras: set[str] = set()
        self.missing_cameras: set[str] = set()
        self.current_timestamp: str | None = None
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Input directory selection
        dir_layout = QHBoxLayout()
        self.dir_button = QPushButton("Select Input Directory")
        dir_layout.addWidget(self.dir_button)
        main_layout.addLayout(dir_layout)

        # File list
        self.file_list = QListWidget()
        main_layout.addWidget(self.file_list)

        # Convert button
        self.convert_button = QPushButton("Convert")
        self.convert_button.setEnabled(False)
        main_layout.addWidget(self.convert_button)

        # Status display
        self.status_layout = QGridLayout()
        self.file_labels = []
        self.progress_bars = []
        self.progress_labels = []
        cameras = ["back", "front", "left_repeater", "right_repeater"]
        for row, camera in enumerate(cameras):
            # File name label
            file_label = QLabel(f"{camera}: Idle")
            self.file_labels.append(file_label)
            self.status_layout.addWidget(file_label, row, 0)
            # Progress bar
            progress_bar = QProgressBar()
            progress_bar.setValue(0)
            self.progress_bars.append(progress_bar)
            self.status_layout.addWidget(progress_bar, row, 1)
            # Progress percentage label
            progress_label = QLabel("0%")
            self.progress_labels.append(progress_label)
            self.status_layout.addWidget(progress_label, row, 2)
        main_layout.addLayout(self.status_layout)

    def connect_signals(self):
        self.dir_button.clicked.connect(self.select_directory)
        self.file_list.itemSelectionChanged.connect(self.update_convert_button)
        self.convert_button.clicked.connect(self.start_conversion)
        self.video_processor.progress_updated.connect(self.update_progress)
        self.video_processor.conversion_finished.connect(self.on_conversion_finished)
        self.video_processor.missing_file_detected.connect(self.on_missing_file)

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            self.input_dir = Path(dir_path)
            self.current_timestamp = None
            self.reset_status()
            self.populate_file_list()

    def populate_file_list(self):
        self.file_list.clear()
        if not self.input_dir:
            return
        timestamps = self.file_handler.get_timestamp_groups(self.input_dir)
        for timestamp in sorted(timestamps):
            self.file_list.addItem(timestamp)

    def update_convert_button(self):
        selected = bool(self.file_list.selectedItems())
        self.convert_button.setEnabled(selected)
        if selected:
            self.current_timestamp = self.file_list.selectedItems()[0].text()
            self.reset_status()

    def start_conversion(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        timestamp = selected_items[0].text()
        self.current_timestamp = timestamp
        self.conversion_count = 0
        self.completed_cameras.clear()
        self.missing_cameras.clear()
        self.reset_status()
        for label, bar, progress_label, cam in zip(
            self.file_labels, self.progress_bars, self.progress_labels,
            ["back", "front", "left_repeater", "right_repeater"]
        ):
            label.setText(f"{timestamp}-{cam}.mp4: Processing")
            bar.setValue(0)
            progress_label.setText("0%")
        if self.input_dir:
            self.convert_button.setEnabled(False)
            self.file_list.setEnabled(False)
            self.video_processor.process_videos(self.input_dir, timestamp)

    def reset_status(self):
        """Reset all file labels, progress bars, and percentage labels to initial state."""
        for label, bar, progress_label, cam in zip(
            self.file_labels, self.progress_bars, self.progress_labels,
            ["back", "front", "left_repeater", "right_repeater"]
        ):
            if self.current_timestamp:
                label.setText(f"{self.current_timestamp}-{cam}.mp4: Idle")
            else:
                label.setText(f"{cam}: Idle")
            bar.setValue(0)
            progress_label.setText("0%")
        self.conversion_count = 0
        self.completed_cameras.clear()
        self.missing_cameras.clear()

    def update_progress(self, camera: str, progress: int):
        if camera in self.missing_cameras:
            return  # Skip updates for missing files
        for label, bar, progress_label, cam in zip(
            self.file_labels, self.progress_bars, self.progress_labels,
            ["back", "front", "left_repeater", "right_repeater"]
        ):
            if cam == camera:
                bar.setValue(progress)
                progress_label.setText(f"{progress}%")
                if progress == 100:
                    label.setText(f"{self.current_timestamp}-{cam}.mp4: Completed")
                elif progress > 0:
                    label.setText(f"{self.current_timestamp}-{cam}.mp4: Processing")

    def on_conversion_finished(self, camera: str):
        if camera not in self.completed_cameras and camera not in self.missing_cameras:
            self.completed_cameras.add(camera)
            self.conversion_count += 1
            if self.conversion_count >= (4 - len(self.missing_cameras)):
                self.convert_button.setEnabled(True)
                self.file_list.setEnabled(True)
                self.conversion_count = 0
                logger.info("All conversions completed")

    def on_missing_file(self, camera: str):
        if camera not in self.missing_cameras:
            self.missing_cameras.add(camera)
            for label, bar, progress_label, cam in zip(
                self.file_labels, self.progress_bars, self.progress_labels,
                ["back", "front", "left_repeater", "right_repeater"]
            ):
                if cam == camera:
                    label.setText(f"{self.current_timestamp}-{cam}.mp4: Missing")
                    bar.setValue(0)
                    progress_label.setText("0%")
