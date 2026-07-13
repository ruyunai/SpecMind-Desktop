# AGENTS.md

> 本文件为 AI 编程代理（含 Trae/Cursor/Copilot 等）在本仓库工作时的标准指南。
> 首次进入项目请通读本文件，再查阅 `memory-bank/` 下 7 个记忆文件。

---

## 1. 项目概览

**SpecMind Desktop** 是一款 ToB 企业级本地 Windows 桌面应用，使用 7 个 LangGraph Agent 协同将脏销售需求（微信记录/口头承诺/文档）在 15 分钟内转化为可落地的标准化 PRD + 报价 + 合同比对 + 评审 + 交付计划。

| 维度 | 说明 |
|------|------|
| 项目类型 | 单文件 Windows exe（PyInstaller 打包，98.5MB） |
| 核心目标 | PRD 产出从 4h → 15min，一次通过率提升至 75%+ |
| 部署模式 | 本地优先 / U 盘便携 / Git 下载源码部署 |
| 数据隔离 | 全部本地存储，禁止任何云端协作/上报依赖 |
| LLM 路由 | DeepSeek（OpenAI 兼容协议），按 Agent 角色路由 |
| 工作流 | LangGraph StateGraph，7 节点 + Interrupt 高风险阻断 |

---

## 2. 项目结构

```
BDWD/
├── AGENTS.md                      # 本文件 - AI 代理工作指南
├── README.md                      # 项目说明
├── requirements.txt               # Python 依赖清单
├── SpecMindDesktop.spec           # PyInstaller 打包配置
├── config/
│   └── app.json                   # 应用配置（明文，含 base_url/data_dir）
├── docs/
│   ├── deploy.md                  # 三种部署方式说明
│   └── usage.md                   # 7 步使用指南
├── memory-bank/                   # 项目记忆库（会话开始必读 7 文件）
│   ├── 项目概要.md
│   ├── 产品背景.md
│   ├── 架构设计.md
│   ├── 技术环境.md
│   ├── 当前状态.md
│   ├── 进度追踪.md
│   └── 修复日志.md
├── src/
│   ├── main.py                    # 应用入口
│   ├── __init__.py
│   ├── agents/                    # LangGraph 节点函数 + LLM 客户端
│   │   ├── state.py               # SpecMindState TypedDict + Enum + reducer
│   │   ├── mock_agents.py         # 7 Agent 节点实现（含 LLM 调用 + mock 回退）
│   │   ├── rag_agents.py          # SAR/Legal/Contract 三 Agent 的 RAG 增强版
│   │   ├── llm_client.py          # ChatOpenAI 统一管理 + 重试机制
│   │   ├── prompts.py             # 各 Agent Prompt 模板
│   │   ├── query_rewriter.py      # 检索查询关键词扩展
│   │   └── confidence.py          # 检索置信度评估 + 降级策略
│   ├── core/                      # 核心编排层
│   │   ├── __init__.py            # 便携模式检测 + 路径解析
│   │   ├── config.py              # 配置加载 + 模型路由 + CostConfig
│   │   ├── crypto.py              # Fernet 加密 + PBKDF2 + 机器绑定
│   │   ├── logger.py              # RotatingFileHandler + JSON Lines 结构化日志
│   │   ├── orchestrator.py        # QThread + LangGraph stream + Interrupt
│   │   └── exporter.py            # PRD 导出（Markdown/Word/JSON）
│   ├── graph/
│   │   └── builder.py             # StateGraph 构建 + 条件路由 + SqliteSaver
│   ├── gui/                       # PySide6 三栏界面
│   │   ├── main_window.py         # QMainWindow + 信号槽连接
│   │   ├── widgets/
│   │   │   ├── asset_library.py   # 左栏：企业资产库（上传/删除/检索）
│   │   │   ├── workspace.py       # 中栏：需求输入 + PRD 预览 + 附件导出
│   │   │   └── workflow_canvas.py # 右栏：节点状态 + 拓扑图 + 实时日志
│   │   ├── dialogs/
│   │   │   ├── model_config_dialog.py  # Ctrl+, 模型配置 + 成本参数
│   │   │   ├── upload_dialog.py        # 文档上传对话框
│   │   │   └── asset_detail_dialog.py  # 资产详情查看
│   │   ├── services/
│   │   │   └── upload_service.py  # 文档解析→分块→向量化→入库
│   │   └── styles/
│   │       └── dark_theme.qss     # 深色主题样式表
│   ├── parsers/                   # 文档解析层
│   │   ├── doc_parser.py          # .docx/.pdf/.txt/.json 统一入口
│   │   └── chunker.py             # 结构化分块（法条按条/合同按款/PRD 按 8 模块）
│   └── storage/                   # 存储层
│       ├── schema.py              # AssetCategory 枚举 + AssetMeta dataclass
│       ├── chroma_store.py        # ChromaDB 向量库 + hash 去重 + _flatten_meta
│       ├── sqlite_store.py        # SQLite FTS5 BM25 + 审计日志 + 资产表
│       ├── retriever.py           # 混合检索（向量+BM25+RRF 融合）
│       ├── seed_data.py           # 种子数据（首次启动初始化）
│       └── __init__.py
└── tests/                         # pytest 测试套件
    ├── test_langgraph_workflow.py # 7 节点工作流验证
    ├── test_legal_block.py        # Legal 高风险 Interrupt 阻断
    ├── test_rag_eval.py           # RAG 评估（Recall@5 + Prompt 安全 + 置信度）
    ├── test_eval_regression.py    # Eval 回归 CI 门禁（5 项阈值断言）
    ├── test_gui_e2e.py            # GUI 真实环境端到端
    ├── test_gui_startup.py        # GUI 启动验证
    ├── test_production_readiness.py # 生产就绪 18 项验证
    ├── test_audit_*.py            # 审计日志 3 阶段测试
    ├── test_crypto_s1.py          # 加密/密钥派生
    ├── test_exporter.py           # 导出器
    ├── test_upload_e2e.py         # 上传管线
    └── test_model_config.py       # 模型配置
```

