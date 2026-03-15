from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List
import math
import re
import sys

import requests

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QProgressBar,
    QSpinBox,
)

from anchoring import compute_sha256
from config_manager import load_config
from llm_clients import LLMClientError, analyze_with_provider
from scanner import discover_files

DISCLAIMER = (
    "⚠️ DIDACTIC USE ONLY — DO NOT USE ON PROPRIETARY SOFTWARE "
    "WITHOUT EXPLICIT OWNER CONSENT"
)

OUTPUT_BRAND = "🛡️ SYRAG™ universal source 1.1"

EXTENSION_OPTIONS = [
    ("Python", ".py"),
    ("JavaScript", ".js"),
    ("TypeScript", ".ts"),
    ("Java", ".java"),
    ("Go", ".go"),
    ("Rust", ".rs"),
    ("C++", ".cpp"),
    ("C", ".c"),
    ("PHP", ".php"),
    ("Ruby", ".rb"),
    ("Shell", ".sh"),
    ("Markdown", ".md"),
    ("JSON", ".json"),
]


class ScanWorker(QThread):
    scan_done = pyqtSignal(object)
    scan_error = pyqtSignal(str)

    def __init__(self, root: Path, exts: List[str]):
        super().__init__()
        self.root = root
        self.exts = exts

    def run(self):
        try:
            files = discover_files(self.root, self.exts)
            self.scan_done.emit(files)
        except Exception as e:
            self.scan_error.emit(str(e))


class AnalysisWorker(QThread):
    analysis_done = pyqtSignal(str)
    analysis_error = pyqtSignal(str)
    analysis_progress = pyqtSignal(str)

    def __init__(
        self,
        provider: str,
        model: str,
        prompt: str,
        config: dict,
        api_key_override: str = "",
        chunk_timeout: int = 120,
    ):
        super().__init__()
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.config = config
        self.api_key_override = api_key_override
        self.chunk_timeout = chunk_timeout

    def run(self):
        try:
            out = analyze_with_provider(
                self.provider,
                self.model,
                self.prompt,
                self.config,
                api_key_override=self.api_key_override,
                chunk_timeout=self.chunk_timeout,
                progress_callback=lambda msg: self.analysis_progress.emit(msg),
            )
            self.analysis_done.emit(out)
        except Exception as e:
            self.analysis_error.emit(str(e))


class CodeScanWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SYRAG™ universal source 1.1")
        self.resize(1500, 900)

        self.config = load_config()
        self.current_root: Path | None = None
        self.current_file: Path | None = None
        self.scan_worker: ScanWorker | None = None
        self.analysis_worker: AnalysisWorker | None = None
        self.ext_checks: Dict[str, QCheckBox] = {}
        self.local_llm_choices: List[tuple] = []

        self._build_ui()
        self._build_menu()
        self._apply_llm_defaults()
        self._show_disclaimer_once()

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        act_safe_exit = QAction("Safe Exit", self)
        act_safe_exit.setShortcut("Ctrl+Q")
        act_safe_exit.triggered.connect(self._safe_exit)
        file_menu.addAction(act_safe_exit)

        act_restart = QAction("Restart App", self)
        act_restart.setShortcut("Ctrl+R")
        act_restart.triggered.connect(self._restart_application)
        file_menu.addAction(act_restart)

        actions_menu = menu.addMenu("Actions")
        act_scan = QAction("Scan", self)
        act_scan.triggered.connect(self._scan)
        actions_menu.addAction(act_scan)

        act_estimate = QAction("Estimate Size/Complexity", self)
        act_estimate.triggered.connect(self._estimate_selected)
        actions_menu.addAction(act_estimate)

        act_analyze = QAction("Analyze Selected File", self)
        act_analyze.triggered.connect(self._analyze_selected)
        actions_menu.addAction(act_analyze)

        act_scan_local_llms = QAction("Scan Local LLMs", self)
        act_scan_local_llms.triggered.connect(self._scan_local_llms)
        actions_menu.addAction(act_scan_local_llms)

        act_hash = QAction("Compute SHA256", self)
        act_hash.triggered.connect(self._hash_selected)
        actions_menu.addAction(act_hash)

        help_menu = menu.addMenu("Help")
        act_rag_explain = QAction("Explain Selected Code (RAG)", self)
        act_rag_explain.setShortcut("Ctrl+Shift+E")
        act_rag_explain.triggered.connect(self._help_explain_selected_rag)
        help_menu.addAction(act_rag_explain)

        act_quick_help = QAction("Quick Help", self)
        act_quick_help.triggered.connect(self._show_quick_help)
        help_menu.addAction(act_quick_help)

        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("SYRAG™ universal source 1.1")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setStyleSheet("background:#8b0000; color:white; padding:8px; font-weight:700;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        top = QGroupBox("Scope")
        top_l = QGridLayout(top)

        self.edt_root = QLineEdit()
        self.edt_root.setPlaceholderText("Select a folder to scan")
        btn_pick = QPushButton("Select Folder")
        btn_pick.clicked.connect(self._pick_folder)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.clicked.connect(self._scan)

        top_l.addWidget(QLabel("Root folder"), 0, 0)
        top_l.addWidget(self.edt_root, 0, 1)
        top_l.addWidget(btn_pick, 0, 2)
        top_l.addWidget(self.btn_scan, 0, 3)

        ext_group = QGroupBox("Extensions")
        ext_layout = QGridLayout(ext_group)
        default_exts = set(self.config.get("scan", {}).get("default_extensions", []))
        for idx, (label, ext) in enumerate(EXTENSION_OPTIONS):
            chk = QCheckBox(f"{label} ({ext})")
            chk.setChecked(ext in default_exts or not default_exts)
            self.ext_checks[ext] = chk
            row = idx // 4
            col = idx % 4
            ext_layout.addWidget(chk, row, col)
        top_l.addWidget(ext_group, 1, 0, 1, 4)
        layout.addWidget(top)

        controls = QGroupBox("LLM")
        controls_l = QGridLayout(controls)

        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["ollama", "openrouter", "openai_compatible"])
        self.cmb_provider.currentTextChanged.connect(self._on_provider_changed)

        self.edt_model = QLineEdit("")
        self.cmb_local_models = QComboBox()
        self.cmb_local_models.addItem("Scan local models...")
        self.cmb_local_models.currentIndexChanged.connect(self._on_local_model_selected)
        self.cmb_analysis_depth = QComboBox()
        self.cmb_analysis_depth.addItems(["Fast", "Balanced", "Deep"])
        self.cmb_analysis_depth.setCurrentText("Balanced")
        self.spn_chunk_timeout = QSpinBox()
        self.spn_chunk_timeout.setRange(10, 600)
        self.spn_chunk_timeout.setValue(120)
        self.spn_chunk_timeout.setSuffix(" s")
        self.btn_scan_local_llms = QPushButton("Scan Local LLMs")
        self.btn_scan_local_llms.clicked.connect(self._scan_local_llms)
        self.btn_analyze = QPushButton("Analyze Selected File")
        self.btn_analyze.clicked.connect(self._analyze_selected)

        self.btn_estimate = QPushButton("Estimate Size/Complexity")
        self.btn_estimate.clicked.connect(self._estimate_selected)

        self.edt_api_key = QLineEdit("")
        self.edt_api_key.setPlaceholderText("Optional API key override (OpenRouter/OpenAI-compatible)")
        self.edt_api_key.setEchoMode(QLineEdit.Password)
        self.btn_toggle_key = QPushButton("Show")
        self.btn_toggle_key.clicked.connect(self._toggle_api_key_visibility)

        self.btn_hash = QPushButton("Compute SHA256")
        self.btn_hash.clicked.connect(self._hash_selected)

        controls_l.addWidget(QLabel("LLM provider"), 0, 0)
        controls_l.addWidget(self.cmb_provider, 0, 1)
        controls_l.addWidget(QLabel("Model"), 0, 2)
        controls_l.addWidget(self.edt_model, 0, 3)
        controls_l.addWidget(self.btn_analyze, 0, 4)
        controls_l.addWidget(self.btn_estimate, 0, 5)
        controls_l.addWidget(self.btn_scan_local_llms, 0, 6)
        controls_l.addWidget(QLabel("Local models"), 1, 0)
        controls_l.addWidget(self.cmb_local_models, 1, 1, 1, 4)
        controls_l.addWidget(QLabel("Analysis depth"), 1, 5)
        controls_l.addWidget(self.cmb_analysis_depth, 1, 6)
        controls_l.addWidget(QLabel("Chunk timeout"), 1, 7)
        controls_l.addWidget(self.spn_chunk_timeout, 1, 8)
        controls_l.addWidget(QLabel("API key"), 2, 0)
        controls_l.addWidget(self.edt_api_key, 2, 1, 1, 3)
        controls_l.addWidget(self.btn_toggle_key, 2, 4)
        controls_l.addWidget(self.btn_hash, 2, 5)
        controls_l.addWidget(QLabel(""), 2, 6)  # spacer

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color:#666;")
        self.prg_busy = QProgressBar()
        self.prg_busy.setRange(0, 0)
        self.prg_busy.setVisible(False)
        controls_l.addWidget(self.lbl_status, 3, 0, 1, 6)
        controls_l.addWidget(self.prg_busy, 3, 6, 1, 2)

        btn_pick.setToolTip("Select the folder to scan recursively")
        self.btn_scan.setToolTip("Run recursive scan using selected extensions")
        self.btn_estimate.setToolTip("Estimate size, complexity and token volume for selected files")
        self.btn_analyze.setToolTip("Send selected file content to chosen LLM provider")
        self.btn_hash.setToolTip("Compute SHA256 hash for selected file")
        self.edt_api_key.setToolTip("Optional runtime API key override for cloud providers")
        self.btn_scan_local_llms.setToolTip("Scan local runtimes and list available local LLM models")
        self.cmb_local_models.setToolTip("Select a detected local model to auto-fill provider and model")
        self.cmb_analysis_depth.setToolTip("Fast=less context, Balanced=default, Deep=more context")
        self.spn_chunk_timeout.setToolTip(
            "Max seconds to wait between token chunks from local Ollama.\n"
            "Increase if your model is slow to start (e.g. first token takes >90s).\n"
            "Default 120s covers most 7-8B models on CPU."
        )
        layout.addWidget(controls)

        split = QSplitter(Qt.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Ext", "Size"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemClicked.connect(self._on_tree_clicked)

        right = QWidget()
        right_l = QVBoxLayout(right)
        self.txt_source = QPlainTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText("Analysis / anchoring output")
        self.txt_output.setPlainText(self._output_header())

        right_l.addWidget(QLabel("Source"))
        right_l.addWidget(self.txt_source, 3)
        right_l.addWidget(QLabel("Output"))
        right_l.addWidget(self.txt_output, 2)

        split.addWidget(self.tree)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        layout.addWidget(split, 1)

        footer = QLabel("SYRAG™ universal source 1.1 — Didactic only. Proprietary software requires explicit consent.")
        footer.setStyleSheet("color:#cc2222; font-weight:700;")
        layout.addWidget(footer)

        self.setCentralWidget(root)

    def _show_disclaimer_once(self):
        QMessageBox.warning(self, "Legal Disclaimer", DISCLAIMER)

    def _show_quick_help(self):
        QMessageBox.information(
            self,
            "Quick Help",
            "1) Select folder and extensions\n"
            "2) Run Scan\n"
            "3) Select one or more files\n"
            "4) Use Estimate/Analyze/Hash actions\n"
            "5) Use Help > Explain Selected Code (RAG) for natural language explanation",
        )

    def _show_about(self):
        QMessageBox.information(
            self,
            "About",
            "SYRAG™ universal source 1.1\n"
            "First release motivation: stimulate the use of LLMs to go beyond open source and make programming languages universal.",
        )

    def _safe_exit(self):
        if not self._stop_workers_for_shutdown():
            return
        self.close()

    def _restart_application(self):
        if not self._stop_workers_for_shutdown():
            return
        ok = QMessageBox.question(
            self,
            "Restart App",
            "Restart SYRAG™ universal source 1.1 now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        QApplication.quit()
        from PyQt5.QtCore import QProcess

        QProcess.startDetached(sys.executable, sys.argv)

    def _stop_workers_for_shutdown(self) -> bool:
        running = []
        if self.scan_worker and self.scan_worker.isRunning():
            running.append("scan")
        if self.analysis_worker and self.analysis_worker.isRunning():
            running.append("analysis")

        if not running:
            return True

        ok = QMessageBox.question(
            self,
            "Workers running",
            "Background operations are still running. Stop them and continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return False

        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.requestInterruption()
            self.scan_worker.terminate()
            self.scan_worker.wait(1500)
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.requestInterruption()
            self.analysis_worker.terminate()
            self.analysis_worker.wait(1500)
        return True

    def _toggle_api_key_visibility(self):
        if self.edt_api_key.echoMode() == QLineEdit.Password:
            self.edt_api_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("Hide")
        else:
            self.edt_api_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("Show")

    def _set_busy(self, busy: bool, message: str = ""):
        self.prg_busy.setVisible(busy)
        if message:
            self.lbl_status.setText(message)
        elif not busy:
            self.lbl_status.setText("Ready")

    def _output_header(self) -> str:
        return (
            f"{OUTPUT_BRAND}\n"
            f"{DISCLAIMER}\n"
            f"{'=' * 68}"
        )

    def _provider_cfg(self, provider: str) -> dict:
        return self.config.get("llm", {}).get("providers", {}).get(provider, {})

    def _apply_llm_defaults(self):
        default_provider = self.config.get("llm", {}).get("default_provider", "ollama")
        idx = self.cmb_provider.findText(default_provider)
        if idx >= 0:
            self.cmb_provider.setCurrentIndex(idx)
        self._on_provider_changed(self.cmb_provider.currentText())
        self._scan_local_llms()

    def _scan_local_llms(self):
        self._set_busy(True, "Scanning local LLM runtimes...")
        self.local_llm_choices = []
        self.cmb_local_models.blockSignals(True)
        self.cmb_local_models.clear()

        ollama_models = self._list_ollama_models()
        preferred = ["llama3.1:8b", "granite3-dense:8b", "olmo-3:7b", "qwen3:8b"]

        def rank_model(name: str) -> int:
            try:
                return preferred.index(name)
            except ValueError:
                return len(preferred)

        ollama_models = sorted(ollama_models, key=lambda m: (rank_model(m), m.lower()))

        for model in ollama_models:
            display = f"Ollama • {model}"
            self.local_llm_choices.append((display, "ollama", model))
            self.cmb_local_models.addItem(display)

        if not self.local_llm_choices:
            self.cmb_local_models.addItem("No local models detected")
            self._log("Local LLM scan: no models detected")
        else:
            self._log(f"Local LLM scan: detected {len(self.local_llm_choices)} model(s)")
            self.cmb_local_models.setCurrentIndex(0)
            _display, provider, model = self.local_llm_choices[0]
            p_idx = self.cmb_provider.findText(provider)
            if p_idx >= 0:
                self.cmb_provider.setCurrentIndex(p_idx)
            self.edt_model.setText(model)
            self._log(f"Recommended local model selected: {provider} / {model}")

        self.cmb_local_models.blockSignals(False)
        self._set_busy(False, "Local LLM scan finished")

    def _on_local_model_selected(self, index: int):
        if index < 0 or index >= len(self.local_llm_choices):
            return
        _display, provider, model = self.local_llm_choices[index]
        p_idx = self.cmb_provider.findText(provider)
        if p_idx >= 0:
            self.cmb_provider.setCurrentIndex(p_idx)
        self.edt_model.setText(model)
        self._log(f"Selected local model: {provider} / {model}")

    def _on_provider_changed(self, provider: str):
        model = self._provider_cfg(provider).get("model", "").strip()
        if provider == "ollama":
            installed = self._list_ollama_models()
            if installed:
                if model and model in installed:
                    self.edt_model.setText(model)
                else:
                    self.edt_model.setText(installed[0])
            else:
                self.edt_model.setText(model or "llama3.1:8b")
        else:
            self.edt_model.setText(model or "")

    def _list_ollama_models(self) -> List[str]:
        base = self._provider_cfg("ollama").get("base_url", "http://localhost:11434").rstrip("/")
        url = f"{base}/api/tags"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code >= 400:
                return []
            data = res.json()
            models = []
            for m in data.get("models", []):
                name = str(m.get("name", "")).strip()
                if name:
                    models.append(name)
            return models
        except Exception:
            return []

    def _pick_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "Select root folder")
        if selected:
            self.edt_root.setText(selected)

    def _selected_extensions(self) -> List[str]:
        return [ext for ext, chk in self.ext_checks.items() if chk.isChecked()]

    def _scan(self):
        root_txt = self.edt_root.text().strip()
        if not root_txt:
            QMessageBox.information(self, "Missing folder", "Select a folder first")
            return

        root = Path(root_txt)
        if not root.exists() or not root.is_dir():
            QMessageBox.critical(self, "Invalid folder", f"Invalid folder: {root}")
            return

        self.current_root = root
        exts = self._selected_extensions()
        if not exts:
            QMessageBox.information(self, "Missing extensions", "Select at least one extension")
            return

        self.btn_scan.setEnabled(False)
        self.btn_analyze.setEnabled(False)
        self._set_busy(True, "Scanning files...")
        self._log(f"[{datetime.now().isoformat(timespec='seconds')}] Scan started...")

        self.scan_worker = ScanWorker(root, exts)
        self.scan_worker.scan_done.connect(self._on_scan_done)
        self.scan_worker.scan_error.connect(self._on_scan_error)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_done(self, files):
        if not self.current_root:
            return
        self.tree.clear()
        for item in files:
            rel = item.path.relative_to(self.current_root)
            node = QTreeWidgetItem([str(rel), item.extension, str(item.size)])
            node.setData(0, Qt.UserRole, str(item.path))
            self.tree.addTopLevelItem(node)
        self._log(f"[{datetime.now().isoformat(timespec='seconds')}] Scan completed: {len(files)} files")

    def _on_scan_error(self, message: str):
        self._log(f"Scan error: {message}")
        QMessageBox.warning(self, "Scan error", message)

    def _on_scan_finished(self):
        self.btn_scan.setEnabled(True)
        self.btn_analyze.setEnabled(True)
        self._set_busy(False, "Scan finished")
        self.scan_worker = None

    def _on_tree_clicked(self, item: QTreeWidgetItem, _col: int):
        full = item.data(0, Qt.UserRole)
        if not full:
            return
        path = Path(full)
        self.current_file = path
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.txt_source.setPlainText(f"Read error: {e}")
            return
        self.txt_source.setPlainText(content)

    def _selected_paths(self) -> List[Path]:
        paths: List[Path] = []
        for item in self.tree.selectedItems():
            full = item.data(0, Qt.UserRole)
            if not full:
                continue
            path = Path(full)
            if path.exists() and path.is_file():
                paths.append(path)
        if not paths and self.current_file and self.current_file.exists():
            paths.append(self.current_file)
        unique = []
        seen = set()
        for p in paths:
            s = str(p)
            if s not in seen:
                unique.append(p)
                seen.add(s)
        return unique

    def _help_explain_selected_rag(self):
        if self.analysis_worker and self.analysis_worker.isRunning():
            QMessageBox.information(self, "Busy", "Another analysis is already running")
            return

        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "No file", "Select one or more files first")
            return

        provider = self.cmb_provider.currentText()
        model = self.edt_model.text().strip() or "llama3.1:8b"

        chunks: List[str] = []
        budget = 12000
        used = 0
        for p in paths[:5]:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            snippet = text[:4000]
            block = f"\n--- FILE: {p.name} ({p}) ---\n{snippet}\n"
            if used + len(block) > budget:
                break
            chunks.append(block)
            used += len(block)

        if not chunks:
            QMessageBox.warning(self, "RAG", "Unable to read selected files")
            return

        prompt = (
            "You are an expert software teacher. Convert the following code context into natural language. "
            "Provide: purpose, architecture, key functions/classes, risks, and practical explanation for non-developers."
            " Keep it structured and concise.\n"
            + "\n".join(chunks)
        )

        self.btn_analyze.setEnabled(False)
        self._set_busy(True, "Running RAG natural-language explanation...")
        self._log("Starting RAG help explanation...")

        self.analysis_worker = AnalysisWorker(
            provider,
            model,
            prompt,
            self.config,
            api_key_override=self.edt_api_key.text().strip(),
            chunk_timeout=self.spn_chunk_timeout.value(),
        )
        self.analysis_worker.analysis_done.connect(self._on_rag_done)
        self.analysis_worker.analysis_error.connect(self._on_analysis_error)
        self.analysis_worker.analysis_progress.connect(lambda msg: self._set_busy(True, msg))
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _on_rag_done(self, out: str):
        self.txt_output.setPlainText(f"{self._output_header()}\n{out}")
        self._log("RAG explanation completed")

    def _estimate_selected(self):
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "No file", "Select one or more files first")
            return

        total_bytes = 0
        total_chars = 0
        total_lines = 0
        total_functions = 0
        total_classes = 0
        complexity_points = 0

        complexity_regex = re.compile(r"\b(if|elif|for|while|except|case|catch|switch|&&|\|\|)\b")

        for path in paths:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass

            total_chars += len(text)
            total_lines += len(text.splitlines())

            if path.suffix.lower() == ".py":
                total_functions += text.count("\ndef ") + (1 if text.startswith("def ") else 0)
                total_classes += text.count("\nclass ") + (1 if text.startswith("class ") else 0)
            else:
                total_functions += len(re.findall(r"\bfunction\b|=>|\bfunc\b|\bdef\b", text))
                total_classes += len(re.findall(r"\bclass\b", text))

            complexity_points += len(complexity_regex.findall(text))

        est_tokens = math.ceil(total_chars / 4)
        avg_lines_per_file = round(total_lines / max(len(paths), 1), 1)

        if est_tokens < 1500 and complexity_points < 40:
            routing = "Suggested LLM: local small/medium model"
        elif est_tokens < 6000 and complexity_points < 120:
            routing = "Suggested LLM: local 7B/8B strong model or cloud mid-tier"
        else:
            routing = "Suggested LLM: cloud high-context model"

        self._log("=" * 60)
        self._log(f"Estimate on {len(paths)} selected file(s)")
        self._log(f"Total size: {total_bytes} bytes")
        self._log(f"Total chars: {total_chars}")
        self._log(f"Total lines: {total_lines} (avg {avg_lines_per_file}/file)")
        self._log(f"Functions: {total_functions} | Classes: {total_classes}")
        self._log(f"Complexity points: {complexity_points}")
        self._log(f"Estimated tokens: ~{est_tokens}")
        self._log(routing)
        self._log("=" * 60)

    def _analyze_selected(self):
        if not self.current_file:
            QMessageBox.information(self, "No file", "Select a file first")
            return

        provider = self.cmb_provider.currentText()
        model = self.edt_model.text().strip() or "llama3.1:8b"
        depth = self.cmb_analysis_depth.currentText().strip().lower()
        depth_factor = {"fast": 0.6, "balanced": 1.0, "deep": 1.5}.get(depth, 1.0)
        base_chars = 2500 if provider == "ollama" else 8000
        max_source_chars = int(max(1200, min(20000, base_chars * depth_factor)))
        if provider in {"openrouter", "openai_compatible"}:
            api_key_ui = self.edt_api_key.text().strip()
            provider_cfg = self._provider_cfg(provider)
            env_name = provider_cfg.get("api_key_env", "")
            import os

            if not api_key_ui and (not env_name or not os.getenv(env_name, "")):
                QMessageBox.warning(
                    self,
                    "Missing API key",
                    "Insert API key in UI or set the configured environment variable before Analyze.",
                )
                return
            if api_key_ui and len(api_key_ui) < 20:
                QMessageBox.warning(
                    self,
                    "Invalid API key",
                    "The provided API key looks too short. Verify and retry.",
                )
                return

        src = self.txt_source.toPlainText()[:max_source_chars]
        prompt = (
            "Analyze this source code and provide: purpose, key components, risks, improvement suggestions.\n\n"
            f"Analysis depth: {depth.title()}\n"
            f"File: {self.current_file}\n\n"
            f"{src}"
        )
        if len(self.txt_source.toPlainText()) > max_source_chars:
            self._log(
                f"Input truncated to {max_source_chars} chars (depth={depth}, provider={provider})"
            )

        self.btn_analyze.setEnabled(False)
        self._set_busy(True, "Running LLM analysis...")
        self._log(f"[{datetime.now().isoformat(timespec='seconds')}] Analysis started...")

        self.analysis_worker = AnalysisWorker(
            provider,
            model,
            prompt,
            self.config,
            api_key_override=self.edt_api_key.text().strip(),
            chunk_timeout=self.spn_chunk_timeout.value(),
        )
        self.analysis_worker.analysis_done.connect(self._on_analysis_done)
        self.analysis_worker.analysis_error.connect(self._on_analysis_error)
        self.analysis_worker.analysis_progress.connect(lambda msg: self._set_busy(True, msg))
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _on_analysis_done(self, out: str):
        self.txt_output.setPlainText(f"{self._output_header()}\n{out}")
        self._log("Analysis completed")

    def _on_analysis_error(self, message: str):
        self._log(f"LLM error: {message}")
        QMessageBox.warning(self, "Analysis error", message)
        provider = self.cmb_provider.currentText()
        if provider == "ollama":
            installed = self._list_ollama_models()
            if installed:
                self._log(f"Installed Ollama models: {', '.join(installed[:8])}")

    def _on_analysis_finished(self):
        self.btn_analyze.setEnabled(True)
        self._set_busy(False, "Analysis finished")
        self.analysis_worker = None

    def _hash_selected(self):
        if not self.current_file:
            QMessageBox.information(self, "No file", "Select a file first")
            return
        try:
            digest = compute_sha256(self.current_file)
        except OSError as e:
            self._log(f"Hash error: {e}")
            return
        self._log(f"SHA256 {self.current_file.name}: {digest}")

    def _log(self, message: str):
        current = self.txt_output.toPlainText().strip()
        header = self._output_header()
        if not current:
            current = header
        if header not in current:
            current = f"{header}\n{current}"
        merged = f"{current}\n{message}".strip()
        self.txt_output.setPlainText(merged)


def run_gui() -> None:
    app = QApplication([])
    win = CodeScanWindow()
    win.show()
    app.exec_()
