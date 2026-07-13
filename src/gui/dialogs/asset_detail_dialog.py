"""资产详情对话框。

显示资产的完整文本、来源、版本、分类等元数据。
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QGridLayout,
)
from PySide6.QtCore import Qt


class AssetDetailDialog(QDialog):
    """资产详情对话框。"""

    def __init__(self, data: dict, parent=None) -> None:
        """初始化详情对话框。

        Args:
            data: 资产数据字典，包含 category/source/version/text 等字段
            parent: 父窗口
        """
        super().__init__(parent)
        self._data = data
        self.setWindowTitle(f"资产详情 - {data.get('source', '未知来源')}")
        self.setMinimumSize(600, 450)
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI。"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 元信息网格
        meta_group = QGridLayout()
        meta_group.setColumnStretch(1, 1)
        meta_group.addWidget(QLabel("分类:"), 0, 0)
        meta_group.addWidget(QLabel(self._data.get("category", "-")), 0, 1)
        meta_group.addWidget(QLabel("来源:"), 1, 0)
        meta_group.addWidget(QLabel(self._data.get("source", "-")), 1, 1)
        meta_group.addWidget(QLabel("版本:"), 2, 0)
        meta_group.addWidget(QLabel(self._data.get("version", "-")), 2, 1)
        layout.addLayout(meta_group)

        # 正文
        layout.addWidget(QLabel("正文内容:"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(self._data.get("text", ""))
        layout.addWidget(self.text_edit)

        # 底部关闭按钮
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)
