"""工作流编排器 - QThread 后台执行 LangGraph 编译图。

信号：
- node_started(node_name): 节点开始执行
- node_finished(node_name): 节点执行完成
- workflow_blocked(reason, state): Legal 高风险阻断，等待人工确认
- workflow_complete(state): 全流程完成
- log_message(message): 实时日志

Interrupt 机制：
1. 主图 Legal 判定高风险 → 图路由到 END（阻断）
2. Orchestrator 发 workflow_blocked 信号，等待确认
3. MainWindow 弹确认对话框
4. 用户确认 → Orchestrator 运行 resume 图（PM → fan-out → Planner）
5. 用户拒绝 → Orchestrator 发 workflow_complete，工作流终止
"""
import threading
from PySide6.QtCore import QThread, Signal

from agents.state import SpecMindState
from graph.builder import get_compiled_graph, get_resume_graph
from core.logger import setup_logger

logger = setup_logger("specmind.orchestrator")


# 节点显示顺序（与 workflow_canvas.py 保持一致，用于进度计算）
_NODE_ORDER = [
    "sar_agent",
    "legal_agent",
    "interrupt",
    "pm_agent",
    "commercial_agent",
    "contract_agent",
    "review_agent",
    "planner_agent",
]


class WorkflowOrchestrator(QThread):
    """后台工作流编排线程，基于 LangGraph 编译图。"""

    # 信号定义
    node_started = Signal(str)
    node_finished = Signal(str)
    progress_updated = Signal(int, int, str)  # current_step, total_steps, message
    workflow_blocked = Signal(str, dict)   # 阻断原因 + 当前 State
    workflow_complete = Signal(dict)       # 最终 State
    log_message = Signal(str)

    def __init__(self, raw_input: str, client_name: str = "") -> None:
        """初始化编排器。"""
        super().__init__()
        self.raw_input = raw_input
        self.client_name = client_name
        self._state: SpecMindState = {}
        self._confirm_event = threading.Event()
        self._reject_flag = False
        self._completed_nodes: set[str] = set()

    def _emit_log(self, msg: str) -> None:
        """发送日志信号。"""
        logger.info(msg)
        self.log_message.emit(msg)

    def _emit_progress(self, node_name: str) -> None:
        """发送进度更新信号。

        进度基于 8 个可视化节点计算：当前已完成节点数 / 8。
        """
        self._completed_nodes.add(node_name)
        # interrupt 节点跟随 legal_agent 状态，不单独计步
        effective = {n for n in self._completed_nodes if n != "interrupt"}
        step = len(effective)
        total = len(_NODE_ORDER) - 1  # 排除 interrupt
        msg = f"{node_name} 完成 ({step}/{total})"
        self.progress_updated.emit(step, total, msg)

    def confirm_resume(self) -> None:
        """用户确认放行 - 触发 resume 图执行。"""
        self._reject_flag = False
        self._confirm_event.set()

    def reject_resume(self) -> None:
        """用户拒绝放行 - 终止工作流。"""
        self._reject_flag = True
        self._confirm_event.set()

    def run(self) -> None:
        """执行工作流（后台线程入口）。"""
        self._emit_log("=" * 60)
        self._emit_log("[Orchestrator] LangGraph 工作流启动")
        self._emit_log(f"[Orchestrator] 输入长度: {len(self.raw_input)} 字符")

        # 初始 State
        initial_state: SpecMindState = {
            "raw_input": self.raw_input,
            "client_info": {"client_name": self.client_name},
            "audit_snapshots": [],
            "current_node": "init",
        }

        try:
            # === 阶段 1：运行主图 ===
            self._emit_log("[Orchestrator] ▶ 阶段 1: 运行主图 (SAR → Legal → 路由)")
            self._run_main_graph(initial_state)

            # 检查是否被阻断
            if self._state.get("legal_blocked", False):
                # === 等待人工确认 ===
                self._emit_log("[Orchestrator] ⛔ Legal 高风险，等待人工确认...")
                reason = f"Legal 合规预检判定 {self._state.get('legal_risk_level', 'high')} 风险"
                self.workflow_blocked.emit(reason, dict(self._state))

                # 阻塞等待用户确认
                self._confirm_event.wait()
                self._confirm_event.clear()

                if self._reject_flag:
                    # 用户拒绝
                    self._emit_log("[Orchestrator] ✗ 用户拒绝放行，工作流终止")
                    self.workflow_complete.emit(dict(self._state))
                    return

                # === 阶段 2：运行 resume 图 ===
                self._emit_log("[Orchestrator] ▶ 阶段 2: 用户确认放行，运行 resume 图")
                self._run_resume_graph()

            # 完成
            self._emit_log("[Orchestrator] ✅ 工作流全部完成")
            self._emit_log(f"[Orchestrator] 审计快照数: {len(self._state.get('audit_snapshots', []))}")
            self.workflow_complete.emit(dict(self._state))

        except Exception as e:
            self._emit_log(f"[Orchestrator] ❌ 异常: {type(e).__name__}: {e}")
            import traceback
            self._emit_log(traceback.format_exc())
            self.workflow_complete.emit(dict(self._state))

    def _run_main_graph(self, initial_state: SpecMindState) -> None:
        """运行主图（SAR → Legal → 路由）。"""
        graph = get_compiled_graph()
        config = {"configurable": {"thread_id": f"specmind_{id(self)}"}}

        self._emit_log("[Orchestrator] 获取编译图，开始 stream 执行...")

        # 注意：stream_mode="updates" 只在节点返回后才 yield 事件，
        # 因此 node_started 信号实际在节点执行完毕后发出（存在天然滞后）。
        # 此处先 emit started 再 merge state 再 emit finished，至少保证信号顺序正确，
        # GUI 上"执行中"状态会短暂显示。要彻底消除滞后需升级 LangGraph 或使用节点回调机制。
        for event in graph.stream(initial_state, config, stream_mode="updates"):
            for node_name, node_update in event.items():
                self.node_started.emit(node_name)
                self._emit_log(f"[Orchestrator] ▶ {node_name} 结果返回，合并 State...")

                # 合并 State 更新（audit_snapshots 需累加，不能覆盖）
                if node_update:
                    self._merge_state_update(node_update)

                self.node_finished.emit(node_name)
                self._emit_log(f"[Orchestrator] ✅ {node_name} 完成")
                self._emit_progress(node_name)

        # 从 checkpointer 获取最终完整 State
        # 注意：并行节点 audit_snapshots 在 checkpointer 中可能不完整，
        # 保留手动累加结果（手动累加在 stream 循环中已正确合并所有节点）
        try:
            final_state = graph.get_state(config)
            if final_state and final_state.values:
                manual_snapshots = self._state.get("audit_snapshots", [])
                self._state = dict(final_state.values)
                if len(manual_snapshots) > len(self._state.get("audit_snapshots", [])):
                    self._state["audit_snapshots"] = manual_snapshots
        except Exception:
            pass  # checkpointer 不可用时保持手动合并结果

        self._emit_log(f"[Orchestrator] 主图执行完毕, legal_blocked={self._state.get('legal_blocked', False)}")

    def _run_resume_graph(self) -> None:
        """运行 resume 图（PM → fan-out → Planner）。"""
        resume_graph = get_resume_graph()

        # 清除阻断标记，让 resume 图正常执行
        resume_state = dict(self._state)
        resume_state["legal_blocked"] = False

        self._emit_log("[Orchestrator] 获取 resume 图，开始 stream 执行...")

        # resume 图同样使用 updates 模式，节点开始信号存在天然滞后
        for event in resume_graph.stream(resume_state, stream_mode="updates"):
            for node_name, node_update in event.items():
                self.node_started.emit(node_name)
                self._emit_log(f"[Orchestrator] ▶ {node_name} 结果返回，合并 State...")

                if node_update:
                    self._merge_state_update(node_update)

                self.node_finished.emit(node_name)
                self._emit_log(f"[Orchestrator] ✅ {node_name} 完成")
                self._emit_progress(node_name)

    def get_state(self) -> SpecMindState:
        """获取当前 State。"""
        return self._state

    def _merge_state_update(self, update: dict) -> None:
        """合并 State 更新，audit_snapshots 累加而非覆盖。"""
        if "audit_snapshots" in update:
            snapshots = self._state.get("audit_snapshots", [])
            snapshots = snapshots + update["audit_snapshots"]
            self._state["audit_snapshots"] = snapshots
            # 其他字段正常更新
            for k, v in update.items():
                if k != "audit_snapshots":
                    self._state[k] = v
        else:
            self._state.update(update)
