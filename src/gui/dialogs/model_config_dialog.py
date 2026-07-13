"""模型配置对话框 - 可视化输入切换每个 Agent 的 LLM。

功能：
- 全局 API Key / Base URL 输入（加密存储）
- 7 个 Agent 各自的模型选择（下拉 + 自由输入）
- 每 Agent 可选独立 API Key / Base URL，或用全局
- 预设路由一键应用（混合/Qwen/DeepSeek/GLM）
- 保存后写入 config，运行时生效
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QGroupBox,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Qt

from core.config import (
    AppConfig,
    AGENT_KEYS,
    PRESET_ROUTING,
    COMMON_MODELS,
    reload_config,
)
from core.crypto import get_crypto


# Agent 中文名映射
AGENT_LABELS = {
    "sar": "SAR Agent（需求清洗）",
    "legal": "Legal Agent（合规预检）",
    "pm": "PM Agent（PRD 生成）",
    "commercial": "Commercial Agent（报价）",
    "contract": "Contract Agent（合同比对）",
    "review": "Tech/Design/QA（评审）",
    "planner": "Planner Agent（交付计划）",
}


class ModelConfigDialog(QDialog):
    """模型配置对话框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("模型配置 - 各 Agent LLM 可视化切换")
        self.resize(900, 600)
        self.config = AppConfig.load()
        self._init_ui()
        self._load_config()

    def _init_ui(self) -> None:
        """初始化界面。"""
        layout = QVBoxLayout(self)

        # 全局配置区
        global_group = QGroupBox("全局配置（默认所有 Agent 共用）")
        global_form = QFormLayout(global_group)
        self.global_key_input = QLineEdit()
        self.global_key_input.setEchoMode(QLineEdit.Password)
        self.global_key_input.setPlaceholderText("输入硅基流动 API Key（加密存储）")
        self.global_url_input = QLineEdit(self.config.global_base_url)
        self.global_url_input.setPlaceholderText("https://api.siliconflow.cn/v1")
        global_form.addRow("全局 API Key:", self.global_key_input)
        global_form.addRow("全局 Base URL:", self.global_url_input)
        layout.addWidget(global_group)

        # 预设路由按钮区
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("一键应用预设路由:"))
        for name in PRESET_ROUTING:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, n=name: self._apply_preset(n))
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        # Agent 配置表格
        agent_group = QGroupBox("各 Agent 模型配置（可独立设置 API Key/Base URL）")
        agent_layout = QVBoxLayout(agent_group)

        # 提示：模型可自定义输入
        tip_label = QLabel("提示：模型名称支持自由输入，可从下拉列表选择常用模型，也可直接输入任意模型名（如其他硅基流动模型/自建模型）")
        tip_label.setObjectName("tipLabel")
        tip_label.setWordWrap(True)
        agent_layout.addWidget(tip_label)

        self.table = QTableWidget(len(AGENT_KEYS), 5)
        self.table.setHorizontalHeaderLabels(
            ["Agent", "模型", "用全局Key", "独立 API Key", "独立 Base URL"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._fill_agent_rows()
        agent_layout.addWidget(self.table)
        layout.addWidget(agent_group)

        # 保存/取消
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("保存配置")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _fill_agent_rows(self) -> None:
        """填充表格行（控件）。"""
        for row, key in enumerate(AGENT_KEYS):
            # Agent 名称（只读）
            name_item = QTableWidgetItem(AGENT_LABELS.get(key, key))
            name_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 0, name_item)

            # 模型选择（可编辑下拉 + 自定义输入）
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.addItems(COMMON_MODELS)
            # 设置当前默认模型
            combo.setCurrentText(COMMON_MODELS[0])
            self.table.setCellWidget(row, 1, combo)

            # 用全局 Key 复选框
            check = QCheckBox()
            check.setChecked(True)
            check.stateChanged.connect(lambda state, r=row: self._on_toggle_global_key(r, state))
            self.table.setCellWidget(row, 2, check)

            # 独立 API Key
            key_input = QLineEdit()
            key_input.setEchoMode(QLineEdit.Password)
            key_input.setPlaceholderText("留空则用全局 Key")
            key_input.setEnabled(False)
            self.table.setCellWidget(row, 3, key_input)

            # 独立 Base URL
            url_input = QLineEdit()
            url_input.setPlaceholderText("留空则用全局 URL")
            self.table.setCellWidget(row, 4, url_input)

    def _on_toggle_global_key(self, row: int, state: int) -> None:
        """切换全局 Key 复选框时启用/禁用独立 Key 输入。"""
        self.table.cellWidget(row, 3).setEnabled(state != Qt.Checked)

    def _apply_preset(self, preset_name: str) -> None:
        """应用预设路由。"""
        preset = PRESET_ROUTING.get(preset_name, {})
        for row, key in enumerate(AGENT_KEYS):
            combo = self.table.cellWidget(row, 1)
            model = preset.get(key, "")
            idx = combo.findText(model)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(model)

    def _load_config(self) -> None:
        """从配置加载到界面。"""
        # 全局 Key（显示掩码，实际值留空让用户重新输入或保留）
        if self.config.global_api_key_enc:
            self.global_key_input.setPlaceholderText("已存储（加密），重新输入可覆盖")
        self.global_url_input.setText(self.config.global_base_url)

        # 各 Agent
        for row, key in enumerate(AGENT_KEYS):
            agent = self.config.agents.get(key)
            if not agent:
                continue
            combo = self.table.cellWidget(row, 1)
            idx = combo.findText(agent.model)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(agent.model)
            check = self.table.cellWidget(row, 2)
            check.setChecked(agent.use_global_key)
            key_input = self.table.cellWidget(row, 3)
            key_input.setEnabled(not agent.use_global_key)
            url_input = self.table.cellWidget(row, 4)
            url_input.setText(agent.base_url)

    def _on_save(self) -> None:
        """保存配置。"""
        # 全局
        new_key = self.global_key_input.text().strip()
        if new_key:
            self.config.set_global_api_key(new_key)
        self.config.global_base_url = self.global_url_input.text().strip() or self.config.global_base_url

        # 各 Agent
        for row, key in enumerate(AGENT_KEYS):
            combo = self.table.cellWidget(row, 1)
            check = self.table.cellWidget(row, 2)
            key_input = self.table.cellWidget(row, 3)
            url_input = self.table.cellWidget(row, 4)
            agent = self.config.agents.get(key)
            if agent is None:
                from core.config import AgentModelConfig
                agent = AgentModelConfig()
                self.config.agents[key] = agent
            agent.model = combo.currentText().strip()
            agent.use_global_key = check.isChecked()
            indep_key = key_input.text().strip()
            agent.api_key_enc = get_crypto().encrypt(indep_key) if indep_key else ""
            agent.base_url = url_input.text().strip()

        self.config.save()
        reload_config()
        QMessageBox.information(self, "保存成功", "模型配置已保存（API Key 已加密存储）。")
        self.accept()
