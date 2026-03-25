"""Main application window for the Data Organiser GUI."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QTextEdit, QCheckBox, QComboBox, QGroupBox,
    QSplitter, QStatusBar, QMessageBox, QHeaderView, QLineEdit,
    QFrame, QSizePolicy, QApplication,
)

from src.core.config import AppConfig, MANIFEST_DIR
from src.core.models import FileCategory, FileInfo, OrganizeResult
from src.core.scanner import FileScanner
from src.core.organizer import FileOrganizer
from src.ui.workers import ScanWorker, ClassifyWorker, OrganizeWorker

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


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.files: list[FileInfo] = []
        self.scan_worker: ScanWorker | None = None
        self.classify_worker: ClassifyWorker | None = None
        self.organize_worker: OrganizeWorker | None = None

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

        # ── Header ──
        header = self._create_header()
        main_layout.addWidget(header)

        # ── Directory Selection ──
        dir_group = self._create_dir_selection()
        main_layout.addWidget(dir_group)

        # ── Main Content (Splitter: Tree + Details) ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: File tree
        left_panel = self._create_file_tree_panel()
        splitter.addWidget(left_panel)

        # Right: Tabs (Preview, Stats, Settings, Undo)
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([600, 400])
        main_layout.addWidget(splitter, stretch=1)

        # ── Progress Bar ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # ── Action Buttons ──
        actions = self._create_action_buttons()
        main_layout.addWidget(actions)

        # ── Status Bar ──
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

        label = QLabel("Organized File Preview")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(label)

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

        # Tab 1: File Details / Preview
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))
        self.tabs.addTab(self.detail_text, "File Details")

        # Tab 2: Statistics
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.tabs.addTab(self.stats_text, "Statistics")

        # Tab 3: Settings
        settings_widget = self._create_settings_tab()
        self.tabs.addTab(settings_widget, "Settings")

        # Tab 4: Undo History
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

        # Save settings button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        # Library status section
        layout.addSpacing(16)
        lib_label = QLabel("Library Status:")
        lib_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lib_label)

        self.lib_status_text = QTextEdit()
        self.lib_status_text.setReadOnly(True)
        self.lib_status_text.setMaximumHeight(140)
        self.lib_status_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.lib_status_text)
        self._refresh_lib_status()

        layout.addStretch()
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

    # ── Directory Browsing ──

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

    # ── Scan ──

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
                # Keep the first, mark rest as duplicates
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

    # ── Classify ──

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

    def _on_classify_finished(self, files: list[FileInfo]):
        self.files = files
        self._set_busy(False)
        self._populate_tree()
        self._update_stats()

        output = self.output_input.text()
        if output:
            self.btn_organize.setEnabled(True)
            self.status_bar.showMessage("Classification complete. Review and click 'Organize'.")
        else:
            self.status_bar.showMessage("Classification complete. Select an output directory, then click 'Organize'.")

    # ── Organize ──

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

    # ── Undo ──

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

    # ── Tree View ──

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

    # ── Statistics ──

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

    # ── Helpers ──

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

        lines.append("")
        lines.append("Missing libraries? Run:  pip install <package-name>")
        lines.append("App works without Ollama using rule-based classification.")

        self.lib_status_text.setText("\n".join(lines))

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
        """)
