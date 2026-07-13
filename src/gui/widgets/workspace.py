"""中栏：工作区面板（三 Tab）。

Tab 1：需求输入 - 导入脏数据 + 清洗报告 + 「开始执行」按钮
Tab 2：PRD 预览 - 8 模块标准化 PRD + 功能点标注表
Tab 3：配套附件 - 报价/合同比对/评审/交付计划

接入 Orchestrator 信号，实时填充各 Agent 产出。
"""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPlainTextEdit,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QSplitter,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QMessageBox,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path


def _extract_weeks(phase: dict) -> int:
    """安全提取阶段周数，兼容 int/str/带「周」字格式。"""
    for key in ("duration", "weeks"):
        val = phase.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            import re
            match = re.search(r"[\d.]+", val)
            if match:
                try:
                    return int(float(match.group()))
                except ValueError:
                    return 0
            return 0
    return 0


def _format_duration(phase: dict) -> str:
    """格式化工期显示文本。"""
    for key in ("duration", "weeks"):
        val = phase.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return f"{int(val)}周"
        if isinstance(val, str) and val:
            return val if "周" in val else f"{val}周"
    return "0周"


class WorkspacePanel(QWidget):
    """中栏工作区，含三个 Tab。"""

    # 信号：用户点击「开始执行」
    execute_requested = Signal(str, str)  # raw_input, client_name

    def __init__(self) -> None:
        super().__init__()
        self._last_state: dict = {}
        self._client_name: str = ""
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化三 Tab。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tabs = QTabWidget()

        # === Tab 1: 需求输入 ===
        self.input_tab = QWidget()
        input_layout = QVBoxLayout(self.input_tab)

        # 按钮栏 + 进度条
        btn_bar = QHBoxLayout()
        self.execute_btn = QPushButton("▶ 开始执行")
        self.execute_btn.setObjectName("primaryBtn")
        self.execute_btn.clicked.connect(self._on_execute)
        self.import_btn = QPushButton("导入文件")
        self.import_btn.clicked.connect(self._on_import)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_bar.addWidget(self.execute_btn)
        btn_bar.addWidget(self.import_btn)
        btn_bar.addWidget(self.clear_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)
        btn_bar.addWidget(self.progress_bar, 1)

        btn_bar.addStretch()
        input_layout.addLayout(btn_bar)

        # 客户名输入框 + 模板选择
        client_bar = QHBoxLayout()
        client_bar.addWidget(QLabel("客户名:"))
        self.client_name_edit = QLineEdit()
        self.client_name_edit.setPlaceholderText("输入客户名（可选，留空时自动从需求中提取）")
        client_bar.addWidget(self.client_name_edit, 1)

        client_bar.addWidget(QLabel("快速模板:"))
        self.template_combo = QComboBox()
        self.template_combo.addItem("选择行业模板...", "")
        self.template_combo.addItem("K12 在线教育", "k12")
        self.template_combo.addItem("企业 ERP", "erp")
        self.template_combo.addItem("政务数字化", "gov")
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        client_bar.addWidget(self.template_combo)

        input_layout.addLayout(client_bar)

        # 输入区
        input_layout.addWidget(QLabel("需求输入 - 粘贴微信记录/文档/口头承诺"))
        self.input_editor = QPlainTextEdit()
        self.input_editor.setPlaceholderText(
            "在此粘贴销售脏需求...\n\n"
            "示例：\n"
            "客户想做K12在线教育平台\n"
            "需要课程管理、直播、作业、支付\n"
            "销售承诺终身免费、10万并发、提供源代码"
        )
        self.input_editor.textChanged.connect(self._update_char_count)
        input_layout.addWidget(self.input_editor)

        # 字数统计
        self.char_count_label = QLabel("字数：0")
        self.char_count_label.setAlignment(Qt.AlignRight)
        input_layout.addWidget(self.char_count_label)

        # SAR 清洗报告区
        self.sar_report = QPlainTextEdit()
        self.sar_report.setReadOnly(True)
        self.sar_report.setPlaceholderText("SAR Agent 清洗报告将在此显示...")
        self.sar_report.setMaximumHeight(200)
        input_layout.addWidget(QLabel("SAR 清洗报告"))
        input_layout.addWidget(self.sar_report)

        self.tabs.addTab(self.input_tab, "需求输入")

        # === Tab 2: PRD 预览 ===
        self.prd_tab = QWidget()
        prd_layout = QVBoxLayout(self.prd_tab)

        # 导出按钮栏
        export_bar = QHBoxLayout()
        self.export_md_btn = QPushButton("导出 Markdown")
        self.export_md_btn.setToolTip("导出为 Markdown 文件")
        self.export_md_btn.clicked.connect(self._on_export_md)
        self.export_word_btn = QPushButton("导出 Word")
        self.export_word_btn.setToolTip("导出为 .docx 文件")
        self.export_word_btn.clicked.connect(self._on_export_word)
        self.export_json_btn = QPushButton("导出完整报告(JSON)")
        self.export_json_btn.setToolTip("导出完整 State 为 JSON")
        self.export_json_btn.clicked.connect(self._on_export_json)
        export_bar.addWidget(self.export_md_btn)
        export_bar.addWidget(self.export_word_btn)
        export_bar.addWidget(self.export_json_btn)
        export_bar.addStretch()
        prd_layout.addLayout(export_bar)

        # PRD 8 模块展示
        self.prd_preview = QPlainTextEdit()
        self.prd_preview.setReadOnly(True)
        self.prd_preview.setPlaceholderText("PRD 生成后将在此展示 8 模块...")
        prd_layout.addWidget(QLabel("PRD 8 模块"))
        prd_layout.addWidget(self.prd_preview)

        # 功能点标注表
        prd_layout.addWidget(QLabel("功能点标注"))
        self.feature_table = QTableWidget(0, 3)
        self.feature_table.setHorizontalHeaderLabels(["功能", "标注", "说明"])
        self.feature_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.feature_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.feature_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        prd_layout.addWidget(self.feature_table)

        self.tabs.addTab(self.prd_tab, "PRD 预览")

        # === Tab 3: 配套附件 ===
        self.attach_tab = QWidget()
        attach_layout = QVBoxLayout(self.attach_tab)

        # 报价区
        quotes_group = QGroupBox("Commercial Agent - 双报价")
        quotes_layout = QVBoxLayout(quotes_group)
        self.quotes_view = QPlainTextEdit()
        self.quotes_view.setReadOnly(True)
        self.quotes_view.setPlaceholderText("报价生成后将在此显示...")
        self.quotes_view.setMaximumHeight(120)
        quotes_layout.addWidget(self.quotes_view)
        attach_layout.addWidget(quotes_group)

        # 合同冲突区
        contract_group = QGroupBox("Contract Agent - 合同冲突")
        contract_layout = QVBoxLayout(contract_group)
        self.contract_view = QPlainTextEdit()
        self.contract_view.setReadOnly(True)
        self.contract_view.setPlaceholderText("合同比对结果将在此显示...")
        self.contract_view.setMaximumHeight(120)
        contract_layout.addWidget(self.contract_view)
        attach_layout.addWidget(contract_group)

        # 评审意见区
        review_group = QGroupBox("Review Agent - 多维评审")
        review_layout = QVBoxLayout(review_group)
        self.review_view = QPlainTextEdit()
        self.review_view.setReadOnly(True)
        self.review_view.setPlaceholderText("评审意见将在此显示...")
        self.review_view.setMaximumHeight(120)
        review_layout.addWidget(self.review_view)
        attach_layout.addWidget(review_group)

        # 交付计划区
        plan_group = QGroupBox("Planner Agent - 交付计划")
        plan_layout = QVBoxLayout(plan_group)
        self.plan_view = QPlainTextEdit()
        self.plan_view.setReadOnly(True)
        self.plan_view.setPlaceholderText("交付计划将在此显示...")
        plan_layout.addWidget(self.plan_view)
        attach_layout.addWidget(plan_group)

        self.tabs.addTab(self.attach_tab, "配套附件")

        layout.addWidget(self.tabs)

    def _on_execute(self) -> None:
        """点击「开始执行"。"""
        raw_input = self.input_editor.toPlainText().strip()
        if not raw_input:
            return
        client_name = self.client_name_edit.text().strip()
        self._client_name = client_name
        self.execute_btn.setEnabled(False)
        self.execute_btn.setText("执行中...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.execute_requested.emit(raw_input, client_name)

    def on_progress_updated(self, step: int, total: int, message: str) -> None:
        """更新进度条。"""
        if total <= 0:
            return
        percent = int(step / total * 100)
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"%p% - {message}")

    def _on_import(self) -> None:
        """导入文件 - 支持 .txt/.json/.docx/.pdf 文本内容。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入需求文件",
            "",
            "需求文件 (*.txt *.json *.docx *.pdf);;文本文件 (*.txt);;JSON (*.json);;Word (*.docx);;PDF (*.pdf);;所有文件 (*)",
        )
        if not file_path:
            return

        from pathlib import Path
        try:
            # 复用 doc_parser 统一解析入口
            from parsers.doc_parser import parse_document
            text = parse_document(Path(file_path))
            if text:
                self.input_editor.setPlainText(text)
                # 自动从文件名提取客户名（如果输入框为空）
                if not self.client_name_edit.text().strip():
                    self.client_name_edit.setText(Path(file_path).stem)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "导入失败", f"解析文件失败：\n{type(e).__name__}: {e}")

    def _on_clear(self) -> None:
        """清空输入。"""
        self.input_editor.clear()
        self.client_name_edit.clear()
        self.template_combo.setCurrentIndex(0)
        self.sar_report.clear()
        self.prd_preview.clear()
        self.feature_table.setRowCount(0)
        self.quotes_view.clear()
        self.contract_view.clear()
        self.review_view.clear()
        self.plan_view.clear()
        self._last_state = {}

    def _update_char_count(self) -> None:
        """更新字数统计。"""
        count = len(self.input_editor.toPlainText())
        self.char_count_label.setText(f"字数：{count}")

    def _on_template_changed(self, index: int) -> None:
        """根据选择的模板快速填充示例需求。"""
        key = self.template_combo.itemData(index)
        if not key:
            return
        templates = {
            "k12": (
                "客户：智联慧学教育科技\n"
                "需求：K12 在线教育平台\n"
                "需要：课程管理、排课、在线直播教学、作业批改、支付系统\n"
                "销售承诺：终身免费升级、10万并发、提供源代码\n"
                "数据：未成年人学生信息收集，人脸识别考勤，数据出境到新加坡\n"
            ),
            "erp": (
                "客户：华东制造集团\n"
                "需求：企业 ERP 系统\n"
                "需要：采购管理、库存管理、生产排程、财务对账、BI 报表\n"
                "销售承诺：3 个月上线、免费对接现有 OA、99.99% 可用性\n"
                "数据：供应商合同、员工薪资、客户订单集中存储\n"
            ),
            "gov": (
                "客户：某市政务服务中心\n"
                "需求：政务数字化服务平台\n"
                "需要：一网通办、电子证照、在线预约、数据分析大屏\n"
                "销售承诺：等保三级、国产化适配、终身运维\n"
                "数据：公民身份证、企业营业执照、办事记录本地存储\n"
            ),
        }
        text = templates.get(key, "")
        if text:
            self.input_editor.setPlainText(text)
            self.client_name_edit.setText(text.split("\n")[0].replace("客户：", "").strip())

    # ============================================================
    # 接收 Orchestrator 信号，填充结果
    # ============================================================
    def on_workflow_complete(self, state: dict) -> None:
        """工作流完成，填充全部结果。"""
        self._last_state = state

        # SAR 清洗报告
        sar_text = f"【清洗后需求】\n{state.get('cleaned_requirements', '')}\n\n"
        sar_text += "【过度承诺风险】\n"
        for i, risk in enumerate(state.get("overcommit_risks", []), 1):
            sar_text += f"{i}. {risk}\n"
        self.sar_report.setPlainText(sar_text)

        # PRD 8 模块
        prd = state.get("prd", {})
        prd_text = ""
        for module, content in prd.items():
            prd_text += f"━━ {module} ━━\n{content}\n\n"
        self.prd_preview.setPlainText(prd_text)

        # 功能点标注表
        features = state.get("prd_features", [])
        self.feature_table.setRowCount(len(features))
        for i, feat in enumerate(features):
            self.feature_table.setItem(i, 0, QTableWidgetItem(feat.get("name", "")))
            tag_item = QTableWidgetItem(feat.get("tag", ""))
            self.feature_table.setItem(i, 1, tag_item)
            self.feature_table.setItem(i, 2, QTableWidgetItem(feat.get("desc", "")))

        # 报价
        quotes = state.get("quotes", {})
        quotes_text = ""
        for version, quote in quotes.items():
            quotes_text += f"【{version}】\n"
            for k, v in quote.items():
                if isinstance(v, float) and v < 1:
                    quotes_text += f"  {k}: {v:.0%}\n"
                else:
                    quotes_text += f"  {k}: {v}\n"
            quotes_text += "\n"
        self.quotes_view.setPlainText(quotes_text)

        # 合同冲突
        conflicts = state.get("contract_conflicts", [])
        contract_text = ""
        for i, c in enumerate(conflicts, 1):
            contract_text += f"[{c.get('risk', '').upper()}] 冲突 {i}\n"
            contract_text += f"  PRD: {c.get('prd_clause', '')}\n"
            contract_text += f"  合同: {c.get('contract_clause', '')}\n"
            contract_text += f"  说明: {c.get('conflict', '')}\n\n"
        self.contract_view.setPlainText(contract_text)

        # 评审意见
        reviews = state.get("review_comments", {})
        review_text = ""
        for dimension, comments in reviews.items():
            review_text += f"【{dimension.upper()}】\n"
            for c in comments:
                review_text += f"  - {c}\n"
            review_text += "\n"
        review_text += f"评审结论: {'通过' if state.get('review_pass') else '不通过'}"
        self.review_view.setPlainText(review_text)

        # 交付计划
        plan = state.get("delivery_plan", [])
        plan_text = ""
        total_weeks = 0
        for phase in plan:
            weeks = _extract_weeks(phase)
            total_weeks += weeks
            dur_display = _format_duration(phase)
            dlv = phase.get("deliverable", phase.get("deliverables", "未指定"))
            plan_text += f"【{phase.get('phase', phase.get('name', '未命名'))}】({dur_display})\n"
            plan_text += f"  交付物: {dlv}\n\n"
        if plan:
            plan_text += f"━━ 总工期: {total_weeks} 周 ━━"
        else:
            plan_text = "（无交付计划数据）"
        self.plan_view.setPlainText(plan_text)

        # 恢复按钮
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("▶ 开始执行")
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

        # 自动切换到 PRD 预览 Tab
        self.tabs.setCurrentIndex(1)

    def on_workflow_blocked(self, reason: str) -> None:
        """工作流被阻断。"""
        self.sar_report.setPlainText(f"⛔ 工作流被阻断\n\n原因: {reason}")
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("▶ 开始执行")
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

    def _on_export_md(self) -> None:
        """导出 Markdown。"""
        if not self._last_state:
            QMessageBox.warning(self, "导出失败", "尚未生成 PRD，请先执行工作流")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 Markdown", f"PRD_{self._client_name or 'output'}.md",
            "Markdown (*.md);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            from core.exporter import export_prd_as_markdown
            md = export_prd_as_markdown(self._last_state, self._client_name)
            Path(file_path).write_text(md, encoding="utf-8")
            QMessageBox.information(self, "导出成功", f"已保存：\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"{type(e).__name__}: {e}")

    def _on_export_word(self) -> None:
        """导出 Word。"""
        if not self._last_state:
            QMessageBox.warning(self, "导出失败", "尚未生成 PRD，请先执行工作流")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 Word", f"PRD_{self._client_name or 'output'}.docx",
            "Word 文档 (*.docx);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            from core.exporter import export_prd_as_word
            export_prd_as_word(self._last_state, Path(file_path), self._client_name)
            QMessageBox.information(self, "导出成功", f"已保存：\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"{type(e).__name__}: {e}")

    def _on_export_json(self) -> None:
        """导出完整 JSON 报告。"""
        if not self._last_state:
            QMessageBox.warning(self, "导出失败", "尚未生成 PRD，请先执行工作流")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出完整报告", f"Report_{self._client_name or 'output'}.json",
            "JSON (*.json);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            from core.exporter import export_full_report_as_json
            export_full_report_as_json(self._last_state, Path(file_path))
            QMessageBox.information(self, "导出成功", f"已保存：\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"{type(e).__name__}: {e}")
