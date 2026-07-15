<div align="center">

# SpecMind Desktop

### AI 驱动的 ToB 标准化 PRD 产出平台

将脏销售需求（微信记录 / 口头承诺 / 文档）在 **15 分钟** 内转化为可落地的标准化 PRD + 报价 + 合同比对 + 评审 + 交付计划

[![Release](https://img.shields.io/badge/版本-v0.2.0-blue)](https://github.com/ruyunai/SpecMind-Desktop/releases)
[![Platform](https://img.shields.io/badge/平台-Windows%2010%2F11-brightgreen)](https://github.com/ruyunai/SpecMind-Desktop/releases)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## 📥 立即下载

| 项目 | 说明 |
|------|------|
| **下载链接** | [SpecMindDesktop.exe](https://github.com/ruyunai/SpecMind-Desktop/releases/latest/download/SpecMindDesktop.exe) |
| **文件大小** | 130.52 MB |
| **系统要求** | Windows 10 / 11 64 位 |
| **无需安装** | 双击即用，无需 Python 或任何依赖 |

> 💡 若浏览器直接播放或预览，请右键链接 → 「链接另存为」下载。
> 首次启动若提示缺 `VCRUNTIME140.dll`，安装 [VC++ Redistributable 2015-2022](https://aka.ms/vs/17/release/vc_redist.x64.exe)。

---

## 🚀 快速开始（3 步）

### 1️⃣ 下载并启动

点击上方下载链接获取 `SpecMindDesktop.exe` → 双击运行。

> 若被 Windows SmartScreen 拦截：点击「更多信息」→「仍要运行」（exe 未代码签名，属正常现象）。

### 2️⃣ 配置 API Key

应用启动后，按 `Ctrl + ,` 打开模型配置：

- **API Key**：粘贴你的 DeepSeek API Key（格式 `sk-xxxxxxxx`）
  - 没有就到 https://platform.deepseek.com/ 注册并充值 ¥10
- **Base URL**：保持默认 `https://api.deepseek.com/v1`
- **模型**：保持默认 `deepseek-chat`
- 点击「保存」（Key 自动 Fernet 加密存储，绝不明文落盘）

### 3️⃣ 上传企业文档 + 执行工作流

1. **左栏**「企业资产库」→ 点击「上传」→ 选择企业文档（`.docx` / `.pdf` / `.txt`）
   - 推荐上传：企业标准功能清单、相关法规、合同模板
2. **中栏**输入需求（例如：`客户：XX教育；需求：在线教育平台含课程和支付`）
3. 点击「开始执行」（或 `Ctrl+Enter`）
4. **右栏** 7 个 Agent 节点依次变绿（约 60-90 秒）→ 中栏生成完整 PRD

---

## ✨ 核心功能

| 模块 | 能力 |
|------|------|
| **7 Agent 协同** | SAR（需求清洗）→ Legal（合规预检）→ PM（PRD 生成）→ Commercial（报价）+ Contract（合同比对）+ Review（三维评审）→ Planner（交付计划） |
| **企业知识库** | 本地 ChromaDB 向量库 + SQLite FTS5 BM25 混合检索，支持企业自有文档上传 |
| **高风险阻断** | Legal 检测高风险自动 Interrupt，弹出人工确认对话框，强放行需自负风险 |
| **标准 PRD 模板** | 8 个强制模块：背景目标 / 用户故事 / 功能列表 / In-Out 范围 / 验收标准 / 非功能需求 / 埋点要求 / 风险章节 |
| **功能点标注** | 每个功能点自动标注「标准功能 / 定制功能 / 暂不支持」 |
| **双报价生成** | 标准版 + 裁剪版动态报价，基于企业成本参数公式驱动 |
| **完整审计** | 每个 Agent 节点 entry/exit 快照入 SQLite，含耗时统计 |
| **本地优先** | 全部数据本地存储，禁止任何云端协作/上报依赖 |

---

## 📦 部署方式

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| **exe 双击运行** | 单台电脑长期使用 | 数据存于 `%APPDATA%\SpecMindDesktop\` |
| **U 盘便携模式** | 多电脑切换、外勤演示 | exe 同级创建空文件 `portable.dat` 即可 |
| **源码部署** | 开发者二次开发 | `git clone` + `pip install -r requirements.txt` |

### U 盘便携模式（3 步）

```powershell
# 1. 在 U 盘创建目录
mkdir E:\SpecMindDesktop

# 2. 拷贝 exe
copy SpecMindDesktop.exe E:\SpecMindDesktop\

# 3. 创建便携标记文件（空文件即可）
New-Item -Path E:\SpecMindDesktop\portable.dat -ItemType File

# 完成！U 盘插任何电脑双击 exe 即可，数据全部写入 U 盘
```

📖 **完整部署手册**：[docs/deploy.md](docs/deploy.md)（含三种模式详细步骤、U 盘迁移流程、备份恢复、12 类常见问题排查）

---

## 🏗️ 项目架构

### 1. 整体架构（六层分离）

```mermaid
graph TD
    subgraph GUI["🖥 GUI 层 · PySide6 6.11"]
        Left["左栏：企业资产库<br/>QTreeView + ChromaStore<br/>上传/删除/检索/详情"]
        Mid["中栏：工作区三 Tab<br/>QTabWidget<br/>需求输入 / PRD 预览 / 附件导出"]
        Right["右栏：LangGraph 画布<br/>节点状态 + 拓扑图 + 实时日志"]
        Left ~~~ Mid ~~~ Right
    end

    subgraph Core["⚙ Core 层 · 编排与基础设施"]
        Orch["Orchestrator<br/>QThread + LangGraph stream<br/>Interrupt 阻断 + 人工确认"]
        Cfg["Config<br/>AppConfig + AgentModelConfig<br/>CostConfig 报价参数"]
        Crypto["Crypto<br/>Fernet + PBKDF2 + 机器绑定<br/>旧格式自动迁移"]
        Log["Logger<br/>RotatingFileHandler 5MB×3<br/>JSON Lines 结构化日志"]
    end

    subgraph Agent["🤖 Agent 层 · 7 个 LangGraph 节点"]
        SAR["SAR Agent<br/>RAG 增强 · 需求清洗"]
        Legal["Legal Agent<br/>RAG 增强 · 合规预检"]
        PM["PM Agent<br/>LLM · PRD 生成"]
        Comm["Commercial Agent<br/>公式驱动 · 双报价"]
        Contract["Contract Agent<br/>RAG 增强 · 合同比对"]
        Review["Review Agent<br/>LLM · Tech/Design/QA 评审"]
        Planner["Planner Agent<br/>LLM · 交付计划"]
    end

    subgraph Graph["🔗 Graph 层 · LangGraph 0.2.34"]
        SG["StateGraph<br/>条件边 + fan-out/fan-in"]
        CP["SqliteSaver Checkpoint<br/>State 持久化 + 回溯"]
        Route["条件路由<br/>Legal 高风险 -> END<br/>低风险 -> PM"]
    end

    subgraph Storage["💾 Storage 层 · 本地优先"]
        Chroma["ChromaDB 1.5.9<br/>向量资产库<br/>bge-m3 嵌入 + hash 去重"]
        SQLite["SQLite<br/>FTS5 BM25 (trigram)<br/>审计日志 + 资产表"]
        CKPT["Checkpoint SQLite<br/>LangGraph State 快照"]
        FLog["应用日志<br/>RotatingFileHandler<br/>specmind.log / .jsonl"]
        Enc["加密存储<br/>secrets.enc<br/>Fernet 加密 API Key"]
    end

    subgraph Parsers["📄 Parsers 层 · 文档解析"]
        DocParser["doc_parser<br/>.docx / .pdf / .txt / .json"]
        Chunker["chunker<br/>法条按条 / 合同按款<br/>PRD 按 8 模块"]
    end

    GUI --> Core
    Core --> Graph
    Graph --> Agent
    Agent --> Storage
    Parsers --> Storage
    Agent -->|LLM 调用| LLM["DeepSeek API<br/>OpenAI 兼容协议<br/>3 次重试 + 指数退避"]
    SAR -->|RAG| Chroma
    Legal -->|RAG| Chroma
    Legal -->|RAG| SQLite
    Contract -->|RAG| Chroma
    Contract -->|RAG| SQLite
```

**技术栈**：PySide6 + LangGraph 0.2 + ChromaDB + SQLite FTS5 + DeepSeek API + PyInstaller

### 2. LangGraph Agent 工作流

```mermaid
flowchart LR
    START((START)) --> SAR["🧹 SAR Agent<br/>需求清洗<br/>RAG 增强"]

    SAR --> Legal["⚖ Legal Agent<br/>合规预检<br/>RAG 增强"]

    Legal -->|legal_blocked=true| Interrupt{{"⛔ Interrupt<br/>高风险人工确认<br/>threading.Event"}}
    Legal -->|legal_blocked=false<br/>低风险放行| PM["📝 PM Agent<br/>PRD 生成<br/>LLM 驱动"]

    Interrupt -->|用户拒绝| END1((END 终止))
    Interrupt -->|用户强制放行| Resume["🔄 Resume 图<br/>从 PM 继续执行"]

    PM --> FanOut{"fan-out<br/>并行执行"}
    Resume --> FanOut

    FanOut --> Comm["💰 Commercial<br/>双报价<br/>公式驱动"]
    FanOut --> Cntr["📋 Contract<br/>合同比对<br/>RAG 增强"]
    FanOut --> Rev["🔍 Review<br/>三维评审<br/>LLM 驱动"]

    Comm --> FanIn{"fan-in"}
    Cntr --> FanIn
    Rev --> FanIn

    FanIn --> Planner["📅 Planner Agent<br/>交付计划<br/>LLM 驱动"]
    Planner --> END2((END 完成))

    subgraph Checkpoint["SqliteSaver 持久化"]
        CP_Entry["节点 entry<br/>State 快照"]
        CP_Exit["节点 exit<br/>State 快照 + elapsed_ms"]
    end

    SAR -.->|审计| CP_Entry
    SAR -.->|审计| CP_Exit
    Legal -.->|审计| CP_Entry
    Legal -.->|审计| CP_Exit

    style Interrupt fill:#ff6b6b,stroke:#c0392b,color:#fff
    style END1 fill:#e74c3c,stroke:#c0392b,color:#fff
    style END2 fill:#27ae60,stroke:#1e8449,color:#fff
```

### 3. RAG 混合检索架构

```mermaid
graph LR
    subgraph Upload["📤 文档上传管线"]
        File["文件选择<br/>.docx/.pdf/.txt/.json"]
        Parse["doc_parser<br/>统一解析入口"]
        Chunk["chunker<br/>结构化分块"]
        Embed["ChromaDB<br/>bge-m3 嵌入"]
        Store["入库<br/>hash 去重<br/>_flatten_meta"]
        File --> Parse --> Chunk --> Embed --> Store
    end

    subgraph Query["🔍 查询检索管线"]
        Input["用户查询"]
        QR["query_rewriter<br/>词典改写<br/>+ LLM 扩展"]
        LLM_Expand["方案 D: llm_expand_query<br/>LLM 生成 2-4 个<br/>语义等价变体"]
        MultiQ["retrieve_multi_query<br/>多查询并行检索"]
        Vec["向量检索<br/>ChromaDB<br/>Top 10"]
        BM25["BM25 检索<br/>SQLite FTS5<br/>trigram 分词<br/>Top 10"]
        RRF["RRF 融合<br/>k=60 重排"]
        Conf["置信度评估<br/>avg≥0.75 high<br/>0.6-0.75 medium<br/>0.4-0.6 low 降级<br/><0.4 empty 强降级"]
        Degrade["降级策略<br/>低置信度：KB>LLM<br/>空检索：LLM 自判定"]
        Input --> QR --> LLM_Expand --> MultiQ
        MultiQ --> Vec
        MultiQ --> BM25
        Vec --> RRF
        BM25 --> RRF
        RRF --> Conf --> Degrade
    end

    subgraph Agents["RAG Agent 消费"]
        SAR_A["SAR Agent<br/>检索标准功能库"]
        Legal_A["Legal Agent<br/>检索法规库"]
        Contract_A["Contract Agent<br/>检索合同模板库"]
    end

    Store -.-> Vec
    Store -.-> BM25
    Degrade --> SAR_A
    Degrade --> Legal_A
    Degrade --> Contract_A
```

### 4. 评测体系（三指标 + CI 门禁）

```mermaid
graph LR
    subgraph Dataset["评测数据集"]
        EDS["eval_dataset.json<br/>25 条用例<br/>5 分类: SAR/Legal/Contract/<br/>PM/Review"]
        GroundTruth["标注数据<br/>期望关键词 + 期望分类<br/>期望 risk_level"]
    end

    subgraph Pipeline["评测管线"]
        Upload["构建知识库<br/>clean_knowledge_base()<br/>种子数据入库"]
        RunEval["run_eval.py<br/>执行评测"]
        Recall["Recall@5<br/>检索 Top-5 命中率<br/>文本 + source 双检查"]
        PromptSafe["Prompt 安全性<br/>RAG: 身份+防注入+溯源<br/>Legal: 免责声明<br/>非RAG: 身份+防注入"]
        ConfRate["置信度降级率<br/>低置信度场景<br/>KB>LLM 优先级验证"]
        Upload --> RunEval
        RunEval --> Recall
        RunEval --> PromptSafe
        RunEval --> ConfRate
    end

    subgraph Thresholds["CI 门禁阈值"]
        T1["Recall@5 ≥ 0.85"]
        T2["Prompt 安全 ≥ 0.90"]
        T3["置信度降级率 ≥ 0.90"]
        T4["5/5 项全通过 -> exit(0)"]
        T5["任一不通过 -> exit(1)"]
    end

    subgraph Report["评测报告"]
        Rpt["eval_report_YYYYMMDD.md<br/>25 条用例明细<br/>每条: 命中/缺失/建议<br/>三指标汇总 + 优化建议"]
    end

    Dataset --> Pipeline
    Pipeline --> Thresholds
    Pipeline --> Report

    style T1 fill:#27ae60,stroke:#1e8449,color:#fff
    style T2 fill:#27ae60,stroke:#1e8449,color:#fff
    style T3 fill:#27ae60,stroke:#1e8449,color:#fff
```

**当前指标**：Recall@5 = 0.92 ✅ ｜ Prompt 安全 = 1.00 ✅ ｜ 置信度降级率 = 1.00 ✅

📖 **完整 10 张架构图**：[docs/架构设计_Mermaid图集.md](docs/架构设计_Mermaid图集.md)（含 State 管理 / 数据流 / 存储分层 / 加密 / 模型路由 / 打包部署等 6 张图）

📖 **架构设计说明文档**：[memory-bank/架构设计.md](memory-bank/架构设计.md)

---

## 📚 文档导航

| 文档 | 内容 |
|------|------|
| [docs/deploy.md](docs/deploy.md) | 完整部署操作手册（12 节 + 2 附录） |
| [docs/usage.md](docs/usage.md) | 7 步使用指南 |
| [docs/架构设计_Mermaid图集.md](docs/架构设计_Mermaid图集.md) | 10 张 Mermaid 架构图（整体架构/工作流/RAG/State/数据流/存储/加密/路由/打包/评测） |
| [docs/skill数据报告.md](docs/skill数据报告.md) | 4 个 AI Skill 使用数据报告（效率提升 66% / 32 Bug 修复归档 / 三指标提升） |
| [docs/eval_report_20260714.md](docs/eval_report_20260714.md) | RAG 评测报告（25 条用例 / Recall@5=0.92 / Prompt=1.00） |
| [AGENTS.md](AGENTS.md) | AI 编程代理工作指南（含代码规范、约束） |
| [memory-bank/](memory-bank/) | 项目记忆库（架构 / 状态 / 进度 / 修复日志） |

---

## 🔧 开发者指南

```powershell
# 环境准备
git clone https://github.com/ruyunai/SpecMind-Desktop.git
cd SpecMind-Desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动开发模式
python src/main.py

# 运行测试
python tests/test_stability_core.py        # 核心稳定性 54 项
python tests/test_production_readiness.py  # 生产就绪 18 项
pytest tests/ -v                           # 全套测试

# 构建 exe
pyinstaller --noconfirm SpecMindDesktop.spec
```

📖 详细开发规范见 [AGENTS.md](AGENTS.md)。

---

## 🛡️ 安全与合规

- **本地优先**：全部数据本地存储，禁止任何云端协作/上报依赖
- **API Key 加密**：Fernet + PBKDF2 + 机器绑定，绝不明文落盘
- **Legal 辅助预检**：Legal Agent 输出必附「辅助预检，非正式法律意见」声明
- **完整审计**：每个 LangGraph 节点 entry/exit 快照入 SQLite

---

## 📝 版本历史

### v0.2.0（2026-07-14）

**架构升级 + 人工测试迭代修复 + exe 打包链路修复**

- 🔧 **核心架构变更**：LLM 知识为主 + 企业资产库为辅（替代原 RAG 强约束设计）
- 📄 **文档解析增强**：docx 表格提取 + pdf 换用 pdfplumber（表格还原准确率 90%+）
- 🖥️ **UI 优化**：Interrupt 阻断弹窗改为可滚动自定义对话框
- 🐛 修复 BUG-023 ~ BUG-030 共 8 项（2 致命 + 6 高危）
  - BUG-030（致命）：exe 打包后 LLM 静默回退 mock 数据 → SSL 证书打包 + llm_errors 追踪 + 显式标注
  - BUG-029：Interrupt 弹窗内容过长无法滚动
  - BUG-026（致命）：LLM 只参考企业资产库 → 全部 Prompt 重写
- 📦 **exe 打包修复**：collect_all(chromadb) + certifi 证书 + openai/httpx 全量打包

详见 [Release v0.2.0](https://github.com/ruyunai/SpecMind-Desktop/releases/tag/v0.2.0)。

### v0.1.1（2026-07-14）

- 修复 BUG-009 ~ BUG-022 共 14 项（2 致命 + 12 高危）
- 新增核心稳定性测试 54 项 + 完整部署手册
- 建立 AGENTS.md 标准 AI 代理工作指南

详见 [Release v0.1.1](https://github.com/ruyunai/SpecMind-Desktop/releases/tag/v0.1.1)。

---

## 📄 License

MIT License - 详见 [LICENSE](LICENSE)

---

## 💬 反馈与支持

- **Bug 反馈**：[提交 Issue](https://github.com/ruyunai/SpecMind-Desktop/issues/new)
- **使用问题**：先查阅 [docs/deploy.md#常见问题排查](docs/deploy.md)
- **查看日志**：`%APPDATA%\SpecMindDesktop\logs\specmind.log`

---

<div align="center">

**⬇️ 立即下载：[SpecMindDesktop.exe](https://github.com/ruyunai/SpecMind-Desktop/releases/latest/download/SpecMindDesktop.exe)**

</div>
