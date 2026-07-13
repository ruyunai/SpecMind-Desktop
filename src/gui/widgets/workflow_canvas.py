"""右栏：LangGraph 工作流动态画布。

实时展示：
- 7 Agent 节点状态（待执行/执行中/完成/阻断/跳过）
- Interrupt 节点高亮
- 节点间数据流向

接入 Orchestrator 信号，实时更新节点颜色。
"""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QPushButton,
    QTextBrowser,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush


# 节点定义（按执行顺序）
NODE_DEFINITIONS = [
    ("sar_agent", "SAR Agent", "需求清洗"),
    ("legal_agent", "Legal Agent", "合规预检"),
    ("interrupt", "⚠ Interrupt", "高风险确认"),
    ("pm_agent", "PM Agent", "PRD 生成"),
    ("commercial_agent", "Commercial Agent", "双报价"),
    ("contract_agent", "Contract Agent", "合同比对"),
    ("review_agent", "Tech/Design/QA", "多维评审"),
    ("planner_agent", "Planner Agent", "交付计划"),
]

# 状态颜色
STATUS_COLORS = {
    "待执行": QColor("#6c7086"),    # 灰色
    "执行中": QColor("#89b4fa"),    # 蓝色
    "完成": QColor("#a6e3a1"),      # 绿色
    "阻断": QColor("#f38ba8"),      # 红色
    "跳过": QColor("#45475a"),      # 暗灰
}


