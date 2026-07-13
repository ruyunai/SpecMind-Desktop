"""知识库上传对话框 — 选择文档 + 分类 → 自动解析/分块/嵌入/入库。

支持格式：.docx / .pdf / .txt / .json
分类映射：
  - 法规库     → regulation (按法条分块)
  - 合同模板   → contract   (按条款分块)
  - 历史 PRD   → prd        (按模块分块)
  - 标准功能   → feature    (通用分块)
  - 其他       → generic    (通用分块)
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFileDialog,
    QProgressBar,
    QTextEdit,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from gui.services.upload_service import ingest_document, CATEGORY_MAP


class _UploadWorker(QObject):
    """后台上传 Worker - 在 QThread 中执行 ingest_document。

    Signals:
        finished(IngestResult): 上传完成（含成功/失败信息，错误看 result.errors）
        error(str): 上传过程抛出未捕获异常
    """
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, file_path: str, category: str, doc_name: str | None) -> None:
        super().__init__()
        self._file_path = file_path
        self._category = category
        self._doc_name = doc_name

    def run(self) -> None:
        """执行上传（在后台线程运行）。"""
        try:
            result = ingest_document(self._file_path, self._category, self._doc_name)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")


class UploadDialog(QDialog):
    """知识库文档上传对话框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("上传文档到知识库")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self._file_path: str = ""
        self._worker_thread: QThread | None = None
        self._worker: _UploadWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 文件选择 ----
        file_group = QGroupBox("选择文档")
        file_layout = QVBoxLayout(file_group)

        file_row = QHBoxLayout()
        self._file_edit = QLineEdit()
        self._file_edit.setReadOnly(True)
        self._file_edit.setPlaceholderText("点击浏览选择文档...")
        file_row.addWidget(self._file_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(browse_btn)
        file_layout.addLayout(file_row)

        # 文件名
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("文档名称:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("留空则使用文件名")
        name_row.addWidget(self._name_edit)
        file_layout.addLayout(name_row)

        layout.addWidget(file_group)

        # ---- 分类选择 ----
        cat_group = QGroupBox("文档分类")
        cat_layout = QHBoxLayout(cat_group)
        cat_layout.addWidget(QLabel("分类:"))
        self._category_combo = QComboBox()
        self._category_combo.addItems([
            "法规库 (regulation)",
            "合同模板 (contract)",
            "历史 PRD / 需求文档 (prd)",
            "标准功能清单 (feature)",
            "其他通用文档 (generic)",
        ])
        cat_layout.addWidget(self._category_combo)
        cat_layout.addStretch()
        layout.addWidget(cat_group)

        # ---- 进度 ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # 不确定进度
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # ---- 日志 ----
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(120)
        self._log_text.setPlaceholderText("上传日志...")
        layout.addWidget(self._log_text)

        # ---- 按钮 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._upload_btn = QPushButton("上传到知识库")
        self._upload_btn.setMinimumWidth(140)
        self._upload_btn.clicked.connect(self._on_upload)
        btn_row.addWidget(self._upload_btn)

        cancel_btn = QPushButton("关闭")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_browse(self) -> None:
        """浏览选择文件。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "文档文件 (*.docx *.pdf *.txt *.json);;所有文件 (*.*)",
        )
        if file_path:
            self._file_path = file_path
            self._file_edit.setText(file_path)
            # 自动填充文件名
            import os
            name = os.path.basename(file_path)
            if not self._name_edit.text():
                self._name_edit.setText(name)

    def _on_upload(self) -> None:
        """执行上传 - 后台线程处理避免 UI 冻结。"""
        if not self._file_path:
            QMessageBox.warning(self, "提示", "请先选择要上传的文档。")
            return

        # 防止并发重复上传
        if self._worker_thread and self._worker_thread.isRunning():
            return

        # 解析分类
        cat_text = self._category_combo.currentText()
        # 从 "法规库 (regulation)" 中提取 regulation
        if "(" in cat_text and ")" in cat_text:
            category = cat_text.split("(")[1].replace(")", "")
        else:
            category = "generic"

        doc_name = self._name_edit.text().strip() or None

        # UI 进入上传状态
        self._upload_btn.setEnabled(False)
        self._progress_bar.show()
        self._log_text.clear()
        self._append_log(f"解析文档: {self._file_path}")
        self._append_log(f"分类: {category}, 名称: {doc_name or '(自动)'}")
        self._append_log("正在分块 + 向量化 + 入库...（后台执行，UI 可响应）")

        # 创建后台线程执行上传
        self._worker = _UploadWorker(self._file_path, category, doc_name)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_upload_finished)
        self._worker.error.connect(self._on_upload_error)
        # 线程结束后清理引用
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_upload_finished(self, result) -> None:
        """上传完成回调（主线程执行）。"""
        # 优雅停止线程
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(2000)

        self._progress_bar.hide()
        self._upload_btn.setEnabled(True)

        if result.errors:
            self._append_log(f"错误: {result.errors}")
            QMessageBox.critical(self, "上传失败", f"上传失败: {result.errors[0]}")
            return

        self._append_log(f"完成! 总共 {result.total_chunks} 个分块")
        self._append_log(f"  ✅ 新增: {result.added} 条")
        if result.skipped:
            self._append_log(f"  ⏭ 跳过: {result.skipped} 条（已存在）")

        QMessageBox.information(
            self,
            "上传完成",
            f"文档「{result.doc_name}」已入库\n"
            f"共 {result.total_chunks} 个分块，新增 {result.added} 条"
            + (f"，跳过 {result.skipped} 条重复" if result.skipped else ""),
        )

        self.accept()

    def _on_upload_error(self, err_msg: str) -> None:
        """上传异常回调（主线程执行）。"""
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(2000)

        self._progress_bar.hide()
        self._upload_btn.setEnabled(True)
        self._append_log(f"❌ 异常: {err_msg}")
        QMessageBox.critical(self, "上传异常", f"上传过程异常: {err_msg}")

    def closeEvent(self, event) -> None:
        """关闭对话框时清理后台线程。"""
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        event.accept()

    def _append_log(self, msg: str) -> None:
        self._log_text.append(msg)
