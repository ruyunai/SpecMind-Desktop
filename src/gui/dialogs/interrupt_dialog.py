"""Interrupt 高风险阻断确认对话框。

QMessageBox 在内容过长时无法滚动，按钮会被挤出可视区域。
本对话框用 QScrollArea 包裹内容，底部固定按钮，支持鼠标滚轮滚动。
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QFrame,
)
from PySide6.QtCore import Qt


class InterruptConfirmDialog(QDialog):
    """高风险阻断确认对话框（可滚动 + 固定底部按钮）。

    布局：
    ┌──────────────────────────────┐
    │ ⛔ 高风险阻断标题（固定）       │
    │ 原因：xxx（固定）              │
    ├──────────────────────────────┤
    │ ┌──────────────────────────┐ │
    │ │ Legal 合规问题详情        │ │
    │ │ （QScrollArea 可滚动）    │ │
    │ │ 1. 法条...               │ │
    │ │    问题...               │ │
    │ │    建议...               │ │
    │ └──────────────────────────┘ │
    ├──────────────────────────────┤
    │ ⚠ 辅助预检声明（固定）         │
    │ [拒绝放行]      [强制放行]    │
    └──────────────────────────────┘
    """

    def __init__(
        self,
        reason: str,
        issues: list,
        parent=None,
    ) -> None:
        """初始化阻断确认对话框。

        Args:
            reason: 阻断原因
            issues: Legal Agent 识别的合规问题列表
            parent: 父窗口
        """
        super().__init__(parent)
        self._confirmed = False

        self.setWindowTitle("⛔ 高风险阻断 - Interrupt 人工确认")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMaximumWidth(800)
        self.setMinimumHeight(400)
        self.setMaximumHeight(700)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # === 标题区（固定） ===
        title = QLabel("⛔ 工作流被阻断！")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        layout.addWidget(title)

        reason_label = QLabel(f"原因：{reason}")
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet("font-size: 13px; color: #ffa502;")
        layout.addWidget(reason_label)

        # === 分割线 ===
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)

        # === 合规问题详情（可滚动） ===
        detail_header = QLabel("Legal Agent 检测到以下合规问题：")
        detail_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(detail_header)

        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setMinimumHeight(150)
        detail_text.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas, 'Microsoft YaHei'; font-size: 12px; }"
        )
        issues_text = ""
        for i, issue in enumerate(issues, 1):
            law = issue.get("law", "未知") if isinstance(issue, dict) else str(issue)
            problem = issue.get("issue", "") if isinstance(issue, dict) else ""
            suggestion = issue.get("suggestion", "") if isinstance(issue, dict) else ""
            issues_text += f"[{i}] {law}\n"
            issues_text += f"    问题: {problem}\n"
            issues_text += f"    建议: {suggestion}\n\n"
        detail_text.setPlainText(issues_text.strip() or "（无详细信息）")
        layout.addWidget(detail_text, stretch=1)

        # === 声明区（固定） ===
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        layout.addWidget(separator2)

        warning = QLabel(
            "⚠ Legal Agent 为辅助预检工具，不构成正式法律意见\n"
            "⚠ 强制放行需自行承担合规风险"
        )
        warning.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        question = QLabel("是否强制放行继续生成 PRD？")
        question.setStyleSheet("font-size: 14px; font-weight: bold;")
        question.setAlignment(Qt.AlignCenter)
        layout.addWidget(question)

        # === 按钮区（固定底部） ===
        btn_layout = QHBoxLayout()

        reject_btn = QPushButton("✗ 拒绝放行（推荐）")
        reject_btn.setMinimumHeight(40)
        reject_btn.setStyleSheet(
            "QPushButton { background-color: #3c3c3c; color: #d4d4d4; "
            "font-size: 14px; border: 1px solid #555; border-radius: 4px; padding: 8px 24px; }"
            "QPushButton:hover { background-color: #4c4c4c; }"
        )
        reject_btn.clicked.connect(self._on_reject)

        confirm_btn = QPushButton("⚠ 强制放行")
        confirm_btn.setMinimumHeight(40)
        confirm_btn.setStyleSheet(
            "QPushButton { background-color: #8b0000; color: white; "
            "font-size: 14px; border: 1px solid #a00; border-radius: 4px; padding: 8px 24px; }"
            "QPushButton:hover { background-color: #a00000; }"
        )
        confirm_btn.clicked.connect(self._on_confirm)

        btn_layout.addStretch()
        btn_layout.addWidget(reject_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_confirm(self) -> None:
        """用户确认强制放行。"""
        self._confirmed = True
        self.accept()

    def _on_reject(self) -> None:
        """用户拒绝放行。"""
        self._confirmed = False
        self.reject()

    @property
    def confirmed(self) -> bool:
        """返回用户是否确认放行。"""
        return self._confirmed
