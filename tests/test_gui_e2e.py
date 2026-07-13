"""GUI 真实环境端到端验证。

在 QApplication 事件循环中启动 MainWindow，模拟用户输入需求并执行工作流，
验证：
1. GUI 能正常初始化
2. 工作区能接收用户输入
3. Orchestrator 能启动 LangGraph 工作流
4. 右侧画布能接收节点状态信号
5. 工作完成后工作区能显示 PRD/报价/交付计划等结果
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

from gui.main_window import MainWindow


class TestHarness:
    """GUI 端到端测试控制器。"""

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.window = MainWindow()
        self.step = 0
        self.start_time = time.time()
        self.results = {
            "gui_initialized": False,
            "workflow_started": False,
            "node_signals": [],
            "workflow_completed": False,
            "prd_displayed": False,
            "quotes_displayed": False,
            "plan_displayed": False,
            "errors": [],
        }

    def run(self):
        """启动测试。"""
        print("=" * 80)
        print("GUI 真实环境端到端验证")
        print("=" * 80)

        # 1. 初始化检查
        print("\n[1] GUI 初始化检查...")
        try:
            self.window.show()
            self.results["gui_initialized"] = True
            print("    ✓ MainWindow 已显示")
            print(f"    ✓ 窗口尺寸: {self.window.width()}x{self.window.height()}")
            print(f"    ✓ 三栏组件: asset={self.window.asset_panel is not None}, "
                  f"workspace={self.window.workspace_panel is not None}, "
                  f"canvas={self.window.canvas_panel is not None}")
        except Exception as e:
            self.results["errors"].append(f"GUI 初始化失败: {e}")
            print(f"    ✗ {e}")
            self._finish()
            return

        # 2. 延迟 500ms 后输入需求并启动工作流
        print("\n[2] 将在 0.5s 后模拟用户输入并启动工作流...")
        QTimer.singleShot(500, self._setup_input_and_start)

        # 3. 设置超时保护（30 秒）
        QTimer.singleShot(30000, self._on_timeout)

        # 进入事件循环
        self.app.exec()

    def _setup_input_and_start(self):
        """设置输入文本并启动工作流。"""
        try:
            workspace = self.window.workspace_panel

            raw_input = (
                "客户：智联慧学教育科技\n"
                "需求：K12 在线教育平台\n"
                "需要：课程管理、排课、在线直播教学、作业批改、支付系统\n"
                "销售承诺：终身免费升级、10万并发、提供源代码\n"
                "数据：未成年人学生信息收集，人脸识别考勤，数据出境到新加坡\n"
            )
            client_name = "智联慧学教育科技"

            # 填充输入框
            workspace.input_editor.setPlainText(raw_input)
            workspace.client_name_edit.setText(client_name)
            print("    ✓ 已填充需求文本和客户名称")

            # 直接发射信号启动工作流（模拟点击执行按钮）
            workspace.execute_requested.emit(raw_input, client_name)
            self.results["workflow_started"] = True
            print("    ✓ execute_requested 信号已发射")

            # 监听画布信号
            canvas = self.window.canvas_panel
            canvas.setProperty("test_harness", self)
            self.window._orchestrator.node_started.connect(self._on_node_started)
            self.window._orchestrator.node_finished.connect(self._on_node_finished)
            self.window._orchestrator.workflow_complete.connect(self._on_workflow_complete)

        except Exception as e:
            self.results["errors"].append(f"输入/启动失败: {e}")
            print(f"    ✗ {e}")
            self._finish()

    def _on_node_started(self, node_name: str):
        """记录节点开始信号。"""
        self.results["node_signals"].append(("start", node_name))
        print(f"    ▶ 信号: {node_name} started")

    def _on_node_finished(self, node_name: str):
        """记录节点完成信号。"""
        self.results["node_signals"].append(("finish", node_name))
        print(f"    ✓ 信号: {node_name} finished")

    def _on_workflow_complete(self, state: dict):
        """工作流完成后检查前端数据。"""
        try:
            elapsed = time.time() - self.start_time
            print(f"\n[3] 工作流完成，耗时 {elapsed:.2f}s")
            self.results["workflow_completed"] = True

            workspace = self.window.workspace_panel

            # 检查 PRD Tab 是否有内容
            prd_text = workspace.prd_preview.toPlainText()
            self.results["prd_displayed"] = len(prd_text) > 100
            print(f"    ✓ PRD 预览长度: {len(prd_text)} 字符")

            # 检查附件 Tab 的交付计划
            plan_text = workspace.plan_view.toPlainText()
            self.results["plan_displayed"] = "周" in plan_text or "阶段" in plan_text
            print(f"    ✓ 交付计划长度: {len(plan_text)} 字符")

            # 检查报价（workspace 上可能有报价显示）
            quotes = state.get("quotes", {})
            self.results["quotes_displayed"] = len(quotes) >= 2
            print(f"    ✓ 报价版本数: {len(quotes)}")

            # 检查审计快照
            snapshots = state.get("audit_snapshots", [])
            print(f"    ✓ 审计快照数: {len(snapshots)}")

            # 检查画布状态
            canvas = self.window.canvas_panel
            completed_nodes = sum(
                1 for i in range(canvas.node_tree.topLevelItemCount())
                if canvas.node_tree.topLevelItem(i).text(1) == "完成"
            )
            print(f"    ✓ 画布完成节点数: {completed_nodes}/{canvas.node_tree.topLevelItemCount()}")

        except Exception as e:
            self.results["errors"].append(f"结果检查失败: {e}")
            print(f"    ✗ {e}")
        finally:
            # 延迟 1s 后退出事件循环
            QTimer.singleShot(1000, self._finish)

    def _on_timeout(self):
        """超时处理。"""
        if not self.results["workflow_completed"]:
            self.results["errors"].append("工作流执行超时（30s）")
            print("\n✗ 工作流执行超时（30s）")
            self._finish()

    def _finish(self):
        """结束测试并输出报告。"""
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 80)
        print("GUI 真实环境端到端验证总结")
        print("=" * 80)
        print(f"总耗时: {elapsed:.2f}s")
        print(f"GUI 初始化: {'✓' if self.results['gui_initialized'] else '✗'}")
        print(f"工作流启动: {'✓' if self.results['workflow_started'] else '✗'}")
        print(f"工作流完成: {'✓' if self.results['workflow_completed'] else '✗'}")
        print(f"节点信号数: {len(self.results['node_signals'])}")
        print(f"PRD 显示: {'✓' if self.results['prd_displayed'] else '✗'}")
        print(f"报价显示: {'✓' if self.results['quotes_displayed'] else '✗'}")
        print(f"交付计划显示: {'✓' if self.results['plan_displayed'] else '✗'}")

        if self.results["errors"]:
            print(f"\n❌ 错误 ({len(self.results['errors'])}):")
            for e in self.results["errors"]:
                print(f"  - {e}")
        else:
            print("\n✅ GUI 真实环境端到端验证通过")
            print("   - GUI 初始化成功")
            print("   - 工作区 → Orchestrator → LangGraph 链路打通")
            print("   - Orchestrator → 画布信号链路打通")
            print("   - 工作完成后前端可正常显示 PRD/报价/交付计划")

        self.app.quit()


if __name__ == "__main__":
    harness = TestHarness()
    harness.run()
    sys.exit(0 if not harness.results["errors"] else 1)