---

## 3. 开发环境

### 3.1 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 桌面 GUI | PySide6 | 6.11.1 (abi3) | 三栏 QMainWindow |
| Agent 编排 | langgraph | 0.2.34 | StateGraph + 条件边 + Interrupt |
| Checkpoint | langgraph-checkpoint-sqlite | 3.1.0 | SqliteSaver 持久化 |
| LLM 抽象 | langchain-openai | 0.1.x | OpenAI 兼容协议接入 DeepSeek |
| 向量库 | chromadb | 1.5.9 | 企业文档向量检索 |
| 关系库 | sqlite3 | 标准库 | 审计日志 + FTS5 BM25（trigram 分词） |
| 加密 | cryptography | 43.x | Fernet 对称加密 API Key |
| 文档解析 | python-docx / PyPDF2 | 1.1.x / 3.0.x | .docx / .pdf 导入 |
| 打包 | pyinstaller | 6.21.0 | 单文件 exe |
| Python | CPython | 3.14.x | 主开发版本 |

### 3.2 环境准备

```powershell
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key（首次运行通过 GUI Ctrl+, 输入，自动加密存储）
#    或设置环境变量：SPECMIND_API_KEY
```

### 3.3 运行

```powershell
# 开发模式（带控制台日志）
python src/main.py

# 打包 exe
pyinstaller --noconfirm SpecMindDesktop.spec
# 输出：dist/SpecMindDesktop.exe（98.5MB）
```

---

## 4. 构建、运行与测试命令

```powershell
# 启动应用
python src/main.py

# 运行全部测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_langgraph_workflow.py -v       # 7 节点工作流
pytest tests/test_rag_eval.py -v                  # RAG 评估
pytest tests/test_eval_regression.py -v           # CI 门禁（5 项阈值）
pytest tests/test_gui_e2e.py -v                   # GUI 端到端
pytest tests/test_production_readiness.py -v      # 生产就绪 18 项

# 打包 exe
pyinstaller --noconfirm SpecMindDesktop.spec

# 初始化种子数据（首次部署或重置知识库）
python -m storage.seed_data
```

---

## 5. 代码规范

### 5.1 通用规范

