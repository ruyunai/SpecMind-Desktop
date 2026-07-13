"""端到端验证：上传文档 → 分块 → 嵌入 → RAG 检索 → Agent 使用。"""
import sys; sys.path.insert(0, 'src')

from gui.services.upload_service import ingest_document, delete_documents_by_source
from storage.chroma_store import ChromaStore
from storage.schema import AssetCategory

# 0. 清理上次测试数据
print("0. 清理上次测试数据...")
store = ChromaStore()
deleted = delete_documents_by_source("个人信息保护法-测试", "regulation")
print(f"   删除: {deleted} 条")
count_before = store.count(AssetCategory.REGULATION)
print(f"   法规库当前: {count_before} 条")

# 1. 上传测试法规文档
print()
print("=" * 50)
print("1. 上传测试文档...")
result = ingest_document(
    "tests/test_upload_regulation.txt",
    "regulation",
    "个人信息保护法-测试"
)
print(f"   文档: {result.doc_name}")
print(f"   分块: {result.total_chunks}, 新增: {result.added}, 跳过: {result.skipped}")
assert result.added > 0, f"上传失败！新增={result.added}"

# 2. 验证入库 + 去重
print()
print("2. 验证入库 + hash去重...")
count_after = store.count(AssetCategory.REGULATION)
print(f"   法规库总数: {count_after}")
assert count_after > 0

# 重复上传验证去重
result2 = ingest_document(
    "tests/test_upload_regulation.txt",
    "regulation",
    "个人信息保护法-测试"
)
assert result2.skipped > 0, f"去重未生效! skipped={result2.skipped}"
print(f"   重复上传: 跳过 {result2.skipped}/{result2.total_chunks} 条 ✅")

# 3. RAG 检索验证
print()
print("3. RAG 检索验证...")
from storage.retriever import HybridRetriever
retriever = HybridRetriever()
results = retriever.retrieve("未成年人信息保护", category="regulation", top_k=3)
items = results.get("items", results) if isinstance(results, dict) else results
print(f"   检索'未成年人信息保护'命中: {len(items)}")
for r in items[:2] if isinstance(items, list) else [items]:
    text = r.get("text", "")[:60]
    score = r.get("score", 0)
    print(f"     [{score:.3f}] {text}...")
assert len(results) > 0, "RAG 检索无结果！"

# 4. Agent 端到端（含上传文档的 RAG 检索）
print()
print("4. Agent e2e 验证（含用户上传文档的 RAG 检索）...")
from graph.builder import build_graph
from agents.state import SpecMindState

graph = build_graph()
initial_state: SpecMindState = {
    "raw_input": "客户：智联慧学教育科技\n需求：在线教育平台，收集学生人脸信息用于考勤，学生数据存储在海外服务器。",
    "client_info": {"client_name": "智联慧学"},
}
config = {"configurable": {"thread_id": "e2e_upload_test"}}
final = graph.invoke(initial_state, config)
print(f"   风险等级: {final.get('legal_risk_level')}")
print(f"   是否阻断: {final.get('legal_blocked')}")
issues = final.get("legal_issues", [])
print(f"   法条命中: {len(issues)} 条")
for li in issues[:3]:
    print(f"     - {li.get('law', '?')}: {li.get('issue', '?')[:80]}")

print()
print("✅ 全部通过！")
