"""验证 7 个 Bug 修复的快速测试脚本（不依赖 GUI/LLM）。"""
import sys
sys.path.insert(0, 'src')


def test_all():
    """运行所有验证。"""
    # 1. prompts.py 导入
    from agents.prompts import (
        build_legal_prompt, build_contract_prompt, build_sar_prompt,
        build_pm_prompt, build_review_prompt, build_planner_prompt
    )
    print("✅ prompts.py 6 个函数导入成功")

    # 2. mock_agents.py 导入
    from agents.mock_agents import (
        _extract_json, _parse_llm_features, _parse_llm_delivery_plan, _clean_markdown
    )
    print("✅ mock_agents.py 导入成功")

    # 3. confidence.py 导入
    from agents.confidence import should_block_workflow
    print("✅ confidence.py 导入成功")

    # 4. doc_parser.py 导入
    from parsers.doc_parser import parse_document, _table_rows_to_markdown
    print("✅ doc_parser.py 导入成功")

    # 5. schema.py + upload_service.py
    from storage.schema import AssetCategory
    assert AssetCategory.GENERIC.value == "generic"
    from gui.services.upload_service import CATEGORY_MAP
    assert CATEGORY_MAP["generic"]["category"] == AssetCategory.GENERIC
    print("✅ schema.py GENERIC 枚举 + upload_service 映射正确")

    # 6. 测试 _extract_json
    test1 = _extract_json('{"risk_level": "high", "legal_issues": []}')
    assert isinstance(test1, dict) and test1["risk_level"] == "high"
    print("✅ _extract_json dict 测试通过")

    test2 = _extract_json('[{"phase": "test"}]')
    assert isinstance(test2, list) and len(test2) == 1
    print("✅ _extract_json list 测试通过")

    test3 = _extract_json('```json\n{"key": "value"}\n```')
    assert isinstance(test3, dict) and test3["key"] == "value"
    print("✅ _extract_json markdown 清理测试通过")

    # 7. 测试表格转 Markdown
    md = _table_rows_to_markdown([["A", "B"], ["1", "2"]])
    assert "| A | B |" in md and "| --- | --- |" in md and "| 1 | 2 |" in md
    print("✅ 表格转 Markdown 测试通过")

    # 8. 测试 Prompt 生成（不调用 LLM）
    legal_prompt = build_legal_prompt("测试需求", [], low_confidence=False)
    assert "你是 SpecMind 的 Legal Agent" in legal_prompt
    assert "法律知识为首要依据" in legal_prompt
    print("✅ Legal Prompt 生成测试通过（LLM 知识为主）")

    sar_prompt = build_sar_prompt("测试需求", [])
    assert "产品知识" in sar_prompt and "首要参考" in sar_prompt
    print("✅ SAR Prompt 生成测试通过（LLM 知识为主）")

    contract_prompt = build_contract_prompt("PRD", "合同", [])
    assert "合同知识为首要参考" in contract_prompt
    print("✅ Contract Prompt 生成测试通过（LLM 知识为主）")

    # 9. workspace.py 函数测试
    from gui.widgets.workspace import _extract_weeks, _format_duration
    assert _extract_weeks({"duration": "3周"}) == 3
    assert _extract_weeks({"duration": 3}) == 3
    assert _extract_weeks({"weeks": "2"}) == 2
    assert _extract_weeks({}) == 0
    print("✅ workspace._extract_weeks 安全解析测试通过")

    # 10. asset_library.py CATEGORY_GROUPS
    from gui.widgets.asset_library import CATEGORY_GROUPS
    keys = [k for _, k, _ in CATEGORY_GROUPS]
    assert "prd" in keys and "generic" in keys
    print("✅ asset_library CATEGORY_GROUPS 含 prd + generic")

    print("\n🎉 全部 10 项验证通过！")


if __name__ == "__main__":
    test_all()