- **单文件 ≤ 200 行**：超出按职责拆分
- **函数必须有文档注释**：说明 Args / Returns
- **新功能必须有测试**：tests/ 下新增对应 test_*.py
- **禁止硬编码密钥/凭据**：API Key 必须用 Fernet 加密，严禁明文落盘
- **Python 代码遵循 PEP 8**，类型注解必填

### 5.2 PySide6 信号槽

- 信号命名：`signal_name`（如 `node_started`、`workflow_complete`）
- 槽函数命名：`on_signal_name`（如 `on_node_started`、`on_workflow_complete`）
- 长耗时操作必须移入 QThread，主线程只负责 UI 更新
- Widget 必须设置 parent，定时器必须在不需要时停止
- **closeEvent 线程终止三层策略**：`cancel()` 设置取消标志 + 解除阻塞 → `wait(3000)` 等待自然退出 → `terminate()` 强制终止兜底。禁止仅用 `quit()`（对自定义 run() 的 QThread 无效）
- **QDialog 长耗时操作（如上传/导出）必须使用 QThread + Worker QObject 模式**：Worker 继承 QObject 含 `finished`/`error` 信号，`moveToThread` 后启动；主线程通过信号回调更新 UI，禁止在主线程同步调用

### 5.3 LangGraph 节点规范

- **节点函数签名统一**：`def node_name(state: State) -> State`（实际返回部分 dict）
- **节点只返回本节点新增/更新的字段**：禁止返回完整 state（会触发 `InvalidUpdateError`）
- **并行节点不能返回相同字段**（除非该字段有 `Annotated[..., reducer]`）
- **节点 entry/exit 必须 State 快照入 SQLite**（审计完整约束）

### 5.4 Agent Prompt 规范

- **System Message 首行必须明确身份定位**（如"你是 SpecMind 的 Legal Agent..."）
- **Legal Agent 输出必须附带"辅助预检，非正式法律意见"声明**
- **引用必须溯源**：LLM 响应只能使用检索结果，附法条编号等来源
- **低置信度必须降级**：平均相似度 <0.6 触发人工复核提示

---

## 6. 关键架构约定

### 6.1 工作流拓扑

```
SAR Agent → Legal Agent → [Interrupt 高风险阻断]
                          ↓ 低风险/确认放行
                       PM Agent → 生成 PRD
                          ↓
              ┌───────────┼───────────┐
              ↓           ↓           ↓
        Commercial    Contract     Review（Tech/Design/QA）
              ↓           ↓           ↓
              └───────────┴───────────┘
                          ↓
                     Planner Agent → 交付计划
```

- SAR/Legal/Contract 使用 RAG 增强（检索企业文档）
- PM/Review/Planner 直接调用 LLM
- Commercial 不调用 LLM，使用公式驱动（基于 CostConfig × prd_features）

### 6.2 State 结构（`src/agents/state.py`）

`SpecMindState` TypedDict 关键字段：

| 字段 | 类型 | 写入节点 |
|------|------|---------|
| `raw_input` | str | 输入 |
| `cleaned_requirements` | str | SAR |
| `overcommit_risks` | List[str] | SAR |
| `legal_risk_level` | str（"low"/"medium"/"high"） | Legal |
| `legal_issues` | List[Dict] | Legal |
| `legal_blocked` | bool | Legal |
| `prd` | Dict[str, str]（8 模块） | PM |
| `prd_features` | List[Dict]（含 tag） | PM |
| `quotes` | Dict[str, Dict] | Commercial |
| `contract_conflicts` | List[Dict] | Contract |
| `review_comments` | Dict[str, List[str]] | Review |
| `review_pass` | bool | Review |
| `delivery_plan` | List[Dict] | Planner |
| `audit_snapshots` | Annotated[List, operator.add] | 所有节点（reducer 并行安全） |

**功能点 tag 枚举**：`标准功能` / `定制功能` / `暂不支持`

### 6.3 模型路由

| Agent | 默认模型 | 用途 |
|-------|---------|------|
| SAR | deepseek-chat | 需求清洗（轻量） |
| Legal | deepseek-chat | 合规预检 |
| PM | deepseek-chat | PRD 生成 |
| Commercial | （不调 LLM） | 公式计算 |
| Contract | deepseek-chat | 合同比对 |
| Review | deepseek-chat | 三维评审 |
| Planner | deepseek-chat | 交付计划 |

