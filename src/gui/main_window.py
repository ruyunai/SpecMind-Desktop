"""三栏主窗口 - 连接 Orchestrator 信号到三栏面板。

布局：
┌──────────────┬────────────────────────┬──────────────┐
│  左栏：资产库  │  中栏：工作区三 Tab       │  右栏：画布    │
│              │  需求输入 → PRD → 附件    │  节点状态     │
│              │                        │  实时日志     │
└──────────────┴────────────────────────┴──────────────┘

信号流：
WorkspacePanel.execute_requested → MainWindow._start_workflow
→ WorkflowOrchestrator (QThread)
  → node_started  → WorkflowCanvasPanel.on_node_started
  → node_finished → WorkflowCanvasPanel.on_node_finished
  → log_message   → WorkflowCanvasPanel.on_log_message
  → workflow_blocked → WorkspacePanel.on_workflow_blocked + Canvas
  → workflow_complete → WorkspacePanel.on_workflow_complete + Canvas
"""
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QMenuBar,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from gui.widgets.asset_library import AssetLibraryPanel
from gui.widgets.workspace import WorkspacePanel
from gui.widgets.workflow_canvas import WorkflowCanvasPanel
from core.orchestrator import WorkflowOrchestrator
from core.logger import setup_logger

logger = setup_logger("specmind.main")