class WorkflowCanvasPanel(QWidget):
    """右栏 LangGraph 工作流画布。"""

    def __init__(self) -> None:
        super().__init__()
        self._node_items: dict[str, QTreeWidgetItem] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化工作流节点列表。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("LangGraph 工作流")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.block_summary = QLabel("")
        self.block_summary.setObjectName("blockSummary")
        self.block_summary.setWordWrap(True)
        self.block_summary.setVisible(False)
        layout.addWidget(self.block_summary)

        # 拓扑图预览区
        diagram_label = QLabel("工作流拓扑")
        diagram_label.setObjectName("panelTitle")
        layout.addWidget(diagram_label)

        self.diagram_view = QTextBrowser()
        self.diagram_view.setMaximumHeight(160)
        self.diagram_view.setOpenExternalLinks(False)
        layout.addWidget(self.diagram_view)
        self._render_diagram()

        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["节点", "状态"])
        self.node_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.node_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        for node_key, node_name, desc in NODE_DEFINITIONS:
            item = QTreeWidgetItem([f"{node_name}\n{desc}", "待执行"])
            item.setData(0, Qt.UserRole, node_key)
            self._set_item_color(item, "待执行")
            self._node_items[node_key] = item
            self.node_tree.addTopLevelItem(item)

        layout.addWidget(self.node_tree)

        # 日志区域
        log_label = QLabel("实时日志")
        log_label.setObjectName("panelTitle")
        layout.addWidget(log_label)

        from PySide6.QtWidgets import QPlainTextEdit
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        self.log_view.setObjectName("logView")
        layout.addWidget(self.log_view)

    def _set_item_color(self, item: QTreeWidgetItem, status: str) -> None:
        """设置节点状态颜色。"""
        color = STATUS_COLORS.get(status, STATUS_COLORS["待执行"])
        item.setText(1, status)
        for col in range(2):
            item.setForeground(col, QBrush(color))

    def _render_diagram(self) -> None:
        """渲染工作流拓扑图（HTML + 实时状态颜色 + 图例）。"""
        # 节点显示名到 node_key 的映射
        name_to_key = {
            "SAR Agent": "sar_agent",
            "Legal Agent": "legal_agent",
            "Interrupt": "interrupt",
            "PM Agent": "pm_agent",
            "Commercial": "commercial_agent",
            "Contract": "contract_agent",
            "Review": "review_agent",
            "Planner Agent": "planner_agent",
        }

        def _node(name: str) -> str:
            """根据节点当前状态返回带颜色的 HTML 节点名。"""
            key = name_to_key.get(name, "")
            item = self._node_items.get(key)
            status = item.text(1) if item else "待执行"
            color = STATUS_COLORS.get(status, STATUS_COLORS["待执行"]).name()
            return f"<span style='color:{color};'>{name}</span>"

        html = [
            "<html><body style='font-family: Consolas, monospace; font-size: 13px; color: #cdd6f4;'>",
            "<pre style='margin:0; line-height:1.4;'>",
            f"{_node('SAR Agent')}",
            "   ↓",
            f"{_node('Legal Agent')}",
            "   ↓ 高风险",
            f"{_node('Interrupt')}",
            "   ↓ 低风险",
            f"{_node('PM Agent')}",
            "   ↓",
            f" {_node('Commercial')}  {_node('Contract')}  {_node('Review')}",
            "   ↓           ↓         ↓",
            f"{_node('Planner Agent')}",
            "</pre>",
            "<div style='margin-top:6px;'>图例: ",
        ]
        for status, color in STATUS_COLORS.items():
            hex_color = color.name()
            html.append(f"<span style='color:{hex_color};'>●</span> {status} ")
        html.append("</div></body></html>")

        self.diagram_view.setHtml("".join(html))

    def on_node_started(self, node_key: str) -> None:
        """节点开始执行 - 蓝色高亮。"""
        item = self._node_items.get(node_key)
        if item:
            self._set_item_color(item, "执行中")
        self._render_diagram()

    def on_node_finished(self, node_key: str) -> None:
        """节点执行完成 - 绿色。"""
        item = self._node_items.get(node_key)
        if item:
            self._set_item_color(item, "完成")
            # Interrupt 节点跟随 Legal 状态
            if node_key == "legal_agent":
                # Legal 完成后 Interrupt 也标记完成（暂未阻断）
                interrupt_item = self._node_items.get("interrupt")
                if interrupt_item:
                    self._set_item_color(interrupt_item, "完成")
        self._render_diagram()

    def on_workflow_blocked(self, reason: str) -> None:
        """工作流被阻断 - Legal/Interrupt 红色，后续节点灰色跳过，显示原因摘要。"""
        self.block_summary.setText(f"⛔ 工作流阻断：{reason}")
        self.block_summary.setVisible(True)

        legal_item = self._node_items.get("legal_agent")
        if legal_item:
            self._set_item_color(legal_item, "阻断")
        interrupt_item = self._node_items.get("interrupt")
        if interrupt_item:
            self._set_item_color(interrupt_item, "阻断")

        # 后续节点标记为跳过
        blocked = False
        for node_key, _, _ in NODE_DEFINITIONS:
            if blocked:
                item = self._node_items.get(node_key)
                if item and item.text(1) == "待执行":
                    self._set_item_color(item, "跳过")
            if node_key == "interrupt":
                blocked = True
        self._render_diagram()

    def on_workflow_complete(self) -> None:
        """工作流完成 - 确保所有节点标记完成。"""
        for node_key, _, _ in NODE_DEFINITIONS:
            item = self._node_items.get(node_key)
            if item and item.text(1) == "待执行":
                self._set_item_color(item, "完成")
        self._render_diagram()

    def on_log_message(self, msg: str) -> None:
        """追加日志消息。"""
        self.log_view.appendPlainText(msg)

    def reset_all(self) -> None:
        """重置所有节点为待执行。"""
        for node_key, _, _ in NODE_DEFINITIONS:
            item = self._node_items.get(node_key)
            if item:
                self._set_item_color(item, "待执行")
        self.block_summary.clear()
        self.block_summary.setVisible(False)
        self.log_view.clear()
        self._render_diagram()

    def reset_blocked_nodes(self) -> None:
        """确认放行后，重置被阻断的后续节点为待执行。"""
        self.block_summary.clear()
        self.block_summary.setVisible(False)

        blocked_found = False
        for node_key, _, _ in NODE_DEFINITIONS:
            if blocked_found:
                item = self._node_items.get(node_key)
                if item and item.text(1) in ("跳过", "阻断"):
                    self._set_item_color(item, "待执行")
            if node_key == "interrupt":
                # Interrupt 节点改为完成（已确认）
                item = self._node_items.get("interrupt")
                if item:
                    self._set_item_color(item, "完成")
                blocked_found = True
        self._render_diagram()