所有 Agent 通过 `https://api.deepseek.com/v1` 接入，可通过 GUI（Ctrl+, → 模型配置）逐 Agent 自定义 model/base_url/api_key。

### 6.4 存储分层

| 数据类型 | 存储 | 路径 |
|---------|------|------|
| 向量资产（企业文档） | ChromaDB | `<app_root>/data/chroma/` |
| 审计日志 + 资产 FTS | SQLite | `<app_root>/data/specmind.db` |
| LangGraph checkpoint | SQLite | `<app_root>/data/checkpoints.db` |
| 应用日志 | 文件 | `<app_root>/logs/specmind.log` + `.1/.2/.3` |
| 加密 API Key | Fernet | `<app_root>/config/secrets.enc` |

**路径解析规则**（`src/core/__init__.py`）：
- 便携模式（exe 同级存在 `portable.dat`）→ exe 同级目录
- 开发模式 → 项目根目录
- frozen 模式 → `%APPDATA%/SpecMindDesktop/`

### 6.5 RAG 检索规范

- **混合检索**：ChromaDB 向量 + SQLite FTS5 BM25 + RRF 融合（k=60）
- **FTS5 分词**：trigram（3 字符滑窗），中文短语匹配
- **查询分流**：<3 字符 LIKE / 3-5 字符 trigram MATCH / ≥6 字符 4 字符滑窗 OR 合并
- **置信度阈值**：avg≥0.75 high / 0.6-0.75 medium / 0.4-0.6 low（降级）/ <0.4 empty（强降级）
- **Legal 空结果必须阻断工作流**

---

## 7. 常见任务

### 7.1 新增 Agent 节点

1. 在 `src/agents/state.py` 添加该 Agent 输出的 State 字段
2. 在 `src/agents/mock_agents.py` 实现 `def new_agent(state) -> dict`，只返回新字段
3. 在 `src/agents/prompts.py` 添加 Prompt 模板（System 首行明确身份）
4. 在 `src/graph/builder.py` 注册节点 + 添加边/条件路由
5. 在 `src/core/orchestrator.py` 节点列表中添加该节点名
6. 新增 `tests/test_new_agent.py` 覆盖

### 7.2 修改 PRD 模板

8 个强制模块不可缺：背景目标 / 用户故事 / 功能列表 / In/Out 范围 / 验收标准 / 非功能需求 / 埋点要求 / 风险章节。

修改位置：`src/agents/prompts.py` 的 `build_pm_prompt()` + `src/agents/mock_agents.py` 的 `pm_agent()` 回退分支。

### 7.3 新增知识库分类

1. `src/storage/schema.py` 的 `AssetCategory` 枚举新增成员
2. `src/gui/widgets/asset_library.py` 的 `CATEGORY_GROUPS` 同步新增分组（**key 必须严格等于 `AssetCategory.XXX.value`**，禁止使用变体如 `standard_feature` vs `feature`，否则 `AssetCategory(cat_key)` 抛 ValueError）
3. `src/agents/query_rewriter.py` 关键词字典按需扩展
4. 如需新解析规则，更新 `src/parsers/chunker.py`
5. 上传对话框 `src/gui/dialogs/upload_dialog.py` 的 `QComboBox` 项需同步新增分类选项，格式 `"显示名 (key)"`

### 7.4 修改成本参数

GUI 路径：Ctrl+, → 成本参数 Tab。配置项：
- `person_day_rate`：人天费率（元）
- `days_per_std_feature`：标准功能人天/个
- `custom_multiplier`：定制功能倍率
- `margin_rate`：毛利率
- `maintenance_rate`：维护费率

### 7.5 打包发布

```powershell
# 1. 清理旧产物
rmdir /s /q build dist

# 2. 打包
pyinstaller --noconfirm SpecMindDesktop.spec

# 3. 验证启动
dist\SpecMindDesktop.exe

# 4. U 盘便携化：在 exe 同级创建空文件 portable.dat
```

---

## 8. 调试

### 8.1 日志位置

