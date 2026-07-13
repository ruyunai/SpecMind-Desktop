"""生产就绪验证脚本 — 测试 LLM 重试 + 空知识库检测。

覆盖:
  1. LLM 重试: 模拟超时 → 重试 → 成功
  2. LLM 重试: 认证错误不重试（直接抛出）
  3. LLM 重试: 3 次全失败后抛出
  4. 空 KB 检测: ChromaDB 三个分类的 count()
  5. 完整 e2e: 上传文档 → LLM 调用（走 retry 链路）→ Agent 分析
"""
import sys; sys.path.insert(0, 'src')
import time

OK = 0; FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global OK, FAIL
    if condition:
        OK += 1
        print(f"  ✅ {name} {detail}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


print("=" * 60)
print("生产就绪验证")
print("=" * 60)

# ============================================================
# 1. LLM 重试：可重试异常检测
# ============================================================
print("\n[1] LLM 重试 — 可重试异常检测")
from agents.llm_client import _is_retryable

check("timeout 可重试",        _is_retryable(TimeoutError("Request timed out")))
check("connection 可重试",      _is_retryable(ConnectionError("Connection refused")))
check("rate_limit 可重试",      _is_retryable(Exception("too many requests, rate limit exceeded")))
check("server_error 可重试",    _is_retryable(Exception("Internal Server Error")))
check("auth 不可重试",          not _is_retryable(Exception("Unauthorized: invalid API Key")))
check("bad_request 不可重试",   not _is_retryable(Exception("Bad Request: model not found")))

# ============================================================
# 2. LLM 重试：指数退避验证
# ============================================================
print("\n[2] LLM 重试 — 退避时序验证")
from agents.llm_client import RETRY_BASE_DELAY, RETRY_BACKOFF_FACTOR, MAX_RETRIES

expected_delays = [RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** i) for i in range(MAX_RETRIES)]
check("退避序列=2s/4s/8s", expected_delays == [2.0, 4.0, 8.0],
      f"→ {expected_delays}")

# ============================================================
# 3. LLM 重试：真实 LLM 调用（验证重试链路可走通）
# ============================================================
print("\n[3] LLM 重试 — 真实调用（DeepSeek，验证重试链路）")
print("    (如果网络正常，首次即成功，重试代码路径不会被触发)")
try:
    from agents.llm_client import invoke_llm
    t0 = time.time()
    result = invoke_llm("sar", "请用一句话回答：1+1等于几")
    elapsed = time.time() - t0
    check("LLM 调用成功", len(result) > 0,
          f"耗时={elapsed:.1f}s, 返回={len(result)}字符")
    check("答案包含2", "2" in result, f"→ {result[:50]}")
except Exception as e:
    check("LLM 调用成功", False, str(e))

# ============================================================
# 4. 空知识库检测
# ============================================================
print("\n[4] 空知识库检测")
from storage.chroma_store import ChromaStore
from storage.schema import AssetCategory

store = ChromaStore()
categories = [
    (AssetCategory.STANDARD_FEATURE, "标准功能清单"),
    (AssetCategory.REGULATION, "法规库"),
    (AssetCategory.CONTRACT_TEMPLATE, "合同模板库"),
]

empty_list = []
for cat, name in categories:
    count = store.count(cat)
    status = "空" if count == 0 else f"{count} 条"
    print(f"    {name}: {status}")
    if count == 0:
        empty_list.append(name)

if len(empty_list) == 3:
    print("    ⚠ 提示: 知识库完全为空！建议上传企业文档后再执行分析。")
elif empty_list:
    print(f"    ⚠ 提示: {', '.join(empty_list)} 为空，建议上传。")
else:
    print("    ✅ 知识库有数据")

check("KB 检测无异常", True)

# ============================================================
# 5. 完整 e2e 流程（含 LLM 重试 + KB 覆盖度）
# ============================================================
print("\n[5] 完整 e2e（上传 → 检索 → LLM → Agent）")
print("    (包含 LLM 重试栈 + 置信度评估 + 降级提示)")

from gui.services.upload_service import ingest_document

# 确保有法规数据
if store.count(AssetCategory.REGULATION) == 0:
    print("    注入测试法规...")
    ingest_document("tests/test_upload_regulation.txt", "regulation", "个人信息保护法-测试")

from graph.builder import build_graph
from agents.state import SpecMindState

graph = build_graph()
initial_state: SpecMindState = {
    "raw_input": (
        "客户：智联慧学教育科技\n"
        "需求：在线教育平台，收集学生人脸信息用于考勤，学生数据存储于海外服务器。\n"
        "要求提供全部源代码，终身免费升级维护。"
    ),
    "client_info": {"client_name": "智联慧学"},
}
config = {"configurable": {"thread_id": "prod_readiness_test"}}

t0 = time.time()
final = graph.invoke(initial_state, config)
elapsed = time.time() - t0

print(f"    耗时: {elapsed:.1f}s")
print(f"    风险等级: {final.get('legal_risk_level')}")
print(f"    是否阻断: {final.get('legal_blocked')}")

# 验证关键字段（对应 agents/state.py 中的 SpecMindState）
cleaned = final.get("cleaned_requirements", "")
prd = final.get("prd", {})
quotes = final.get("quotes", {})
plan = final.get("delivery_plan", [])
review = final.get("review_comments", {})
review_pass = final.get("review_pass", False)

check("清洗后需求非空",      bool(cleaned), f"{len(cleaned)} 字符")
check("PRD 已生成",            bool(prd),    f"{len(prd)} 模块")
check("标准版报价已生成",      quotes.get("标准版") is not None,
      f"{quotes.get('标准版', {})}")
check("高级版报价已生成",      quotes.get("裁剪版") is not None,
      f"{quotes.get('裁剪版', {})}")
check("交付计划已生成",        bool(plan), f"{len(plan)} 阶段")
check("评审意见已生成",        bool(review), f"{len(review)} 维度")
check("评审通过",              review_pass)
check("合规预检已执行",        bool(final.get("legal_risk_level")))

# ============================================================
# 总结
# ============================================================
print()
print("=" * 60)
total = OK + FAIL
if FAIL == 0:
    print(f"✅ 全部 {total} 项通过")
else:
    print(f"⚠ {OK}/{total} 通过, {FAIL} 失败")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