class MainWindow(QMainWindow):
    """SpecMind Desktop 三栏主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SpecMind Desktop - PRD 标准化产出平台")
        self.resize(1600, 900)
        self.setMinimumSize(1280, 720)
        self._orchestrator: WorkflowOrchestrator | None = None

        self._init_ui()
        self._init_menubar()
        self._init_statusbar()
        self._connect_signals()

    def _init_ui(self) -> None:
        """初始化三栏布局。"""
        splitter = QSplitter(Qt.Horizontal)

        self.asset_panel = AssetLibraryPanel()
        self.workspace_panel = WorkspacePanel()
        self.canvas_panel = WorkflowCanvasPanel()

        splitter.addWidget(self.asset_panel)
        splitter.addWidget(self.workspace_panel)
        splitter.addWidget(self.canvas_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 950, 350])

        self.setCentralWidget(splitter)

    def _init_menubar(self) -> None:
        """初始化菜单栏。"""
        menubar = self.menuBar()

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        model_config_action = QAction("模型配置", self)
        model_config_action.setShortcut("Ctrl+,")
        model_config_action.setStatusTip("可视化配置各 Agent 的 LLM API Key/模型/Base URL")
        model_config_action.triggered.connect(self._open_model_config)
        settings_menu.addAction(model_config_action)
        settings_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        settings_menu.addAction(exit_action)

    def _open_model_config(self) -> None:
        """打开模型配置对话框。"""
        from gui.dialogs.model_config_dialog import ModelConfigDialog
        dialog = ModelConfigDialog(self)
        dialog.exec()

    def _init_statusbar(self) -> None:
        """初始化状态栏。"""
        status = self.statusBar()
        status.showMessage("就绪 - 在中栏输入需求后点击「开始执行」（Ctrl+, 打开模型配置）")

        # 延迟检测知识库是否为空（避免阻塞 UI 初始化）
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._check_empty_kb)

    def _check_empty_kb(self) -> None:
        """检测知识库是否为空，若为空则提示用户上传文档。"""
        try:
            from storage.chroma_store import ChromaStore
            from storage.schema import AssetCategory
            store = ChromaStore()
            empty_categories = []
            for cat in (AssetCategory.STANDARD_FEATURE, AssetCategory.REGULATION, AssetCategory.CONTRACT_TEMPLATE):
                if store.count(cat) == 0:
                    cat_names = {
                        AssetCategory.STANDARD_FEATURE: "标准功能清单",
                        AssetCategory.REGULATION: "法规库",
                        AssetCategory.CONTRACT_TEMPLATE: "合同模板库",
                    }
                    empty_categories.append(cat_names.get(cat, cat.value))

            if len(empty_categories) == 3:
                self.statusBar().showMessage(
                    "⚠ 知识库为空！请在左栏「企业资产库」点击「上传」按钮，上传企业文档（支持 Word/PDF/TXT）以启用智能检索"
                )
            elif empty_categories:
                self.statusBar().showMessage(
                    f"⚠ 以下知识库为空: {', '.join(empty_categories)}。建议上传对应文档以提升 Agent 分析质量"
                )
        except Exception:
            pass  # ChromaDB 未初始化时不强行报错

    def _connect_signals(self) -> None:
        """连接信号。"""
        self.workspace_panel.execute_requested.connect(self._start_workflow)

    def _start_workflow(self, raw_input: str, client_name: str) -> None:
        """启动工作流。"""
        if self._orchestrator and self._orchestrator.isRunning():
            logger.warning("[Main] 工作流正在执行中，忽略重复请求")
            return

        logger.info("[Main] 启动工作流, 输入长度=%d", len(raw_input))

        # 重置画布
        self.canvas_panel.reset_all()

        # 状态栏更新
        self.statusBar().showMessage("工作流执行中...")

        # 创建并启动 Orchestrator
        self._orchestrator = WorkflowOrchestrator(raw_input, client_name)

        # 连接信号
        self._orchestrator.node_started.connect(self.canvas_panel.on_node_started)
        self._orchestrator.node_finished.connect(self.canvas_panel.on_node_finished)
        self._orchestrator.progress_updated.connect(self._on_progress_updated)
        self._orchestrator.log_message.connect(self.canvas_panel.on_log_message)
        self._orchestrator.workflow_blocked.connect(self._on_workflow_blocked)
        self._orchestrator.workflow_complete.connect(self._on_workflow_complete)

        self._orchestrator.start()

    def _on_progress_updated(self, step: int, total: int, message: str) -> None:
        """更新状态栏进度。"""
        percent = int(step / total * 100) if total > 0 else 0
        self.statusBar().showMessage(f"⏳ 工作流执行中... {percent}% | {message}")
        self.workspace_panel.on_progress_updated(step, total, message)

    def _on_workflow_blocked(self, reason: str, state: dict) -> None:
        """工作流被阻断 - 弹出 Interrupt 确认对话框。"""
        logger.warning("[Main] 工作流阻断: %s", reason)
        self.canvas_panel.on_workflow_blocked(reason)
        self.workspace_panel.on_workflow_blocked(reason)
        self.statusBar().showMessage(f"⛔ 工作流阻断: {reason}")

        # 展示 Legal 风险详情
        issues = state.get("legal_issues", [])
        issues_text = ""
        for i, issue in enumerate(issues, 1):
            issues_text += f"  {i}. {issue.get('law', '')}\n"
            issues_text += f"     问题: {issue.get('issue', '')}\n"
            issues_text += f"     建议: {issue.get('suggestion', '')}\n\n"

        # 弹出 Interrupt 确认对话框（确认/拒绝）
        reply = QMessageBox.question(
            self,
            "⛔ 高风险阻断 - Interrupt 人工确认",
            f"工作流被阻断！\n\n"
            f"原因：{reason}\n\n"
            f"Legal Agent 检测到以下合规问题：\n{issues_text}"
            f"是否强制放行继续生成 PRD？\n\n"
            f"⚠ Legal Agent 为辅助预检工具，不构成正式法律意见\n"
            f"⚠ 强制放行需自行承担合规风险",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            logger.info("[Main] 用户确认放行，继续执行 resume 图")
            self.statusBar().showMessage("用户确认放行，继续执行...")
            self.canvas_panel.reset_blocked_nodes()
            self._orchestrator.confirm_resume()
        else:
            logger.info("[Main] 用户拒绝放行，工作流终止")
            self._orchestrator.reject_resume()

    def _on_workflow_complete(self, state: dict) -> None:
        """工作流完成。"""
        logger.info("[Main] 工作流完成, 节点数=%d", len(state.get("audit_snapshots", [])))
        self.canvas_panel.on_workflow_complete()
        self.workspace_panel.on_workflow_complete(state)
        self.statusBar().showMessage("✅ 工作流完成 - PRD 已生成")

    def closeEvent(self, event) -> None:
        """窗口关闭时清理线程。

        三层终止策略：
        1. cancel() 设置 _cancel_flag + 解除 _confirm_event 阻塞，让 stream 循环正常退出
        2. wait(3000) 等待线程自然结束
        3. terminate() 强制终止（兜底，仅在自然退出失败时使用）
        """
        if self._orchestrator and self._orchestrator.isRunning():
            self._orchestrator.cancel()  # 解除 Interrupt 阻塞 + 设置 cancel flag
            self._orchestrator.wait(3000)
            if self._orchestrator.isRunning():
                logger.warning("[Main] 线程未自然退出，强制 terminate")
                self._orchestrator.terminate()
                self._orchestrator.wait(1000)
        event.accept()