- 应用日志：`<app_root>/logs/specmind.log`（RotatingFileHandler，5MB×3）
- 结构化日志：`<app_root>/logs/specmind.jsonl`（frozen 模式自动启用）
- 审计日志：SQLite `audit_logs` 表（含 `run_id` / `elapsed_ms`）

### 8.2 性能指标查询

```python
from storage.sqlite_store import get_store
store = get_store()
# 节点耗时统计（avg/min/max/cnt/errors）
stats = store.get_node_timing_stats()
# 工作流汇总（total_elapsed/node_count/status）
summary = store.get_workflow_summary()
```

### 8.3 常见问题排查

| 现象 | 排查方向 |
|------|---------|
| 启动后状态栏提示"知识库为空" | 正常现象，需在左栏上传企业文档 |
| LLM 调用失败 | 检查 Ctrl+, → API Key；查看 `specmind.log` 中的 `[LLM]` 行 |
| RAG 相似度低触发降级 | 知识库文档少导致，上传更多企业文档即可 |
| Legal 高风险阻断 | 弹窗确认是否强制放行，强放行需自行承担合规风险 |
| exe 双击被 SmartScreen 拦截 | 未代码签名，点击"仍要运行" |
| FTS5 中文搜索召回低 | 短词走 LIKE 回退属正常；长词检查 trigram 滑窗逻辑 |

---

## 9. 硬约束清单（不可违反）

| 约束 | 说明 |
|------|------|
| 本地优先 | 禁止引入任何云端协作/上报依赖，数据仅本地存储 |
| 加密强制 | API Key 必须用 Fernet 加密，严禁明文落盘/入日志 |
| Interrupt 强制 | Legal 高风险必须阻断 PRD 生成，高风险操作必须弹出人工确认 |
| Legal 声明强制 | Legal Agent 输出必须附带"辅助预检，非正式法律意见"声明 |
| 模型路由 | 按 Agent 角色路由，可通过 GUI 自定义 |
| PRD 模板 | 8 个强制模块不可缺 |
| 功能点标注 | 每个功能点必须标注「标准功能/定制功能/暂不支持」 |
| 审计完整 | 每个 LangGraph 节点 entry/exit 必须 State 快照入 SQLite |
| 检索规范 | 混合检索（向量+BM25+RRF）+ reranking，低置信度必须降级 |
| Checkpointer | 路径必须使用绝对项目根路径 |
| LLM 重试 | 必须包含 3 次重试 + 指数退避（2s→4s→8s） |

---

## 10. 禁止事项

- 禁止单次重构整个代码库
- 禁止不更新记忆库就换技术栈
- 禁止重复尝试 `memory-bank/修复日志.md` 中已标记失败的方案
- 禁止留 TODO 不在 `进度追踪.md` 中记录
- 禁止 Legal Agent 输出未声明"辅助预检"的合规结论
- 禁止高风险操作绕过 Interrupt 自动执行
- 禁止 API Key 明文写入配置文件/日志/State
- 禁止引入 jieba 等大词典依赖（trigram 已达成 100% Recall@5）
- 禁止 ChromaDB 嵌套 dict 入 metadata（必须 `_flatten_meta` 平铺）

---

## 11. 会话流程约定

### 11.1 会话开始必做

1. 阅读 `memory-bank/` 下全部 7 个文件
2. 查阅 `修复日志.md`，避免重复已失败方案
3. 确认当前焦点（`当前状态.md`）

### 11.2 会话结束必做

1. 更新 `当前状态.md`（变更 + 下一步）
2. 更新 `进度追踪.md`（完成/进行中/待做）
3. Bug 修复追加到 `修复日志.md`（按 BUG-XXX 编号递增），每条记录必含：现象/根因/修复方案/是否成功/涉及文件/日期/备注

### 11.3 提交规范

- Git commit message 用中文，说明"为什么"而非"做了什么"
- 禁止 `git add -A`，按文件名添加避免误带敏感文件
- 禁止提交 `.env` / `secrets.enc` / `config/app.json`（含加密 Key）

---

## 12. 参考文档

- 部署指南：`docs/deploy.md`
- 使用说明：`docs/usage.md`
- 架构设计：`memory-bank/架构设计.md`
- 技术环境：`memory-bank/技术环境.md`
- 修复历史：`memory-bank/修复日志.md`
