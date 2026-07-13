"""模型配置对话框 - LLM 模型路由 + 成本参数配置。

两个 Tab：
  Tab 1「LLM 模型」：全局 API Key / 预设路由 / 各 Agent 独立模型配置
  Tab 2「成本参数」：人天费率 / 功能工期 / 定制倍率 / 毛利率 / 维护费率
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
    QTabWidget,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt

from core.config import (
    AppConfig,
    AGENT_KEYS,
    PRESET_ROUTING,
    COMMON_MODELS,
    CostConfig,
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
    """模型配置对话框（LLM + 成本参数双 Tab）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("模型配置")
        self.resize(900, 650)
        self.config = AppConfig.load()
        self._init_ui()
        self._load_config()

    # ---- UI 初始化 ----

    def _init_ui(self) -> None:
        """初始化双 Tab 界面。"""
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: LLM 模型配置
        llm_tab = self._build_llm_tab()
        tabs.addTab(llm_tab, "LLM 模型")

        # Tab 2: 成本参数
        cost_tab = self._build_cost_tab()
        tabs.addTab(cost_tab, "成本参数")

        layout.addWidget(tabs)

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

    def _build_llm_tab(self) -> QWidget:
        """构建 LLM 模型 Tab。"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        tip_label = QLabel("提示：模型名称支持自由输入，可从下拉列表选择常用模型，也可直接输入任意模型名")
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

        return tab

    def _build_cost_tab(self) -> QWidget:
        """构建成本参数 Tab。"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 说明
        tip = QLabel(
            "调整以下参数将影响 Commercial Agent 的报价计算。\n"
            "不同公司/不同项目类型可灵活配置，保存后立即生效。"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # 成本参数表单
        cost_group = QGroupBox("报价成本参数")
        form = QFormLayout(cost_group)

        # 人天费率
        self.cost_pd_rate = QSpinBox()
        self.cost_pd_rate.setRange(500, 20000)
        self.cost_pd_rate.setSuffix(" 元/人天")
        self.cost_pd_rate.setValue(3000)
        form.addRow("人天费率:", self.cost_pd_rate)

        # 标准功能人天
        self.cost_days_std = QSpinBox()
        self.cost_days_std.setRange(1, 60)
        self.cost_days_std.setSuffix(" 人天/功能")
        self.cost_days_std.setValue(15)
        form.addRow("标准功能工期:", self.cost_days_std)

        # 定制功能倍率
        self.cost_custom_mul = QDoubleSpinBox()
        self.cost_custom_mul.setRange(1.0, 10.0)
        self.cost_custom_mul.setSingleStep(0.5)
        self.cost_custom_mul.setSuffix(" x")
        self.cost_custom_mul.setValue(2.0)
        form.addRow("定制功能倍率:", self.cost_custom_mul)

        # 毛利率
        self.cost_margin = QDoubleSpinBox()
        self.cost_margin.setRange(0.0, 0.90)
        self.cost_margin.setSingleStep(0.05)
        self.cost_margin.setDecimals(2)
        self.cost_margin.setSuffix(" (40% = 0.40)")
        self.cost_margin.setValue(0.40)
        form.addRow("毛利率:", self.cost_margin)

        # 维护费率
        self.cost_maint = QDoubleSpinBox()
        self.cost_maint.setRange(0.0, 0.50)
        self.cost_maint.setSingleStep(0.05)
        self.cost_maint.setDecimals(2)
        self.cost_maint.setSuffix(" (10% = 0.10)")
        self.cost_maint.setValue(0.10)
        form.addRow("维护费率:", self.cost_maint)

        # 项目周期
        self.cost_months = QSpinBox()
        self.cost_months.setRange(1, 36)
        self.cost_months.setSuffix(" 月")
        self.cost_months.setValue(3)
        form.addRow("项目周期:", self.cost_months)

        layout.addWidget(cost_group)

        # 公式说明
        formula_label = QLabel(
            "报价公式：\n"
            "  标准版 = 所有标准功能 + 定制功能\n"
            "  裁剪版 = 核心标准功能（前 60%）\n"
            "  人天 = Σ(标准功能×工期) + Σ(定制功能×工期×倍率)\n"
            "  开发费 = 人天 × 人天费率\n"
            "  维护费 = 开发费 × 维护费率\n"
            "  毛利 = 开发费 × 毛利率"
        )
        formula_label.setObjectName("tipLabel")
        formula_label.setWordWrap(True)
        layout.addWidget(formula_label)

        layout.addStretch()
        return tab

    # ---- Agent 表格 ----

    def _fill_agent_rows(self) -> None:
        """填充表格行（控件）。"""
        for row, key in enumerate(AGENT_KEYS):
            name_item = QTableWidgetItem(AGENT_LABELS.get(key, key))
            name_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 0, name_item)

            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.addItems(COMMON_MODELS)
            combo.setCurrentText(COMMON_MODELS[0])
            self.table.setCellWidget(row, 1, combo)

            check = QCheckBox()
            check.setChecked(True)
            check.stateChanged.connect(lambda state, r=row: self._on_toggle_global_key(r, state))
            self.table.setCellWidget(row, 2, check)

            key_input = QLineEdit()
            key_input.setEchoMode(QLineEdit.Password)
            key_input.setPlaceholderText("留空则用全局 Key")
            key_input.setEnabled(False)
            self.table.setCellWidget(row, 3, key_input)

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

    # ---- 加载/保存 ----

    def _load_config(self) -> None:
        """从配置加载到界面。"""
        # 全局 Key
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

        # 成本参数
        cost = self.config.cost
        self.cost_pd_rate.setValue(cost.person_day_rate)
        self.cost_days_std.setValue(cost.days_per_std_feature)
        self.cost_custom_mul.setValue(cost.custom_multiplier)
        self.cost_margin.setValue(cost.margin_rate)
        self.cost_maint.setValue(cost.maintenance_rate)
        self.cost_months.setValue(cost.project_months)

    def _on_save(self) -> None:
        """保存配置（LLM + 成本参数）。"""
        # 全局 LLM
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

        # 成本参数
        self.config.cost = CostConfig(
            person_day_rate=self.cost_pd_rate.value(),
            days_per_std_feature=self.cost_days_std.value(),
            custom_multiplier=self.cost_custom_mul.value(),
            margin_rate=self.cost_margin.value(),
            maintenance_rate=self.cost_maint.value(),
            project_months=self.cost_months.value(),
        )

        self.config.save()
        reload_config()
        QMessageBox.information(self, "保存成功", "模型配置 + 成本参数已保存。")
        self.accept()
