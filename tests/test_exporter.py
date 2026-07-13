"""导出模块单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.exporter import export_prd_as_markdown, export_prd_as_word, export_full_report_as_json


def _sample_state():
    """构造一个模拟工作流 State。"""
    return {
        "cleaned_requirements": "K12 在线教育平台",
        "overcommit_risks": ["终身免费升级", "10万并发"],
        "prd": {
            "背景目标": "为 K12 教育机构提供平台",
            "用户故事": "教师排课、学生上课",
            "功能列表": "课程管理、直播、作业",
            "In_Out范围": "In: 核心教学; Out: AI推荐",
            "验收标准": "直播延迟≤2s",
            "非功能需求": "支持1000人在线",
            "埋点要求": "课程点击、支付转化",
            "风险章节": "数据合规风险",
        },
        "prd_features": [
            {"name": "课程管理", "tag": "标准功能", "desc": "核心功能"},
            {"name": "10万并发", "tag": "暂不支持", "desc": "超出标准版"},
        ],
        "quotes": {
            "标准版": {"开发费": 360000, "维护费": 36000, "毛利率": 0.4},
            "裁剪版": {"开发费": 240000, "维护费": 24000, "毛利率": 0.4},
        },
        "contract_conflicts": [
            {
                "risk": "high",
                "prd_clause": "终身免费升级",
                "contract_clause": "首年免费维护",
                "conflict": "销售承诺与合同条款不一致",
            }
        ],
        "review_comments": {
            "tech": ["建议使用 WebRTC"],
            "design": ["增加学习日历"],
            "qa": ["并发测试覆盖"],
        },
        "review_pass": True,
        "delivery_plan": [
            {"phase": "需求确认", "duration": "1周", "deliverable": "PRD 终稿"},
            {"phase": "开发阶段", "duration": "3周", "deliverable": "核心功能"},
        ],
    }


def test_export_markdown():
    """测试 Markdown 导出。"""
    print("\n[1] Markdown 导出测试")
    md = export_prd_as_markdown(_sample_state(), client_name="智联慧学")
    assert "# SpecMind PRD 输出 - 智联慧学" in md
    assert "## 二、PRD 文档（8 模块）" in md
    assert "课程管理 | 标准功能 | 核心功能" in md
    assert "总工期：4 周" in md
    assert "辅助预检工具" in md
    print("    ✓ Markdown 内容正确")


def test_export_word(tmp_path: Path):
    """测试 Word 导出。"""
    print("\n[2] Word 导出测试")
    output = tmp_path / "test_prd.docx"
    export_prd_as_word(_sample_state(), output, client_name="智联慧学")
    assert output.exists()
    assert output.stat().st_size > 0
    print(f"    ✓ Word 文件生成: {output.stat().st_size} bytes")


def test_export_json(tmp_path: Path):
    """测试 JSON 导出。"""
    print("\n[3] JSON 导出测试")
    output = tmp_path / "test_report.json"
    export_full_report_as_json(_sample_state(), output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert '"state"' in content
    assert "智联慧学" not in content  # state 中没有 client_name
    print(f"    ✓ JSON 文件生成: {len(content)} 字符")


if __name__ == "__main__":
    import tempfile
    print("=" * 80)
    print("导出模块单元测试")
    print("=" * 80)

    test_export_markdown()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_export_word(tmp)
        test_export_json(tmp)

    print("\n✅ 导出模块测试通过")
