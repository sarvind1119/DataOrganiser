"""Main application window for the Data Organiser GUI."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QTextEdit, QCheckBox, QComboBox, QGroupBox,
    QSplitter, QStatusBar, QMessageBox, QHeaderView, QLineEdit,
    QFrame, QSizePolicy, QApplication, QTableWidget, QTableWidgetItem,
    QScrollArea,
)

from src.core.config import AppConfig, MANIFEST_DIR
from src.core.models import FileCategory, FileInfo, FileType, OrganizeResult
from src.core.scanner import FileScanner
from src.core.organizer import FileOrganizer
from src.ui.workers import ScanWorker, ClassifyWorker, OrganizeWorker, WatcherWorker

# Color palette
COLORS = {
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "bg": "#F8FAFC",
    "card": "#FFFFFF",
    "text": "#1E293B",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
}

# Image extensions for thumbnail preview
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tiff"}

# All category values for the dropdown
ALL_CATEGORIES = [cat.value for cat in FileCategory]


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.files: list[FileInfo] = []
        self.scan_worker: ScanWorker | None = None
        self.classify_worker: ClassifyWorker | None = None
        self.organize_worker: OrganizeWorker | None = None
        self.watcher_worker: WatcherWorker | None = None

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        self.setWindowTitle("Data Organiser - Smart File Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # -- Header --
        header = self._create_header()
        main_layout.addWidget(header)

        # -- Directory Selection --
        dir_group = self._create_dir_selection()
        main_layout.addWidget(dir_group)

        # -- Main Content (Splitter: Tree + Details) --
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: File tree
        left_panel = self._create_file_tree_panel()
        splitter.addWidget(left_panel)

        # Right: Tabs (Preview, Stats, Settings, Undo, Custom Rules, Watchdog)
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([600, 400])
        main_layout.addWidget(splitter, stretch=1)

        # -- Progress Bar --
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # -- Action Buttons --
        actions = self._create_action_buttons()
        main_layout.addWidget(actions)

        # -- Status Bar --
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select a directory to begin.")

    def _create_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Data Organiser")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['primary']};")
        layout.addWidget(title)

        subtitle = QLabel("AI-Powered Smart File Organization")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(subtitle)

        layout.addStretch()

        # LLM status indicator
        self.llm_status = QLabel("LLM: Checking...")
        self.llm_status.setFont(QFont("Segoe UI", 9))
        layout.addWidget(self.llm_status)

        return header

    def _create_dir_selection(self) -> QGroupBox:
        group = QGroupBox("Directories")
        layout = QHBoxLayout(group)

        # Source directory
        layout.addWidget(QLabel("Scan:"))
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Select folder to scan...")
        self.source_input.setReadOnly(True)
        layout.addWidget(self.source_input, stretch=1)

        self.btn_browse_source = QPushButton("Browse")
        self.btn_browse_source.clicked.connect(self._browse_source)
        layout.addWidget(self.btn_browse_source)

        layout.addSpacing(20)

        # Output directory
        layout.addWidget(QLabel("Output:"))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Select output folder...")
        self.output_input.setReadOnly(True)
        layout.addWidget(self.output_input, stretch=1)

        self.btn_browse_output = QPushButton("Browse")
        self.btn_browse_output.clicked.connect(self._browse_output)
        layout.addWidget(self.btn_browse_output)

        return group

    def _create_file_tree_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row with label and export button
        header_row = QHBoxLayout()
        label = QLabel("Organized File Preview")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header_row.addWidget(label)
        header_row.addStretch()

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setFixedHeight(28)
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setEnabled(False)
        header_row.addWidget(self.btn_export)

        layout.addLayout(header_row)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Name", "Category", "Confidence", "Size"])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.itemClicked.connect(self._on_tree_item_clicked)

        header = self.file_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.file_tree)
        return panel

    def _create_right_panel(self) -> QTabWidget:
        self.tabs = QTabWidget()

        # Tab 1: File Details / Preview (with thumbnail area)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(4, 4, 4, 4)

        # Thumbnail label for image preview
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumHeight(20)
        self.thumbnail_label.setMaximumHeight(250)
        self.thumbnail_label.setVisible(False)
        self.thumbnail_label.setStyleSheet("background-color: #F1F5F9; border-radius: 6px; padding: 4px;")
        details_layout.addWidget(self.thumbnail_label)

        # Category reassignment dropdown
        reassign_row = QHBoxLayout()
        reassign_row.addWidget(QLabel("Reassign:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(ALL_CATEGORIES)
        self.category_combo.setEnabled(False)
        reassign_row.addWidget(self.category_combo, stretch=1)
        self.btn_reassign = QPushButton("Apply")
        self.btn_reassign.setFixedHeight(28)
        self.btn_reassign.setEnabled(False)
        self.btn_reassign.clicked.connect(self._reassign_category)
        reassign_row.addWidget(self.btn_reassign)
        details_layout.addLayout(reassign_row)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))
        details_layout.addWidget(self.detail_text)

        self.tabs.addTab(details_widget, "File Details")

        # Tab 2: Statistics
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.tabs.addTab(self.stats_text, "Statistics")

        # Tab 3: Settings
        settings_widget = self._create_settings_tab()
        self.tabs.addTab(settings_widget, "Settings")

        # Tab 4: Custom Rules
        rules_widget = self._create_custom_rules_tab()
        self.tabs.addTab(rules_widget, "Custom Rules")

        # Tab 5: Folder Monitor
        monitor_widget = self._create_monitor_tab()
        self.tabs.addTab(monitor_widget, "Folder Monitor")

        # Tab 6: Undo History
        undo_widget = self._create_undo_tab()
        self.tabs.addTab(undo_widget, "Undo History")

        return self.tabs

    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # LLM toggle
        self.chk_use_llm = QCheckBox("Use AI (Ollama LLM) for smart classification")
        self.chk_use_llm.setChecked(self.config.use_llm)
        self.chk_use_llm.toggled.connect(lambda v: setattr(self.config, "use_llm", v))
        layout.addWidget(self.chk_use_llm)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Ollama Model:"))
        self.model_input = QLineEdit(self.config.ollama_model)
        self.model_input.textChanged.connect(lambda v: setattr(self.config, "ollama_model", v))
        model_layout.addWidget(self.model_input)
        layout.addLayout(model_layout)

        # OCR toggle
        self.chk_use_ocr = QCheckBox("Use OCR for scanned PDFs and images (requires Tesseract)")
        self.chk_use_ocr.setChecked(self.config.use_ocr)
        self.chk_use_ocr.toggled.connect(lambda v: setattr(self.config, "use_ocr", v))
        layout.addWidget(self.chk_use_ocr)

        # Cache toggle
        self.chk_use_cache = QCheckBox("Cache classification results (faster re-scans)")
        self.chk_use_cache.setChecked(self.config.use_cache)
        self.chk_use_cache.toggled.connect(lambda v: setattr(self.config, "use_cache", v))
        layout.addWidget(self.chk_use_cache)

        # Duplicate detection
        self.chk_dedup = QCheckBox("Detect and skip duplicate files")
        self.chk_dedup.setChecked(self.config.detect_duplicates)
        self.chk_dedup.toggled.connect(lambda v: setattr(self.config, "detect_duplicates", v))
        layout.addWidget(self.chk_dedup)

        # Dry run toggle
        self.chk_dry_run = QCheckBox("Dry Run (preview only, don't move files)")
        self.chk_dry_run.setChecked(self.config.dry_run)
        self.chk_dry_run.toggled.connect(lambda v: setattr(self.config, "dry_run", v))
        layout.addWidget(self.chk_dry_run)

        # Save / Clear cache buttons
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(btn_save)

        btn_clear_cache = QPushButton("Clear Cache")
        btn_clear_cache.clicked.connect(self._clear_cache)
        btn_row.addWidget(btn_clear_cache)
        layout.addLayout(btn_row)

        # Library status section
        layout.addSpacing(16)
        lib_label = QLabel("Library Status:")
        lib_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lib_label)

        self.lib_status_text = QTextEdit()
        self.lib_status_text.setReadOnly(True)
        self.lib_status_text.setMaximumHeight(160)
        self.lib_status_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.lib_status_text)
        self._refresh_lib_status()

        layout.addStretch()
        return widget

    def _create_custom_rules_tab(self) -> QWidget:
        """Tab for user-defined keyword-to-category rules."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel("Define custom rules: if a file's name or content contains the keywords, it gets the category.")
        info.setWordWrap(True)
        info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(info)

        # Rules table
        self.rules_table = QTableWidget(0, 2)
        self.rules_table.setHorizontalHeaderLabels(["Keywords (comma-separated)", "Category"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.rules_table)

        # Load existing rules
        self._load_rules_to_table()

        # Buttons
        btn_row = QHBoxLayout()

        btn_add = QPushButton("Add Rule")
        btn_add.clicked.connect(self._add_rule_row)
        btn_row.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_rule_row)
        btn_row.addWidget(btn_remove)

        btn_save_rules = QPushButton("Save Rules")
        btn_save_rules.clicked.connect(self._save_rules)
        btn_row.addWidget(btn_save_rules)

        layout.addLayout(btn_row)
        return widget

    def _create_monitor_tab(self) -> QWidget:
        """Tab for real-time folder monitoring (watchdog)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel("Monitor a folder for new files and auto-classify them in real-time.")
        info.setWordWrap(True)
        info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(info)

        # Watch directory selection
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Watch:"))
        self.watch_input = QLineEdit()
        self.watch_input.setPlaceholderText("Select folder to monitor...")
        self.watch_input.setReadOnly(True)
        if self.config.watch_dir:
            self.watch_input.setText(self.config.watch_dir)
        dir_row.addWidget(self.watch_input, stretch=1)

        btn_browse_watch = QPushButton("Browse")
        btn_browse_watch.clicked.connect(self._browse_watch_dir)
        dir_row.addWidget(btn_browse_watch)
        layout.addLayout(dir_row)

        # Start/Stop buttons
        btn_row = QHBoxLayout()
        self.btn_start_watch = QPushButton("Start Monitoring")
        self.btn_start_watch.clicked.connect(self._start_watching)
        btn_row.addWidget(self.btn_start_watch)

        self.btn_stop_watch = QPushButton("Stop Monitoring")
        self.btn_stop_watch.clicked.connect(self._stop_watching)
        self.btn_stop_watch.setEnabled(False)
        btn_row.addWidget(self.btn_stop_watch)
        layout.addLayout(btn_row)

        # Watch status
        self.watch_status = QLabel("Status: Not monitoring")
        self.watch_status.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.watch_status)

        # Log of detected files
        self.watch_log = QTextEdit()
        self.watch_log.setReadOnly(True)
        self.watch_log.setFont(QFont("Consolas", 9))
        self.watch_log.setPlaceholderText("New files will appear here...")
        layout.addWidget(self.watch_log)

        return widget

    def _create_undo_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.undo_list = QTreeWidget()
        self.undo_list.setHeaderLabels(["Manifest", "Files", "Date"])
        layout.addWidget(self.undo_list)

        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_undo_list)
        btn_layout.addWidget(btn_refresh)

        self.btn_undo = QPushButton("Undo Selected")
        self.btn_undo.clicked.connect(self._perform_undo)
        btn_layout.addWidget(self.btn_undo)

        layout.addLayout(btn_layout)
        return widget

    def _create_action_buttons(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_scan = QPushButton("  1. Scan Files")
        self.btn_scan.setMinimumHeight(42)
        self.btn_scan.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_scan.clicked.connect(self._start_scan)
        self.btn_scan.setEnabled(False)
        layout.addWidget(self.btn_scan)

        self.btn_classify = QPushButton("  2. Classify")
        self.btn_classify.setMinimumHeight(42)
        self.btn_classify.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_classify.clicked.connect(self._start_classify)
        self.btn_classify.setEnabled(False)
        layout.addWidget(self.btn_classify)

        self.btn_organize = QPushButton("  3. Organize")
        self.btn_organize.setMinimumHeight(42)
        self.btn_organize.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_organize.clicked.connect(self._start_organize)
        self.btn_organize.setEnabled(False)
        layout.addWidget(self.btn_organize)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_operation)
        layout.addWidget(self.btn_cancel)

        return widget

    # -- Directory Browsing --

    def _browse_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if path:
            self.source_input.setText(path)
            self.config.last_scan_dir = path
            self.btn_scan.setEnabled(True)
            self.status_bar.showMessage(f"Source: {path}")

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_input.setText(path)
            self.config.last_output_dir = path

    def _browse_watch_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Monitor")
        if path:
            self.watch_input.setText(path)
            self.config.watch_dir = path

    # -- Scan --

    def _start_scan(self):
        source = self.source_input.text()
        if not source:
            return

        self._set_busy(True, "Scanning files...")
        self.file_tree.clear()
        self.files = []

        self.scan_worker = ScanWorker(Path(source), self.config)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_error)
        self.scan_worker.start()

    def _on_scan_progress(self, count: int, current: str):
        self.progress_bar.setFormat(f"Scanned {count} files... %p%")
        self.status_bar.showMessage(f"Scanning: {current}")

    def _on_scan_finished(self, files: list[FileInfo]):
        self.files = files
        self._set_busy(False)

        # Detect duplicates
        if self.config.detect_duplicates:
            scanner = FileScanner(self.config)
            dupes = scanner.find_duplicates(files)
            dup_count = 0
            for hash_val, group in dupes.items():
                for fi in group[1:]:
                    fi.is_duplicate = True
                    dup_count += 1
            self.status_bar.showMessage(
                f"Found {len(files)} files ({dup_count} duplicates). Click 'Classify' to continue."
            )
        else:
            self.status_bar.showMessage(
                f"Found {len(files)} files. Click 'Classify' to continue."
            )

        self.btn_classify.setEnabled(True)
        self._check_llm_status()

    # -- Classify --

    def _start_classify(self):
        if not self.files:
            return

        self._set_busy(True, "Classifying files...")
        self.progress_bar.setMaximum(len(self.files))

        self.classify_worker = ClassifyWorker(self.files, self.config)
        self.classify_worker.progress.connect(self._on_classify_progress)
        self.classify_worker.finished.connect(self._on_classify_finished)
        self.classify_worker.error.connect(self._on_error)
        self.classify_worker.start()

    def _on_classify_progress(self, current: int, total: int, status: str):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total} - {status}")

    def _on_classify_finished(self, files: list[FileInfo], cache_hits: int):
        self.files = files
        self._set_busy(False)
        self._populate_tree()
        self._update_stats()
        self.btn_export.setEnabled(True)

        cache_msg = f" ({cache_hits} from cache)" if cache_hits > 0 else ""
        output = self.output_input.text()
        if output:
            self.btn_organize.setEnabled(True)
            self.status_bar.showMessage(f"Classification complete{cache_msg}. Review and click 'Organize'.")
        else:
            self.status_bar.showMessage(f"Classification complete{cache_msg}. Select an output directory, then click 'Organize'.")

    # -- Organize --

    def _start_organize(self):
        output = self.output_input.text()
        if not output or not self.files:
            QMessageBox.warning(self, "Missing Output", "Please select an output directory.")
            return

        mode = "DRY RUN" if self.config.dry_run else "MOVE FILES"
        if not self.config.dry_run:
            reply = QMessageBox.question(
                self,
                "Confirm Move",
                f"This will MOVE {sum(1 for f in self.files if not f.is_duplicate)} files "
                f"to:\n{output}\n\nThis operation can be undone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._set_busy(True, f"Organizing ({mode})...")

        self.organize_worker = OrganizeWorker(self.files, Path(output), self.config)
        self.organize_worker.progress.connect(self._on_organize_progress)
        self.organize_worker.finished.connect(self._on_organize_finished)
        self.organize_worker.error.connect(self._on_error)
        self.organize_worker.start()

    def _on_organize_progress(self, current: int, total: int, status: str):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total} - {status}")

    def _on_organize_finished(self, result: OrganizeResult):
        self._set_busy(False)
        mode = "DRY RUN" if self.config.dry_run else "MOVED"

        summary = (
            f"[{mode}] Organization Complete!\n\n"
            f"Total files: {result.total_files}\n"
            f"Organized: {result.moved_files}\n"
            f"Duplicates skipped: {result.duplicates_found}\n"
            f"Errors: {len(result.errors)}\n"
        )

        if result.errors:
            summary += "\nErrors:\n" + "\n".join(f"  - {e}" for e in result.errors[:20])

        self.detail_text.setText(summary)
        self.tabs.setCurrentIndex(0)
        self.status_bar.showMessage(
            f"{mode}: {result.moved_files} files organized, "
            f"{result.duplicates_found} duplicates skipped."
        )

        if self.config.dry_run:
            QMessageBox.information(
                self, "Dry Run Complete",
                f"Dry run finished. {result.moved_files} files would be organized.\n\n"
                "Uncheck 'Dry Run' in Settings and click 'Organize' again to actually move files."
            )

    # -- Undo --

    def _refresh_undo_list(self):
        self.undo_list.clear()
        organizer = FileOrganizer(self.config)
        for manifest_path in organizer.get_manifests():
            try:
                data = json.loads(manifest_path.read_text())
                item = QTreeWidgetItem([
                    manifest_path.name,
                    str(len(data)),
                    manifest_path.stem.replace("manifest_", ""),
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, str(manifest_path))
                self.undo_list.addTopLevelItem(item)
            except (json.JSONDecodeError, OSError):
                pass

    def _perform_undo(self):
        selected = self.undo_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a manifest to undo.")
            return

        manifest_path = Path(selected.data(0, Qt.ItemDataRole.UserRole))
        reply = QMessageBox.question(
            self, "Confirm Undo",
            f"This will restore files from:\n{manifest_path.name}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        organizer = FileOrganizer(self.config)
        restored, errors = organizer.undo(manifest_path)

        msg = f"Restored {restored} files."
        if errors:
            msg += f"\n{len(errors)} errors:\n" + "\n".join(errors[:10])

        QMessageBox.information(self, "Undo Complete", msg)
        self._refresh_undo_list()

    # -- Tree View --

    def _populate_tree(self):
        """Populate the file tree grouped by category."""
        self.file_tree.clear()

        # Group files by category
        groups: dict[str, list[FileInfo]] = {}
        for fi in self.files:
            if fi.is_duplicate:
                continue
            cat = fi.category.value
            groups.setdefault(cat, []).append(fi)

        for cat_path in sorted(groups.keys()):
            files = groups[cat_path]
            cat_item = QTreeWidgetItem([
                f"{cat_path} ({len(files)} files)",
                "", "", ""
            ])
            cat_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            for fi in sorted(files, key=lambda f: f.name.lower()):
                size_str = self._format_size(fi.size_bytes)
                conf_str = f"{fi.confidence:.0%}"
                child = QTreeWidgetItem([fi.name, fi.category.name, conf_str, size_str])
                child.setData(0, Qt.ItemDataRole.UserRole, fi)

                # Color code by confidence
                if fi.confidence >= 0.8:
                    child.setForeground(2, QColor(COLORS["success"]))
                elif fi.confidence >= 0.5:
                    child.setForeground(2, QColor(COLORS["warning"]))
                else:
                    child.setForeground(2, QColor(COLORS["danger"]))

                cat_item.addChild(child)

            self.file_tree.addTopLevelItem(cat_item)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        fi = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(fi, FileInfo):
            # Show thumbnail for images
            self._show_thumbnail(fi)

            # Enable category reassignment
            self.category_combo.setEnabled(True)
            self.btn_reassign.setEnabled(True)
            # Set current category in dropdown
            try:
                idx = ALL_CATEGORIES.index(fi.category.value)
                self.category_combo.setCurrentIndex(idx)
            except ValueError:
                pass
            # Store reference to current item for reassignment
            self._selected_tree_item = item
            self._selected_file_info = fi

            details = (
                f"File: {fi.name}\n"
                f"Path: {fi.path}\n"
                f"Size: {self._format_size(fi.size_bytes)}\n"
                f"Type: {fi.file_type.value}\n"
                f"Category: {fi.category.value}\n"
                f"Confidence: {fi.confidence:.1%}\n"
                f"Modified: {fi.modified_time}\n"
                f"Duplicate: {fi.is_duplicate}\n"
            )
            if fi.destination:
                details += f"Destination: {fi.destination}\n"
            if fi.content_preview:
                details += f"\n--- Content Preview ---\n{fi.content_preview}"
            if fi.metadata:
                details += f"\n\n--- Metadata ---\n"
                for k, v in fi.metadata.items():
                    details += f"{k}: {v}\n"

            self.detail_text.setText(details)
            self.tabs.setCurrentIndex(0)

    def _show_thumbnail(self, fi: FileInfo):
        """Show image thumbnail in the details panel."""
        if fi.extension.lower() in IMAGE_EXTENSIONS:
            try:
                pixmap = QPixmap(str(fi.path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        QSize(380, 240),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.thumbnail_label.setPixmap(scaled)
                    self.thumbnail_label.setVisible(True)
                    return
            except Exception:
                pass
        self.thumbnail_label.setVisible(False)
        self.thumbnail_label.clear()

    # -- Category Reassignment --

    def _reassign_category(self):
        """Manually reassign a file's category from the dropdown."""
        if not hasattr(self, "_selected_file_info"):
            return

        new_cat_value = self.category_combo.currentText()
        try:
            new_category = FileCategory(new_cat_value)
        except ValueError:
            return

        fi = self._selected_file_info
        fi.category = new_category
        fi.confidence = 1.0  # Manual assignment = 100% confidence

        # Update tree item
        item = self._selected_tree_item
        item.setText(1, new_category.name)
        item.setText(2, "100%")
        item.setForeground(2, QColor(COLORS["success"]))

        # Update details
        self._on_tree_item_clicked(item, 0)
        self._update_stats()
        self.status_bar.showMessage(f"Reassigned '{fi.name}' to '{new_cat_value}'")

    # -- Export CSV --

    def _export_csv(self):
        """Export classification results as CSV."""
        if not self.files:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "organization_report.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "File Name", "Path", "Size (bytes)", "File Type",
                    "Category", "Confidence", "Is Duplicate", "Modified"
                ])
                for fi in self.files:
                    writer.writerow([
                        fi.name, str(fi.path), fi.size_bytes, fi.file_type.value,
                        fi.category.value, f"{fi.confidence:.2f}",
                        fi.is_duplicate, fi.modified_time,
                    ])

            QMessageBox.information(self, "Export Complete", f"Report saved to:\n{path}")
            self.status_bar.showMessage(f"Exported {len(self.files)} files to CSV")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    # -- Custom Rules --

    def _load_rules_to_table(self):
        """Load custom rules from config into the table."""
        self.rules_table.setRowCount(0)
        for rule in self.config.custom_rules:
            row = self.rules_table.rowCount()
            self.rules_table.insertRow(row)
            self.rules_table.setItem(row, 0, QTableWidgetItem(rule.get("keywords", "")))
            # Category dropdown in cell
            combo = QComboBox()
            combo.addItems(ALL_CATEGORIES)
            cat_val = rule.get("category", "")
            try:
                idx = ALL_CATEGORIES.index(cat_val)
                combo.setCurrentIndex(idx)
            except ValueError:
                pass
            self.rules_table.setCellWidget(row, 1, combo)

    def _add_rule_row(self):
        """Add an empty rule row."""
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        self.rules_table.setItem(row, 0, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItems(ALL_CATEGORIES)
        self.rules_table.setCellWidget(row, 1, combo)

    def _remove_rule_row(self):
        """Remove the selected rule row."""
        row = self.rules_table.currentRow()
        if row >= 0:
            self.rules_table.removeRow(row)

    def _save_rules(self):
        """Save custom rules from table to config."""
        rules = []
        for row in range(self.rules_table.rowCount()):
            keywords_item = self.rules_table.item(row, 0)
            combo = self.rules_table.cellWidget(row, 1)
            if keywords_item and combo:
                keywords = keywords_item.text().strip()
                category = combo.currentText()
                if keywords and category:
                    rules.append({"keywords": keywords, "category": category})

        self.config.custom_rules = rules
        self.config.save()
        self.status_bar.showMessage(f"Saved {len(rules)} custom rules")

    # -- Folder Monitor (Watchdog) --

    def _start_watching(self):
        """Start monitoring a folder for new files."""
        watch_dir = self.watch_input.text()
        if not watch_dir:
            QMessageBox.warning(self, "No Directory", "Select a directory to monitor.")
            return

        try:
            self.watcher_worker = WatcherWorker(Path(watch_dir))
            self.watcher_worker.new_file.connect(self._on_new_file_detected)
            self.watcher_worker.error.connect(self._on_watch_error)
            self.watcher_worker.start()

            self.btn_start_watch.setEnabled(False)
            self.btn_stop_watch.setEnabled(True)
            self.watch_status.setText(f"Status: Monitoring {watch_dir}")
            self.watch_status.setStyleSheet(f"color: {COLORS['success']};")
            self.config.watch_dir = watch_dir
        except Exception as e:
            QMessageBox.critical(self, "Watch Error", str(e))

    def _stop_watching(self):
        """Stop folder monitoring."""
        if self.watcher_worker:
            self.watcher_worker.stop_watching()
            self.watcher_worker.quit()
            self.watcher_worker.wait(3000)
            self.watcher_worker = None

        self.btn_start_watch.setEnabled(True)
        self.btn_stop_watch.setEnabled(False)
        self.watch_status.setText("Status: Not monitoring")
        self.watch_status.setStyleSheet(f"color: {COLORS['text_secondary']};")

    def _on_new_file_detected(self, path_str: str):
        """Handle a newly detected file."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.watch_log.append(f"[{timestamp}] New file: {path_str}")

    def _on_watch_error(self, error: str):
        self.watch_log.append(f"[ERROR] {error}")
        self._stop_watching()

    # -- Statistics --

    def _update_stats(self):
        if not self.files:
            return

        total = len(self.files)
        dupes = sum(1 for f in self.files if f.is_duplicate)
        categories = Counter(f.category.value for f in self.files if not f.is_duplicate)
        types = Counter(f.file_type.value for f in self.files)
        total_size = sum(f.size_bytes for f in self.files)

        stats = f"=== Scan Statistics ===\n\n"
        stats += f"Total files: {total}\n"
        stats += f"Duplicates: {dupes}\n"
        stats += f"Unique files: {total - dupes}\n"
        stats += f"Total size: {self._format_size(total_size)}\n\n"

        stats += "=== By Category ===\n"
        for cat, count in categories.most_common():
            stats += f"  {cat}: {count}\n"

        stats += "\n=== By File Type ===\n"
        for ftype, count in types.most_common():
            stats += f"  {ftype}: {count}\n"

        # Confidence distribution
        high = sum(1 for f in self.files if f.confidence >= 0.8)
        med = sum(1 for f in self.files if 0.5 <= f.confidence < 0.8)
        low = sum(1 for f in self.files if f.confidence < 0.5)
        stats += f"\n=== Classification Confidence ===\n"
        stats += f"  High (>=80%): {high}\n"
        stats += f"  Medium (50-79%): {med}\n"
        stats += f"  Low (<50%): {low}\n"

        self.stats_text.setText(stats)

    # -- Helpers --

    def _check_llm_status(self):
        """Check and display Ollama/LLM availability."""
        if not self.config.use_llm:
            self.llm_status.setText("LLM: Off (rule-based mode)")
            self.llm_status.setStyleSheet(f"color: {COLORS['text_secondary']};")
            return

        try:
            import ollama as _  # noqa: F401
        except ImportError:
            self.llm_status.setText("LLM: ollama package not installed")
            self.llm_status.setStyleSheet(f"color: {COLORS['warning']};")
            return

        try:
            from src.classifiers.llm_classifier import LLMClassifier
            llm = LLMClassifier(self.config)
            if llm.is_available():
                self.llm_status.setText(f"LLM: {self.config.ollama_model}")
                self.llm_status.setStyleSheet(f"color: {COLORS['success']};")
            else:
                self.llm_status.setText("LLM: Model not found (rule-based mode)")
                self.llm_status.setStyleSheet(f"color: {COLORS['warning']};")
        except Exception:
            self.llm_status.setText("LLM: Ollama not running (rule-based mode)")
            self.llm_status.setStyleSheet(f"color: {COLORS['warning']};")

    def _refresh_lib_status(self):
        """Show which optional libraries are installed."""
        from src.utils.extractors import get_available_extractors

        lines = []
        for lib_name, available in get_available_extractors().items():
            icon = "OK" if available else "MISSING"
            lines.append(f"  [{icon:>7}]  {lib_name}")

        # Check ollama separately
        try:
            import ollama  # noqa: F401
            lines.append(f"  [     OK]  Ollama (AI classification)")
        except ImportError:
            lines.append(f"  [MISSING]  Ollama (optional - AI classification)")

        # Check watchdog
        try:
            import watchdog  # noqa: F401
            lines.append(f"  [     OK]  Watchdog (folder monitoring)")
        except ImportError:
            lines.append(f"  [MISSING]  Watchdog (optional - folder monitoring)")

        lines.append("")
        lines.append("Missing libraries? Run:  pip install <package-name>")
        lines.append("App works without Ollama using rule-based classification.")

        self.lib_status_text.setText("\n".join(lines))

    def _clear_cache(self):
        """Clear the classification cache."""
        try:
            from src.core.cache import ClassificationCache
            cache = ClassificationCache()
            cache.clear()
            cache.close()
            self.status_bar.showMessage("Classification cache cleared")
        except Exception as e:
            self.status_bar.showMessage(f"Failed to clear cache: {e}")

    def _set_busy(self, busy: bool, message: str = ""):
        """Toggle UI busy state."""
        self.btn_scan.setEnabled(not busy and bool(self.source_input.text()))
        self.btn_classify.setEnabled(not busy and bool(self.files))
        self.btn_organize.setEnabled(not busy and bool(self.files) and bool(self.output_input.text()))
        self.btn_cancel.setVisible(busy)
        self.progress_bar.setVisible(busy)

        if busy:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.status_bar.showMessage(message)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)

    def _cancel_operation(self):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.cancel()
        self._set_busy(False)
        self.status_bar.showMessage("Operation cancelled.")

    def _on_error(self, error: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error}")
        self.status_bar.showMessage(f"Error: {error}")

    def _save_settings(self):
        self.config.save()
        self.status_bar.showMessage("Settings saved.")
        self._check_llm_status()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['bg']};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 12px;
                padding-top: 24px;
                background-color: {COLORS['card']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
            QPushButton#btn_cancel {{
                background-color: {COLORS['danger']};
            }}
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px 10px;
                background: white;
            }}
            QTreeWidget {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: white;
                alternate-background-color: #F1F5F9;
            }}
            QProgressBar {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                text-align: center;
                height: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: white;
            }}
            QTextEdit {{
                border: none;
                background: white;
            }}
            QCheckBox {{
                spacing: 8px;
                padding: 4px;
            }}
            QTableWidget {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: white;
                alternate-background-color: #F1F5F9;
            }}
            QComboBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                background: white;
            }}
        """)

    def closeEvent(self, event):
        """Clean up on close."""
        self._stop_watching()
        super().closeEvent(event)
