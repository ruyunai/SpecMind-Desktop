# SpecMind Desktop 部署操作手册

> 本手册涵盖 Windows 本地部署（exe / 源码）与 U 盘便携迁移的完整操作步骤。
> 适用版本：v0.1.0+（PyInstaller 98.5MB 单文件）
> 适用操作系统：Windows 10 / 11（64 位），Windows 7 需 SP1

---

## 目录

- [1. 部署模式选择](#1-部署模式选择)
- [2. 前置条件](#2-前置条件)
- [3. 模式 A：Windows 本地部署（exe）](#3-模式-awindows-本地部署exe)
- [4. 模式 B：U 盘便携部署](#4-模式-bu-盘便携部署)
- [5. 模式 C：源码部署（开发者）](#5-模式-c源码部署开发者)
- [6. 首次启动配置](#6-首次启动配置)
- [7. 知识库初始化](#7-知识库初始化)
- [8. 部署验证](#8-部署验证)
- [9. U 盘迁移完整流程](#9-u-盘迁移完整流程)
- [10. 数据备份与恢复](#10-数据备份与恢复)
- [11. 升级与卸载](#11-升级与卸载)
- [12. 常见问题排查](#12-常见问题排查)
- [附录 A：数据目录结构](#附录-a数据目录结构)
- [附录 B：命令速查表](#附录-b命令速查表)

---

## 1. 部署模式选择

| 模式 | 适用场景 | 数据位置 | 优势 | 限制 |
|------|---------|---------|------|------|
| **A. exe 本地部署** | 单台电脑长期使用 | `%APPDATA%\SpecMindDesktop\` | 双击即用，无需 Python | 跨电脑需重新配置 |
| **B. U 盘便携部署** | 多电脑切换、外勤演示 | U 盘内 `data/` 目录 | 拔插即用，数据跟随 | U 盘丢失=数据丢失 |
| **C. 源码部署** | 开发调试、二次开发 | 项目根目录 `data/` | 完整可控，可改代码 | 需 Python 环境 |

**决策建议**：
- 内勤团队固定工位 → **模式 A**
- 销售/售前外出演示 → **模式 B**（推荐配合模式 A 在公司电脑做主备份）
- 二次开发或贡献代码 → **模式 C**

---

## 2. 前置条件

### 2.1 硬件要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| CPU | 双核 x64 | 四核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 500 MB（exe + 数据） | 2 GB（含知识库） |
| 网络 | 首次配置需联网 | 持续联网（调用 LLM API） |

### 2.2 软件要求

- **操作系统**：Windows 10 64 位 / Windows 11 / Windows 7 SP1
- **运行库**：Visual C++ Redistributable 2015-2022（多数 Win10/11 已预装；如启动报错缺 `VCRUNTIME140.dll`，从 [微软官网](https://aka.ms/vs/17/release/vc_redist.x64.exe) 下载安装）
- **API Key**：[DeepSeek API Key](https://platform.deepseek.com/)（必需，用于 7 个 Agent 调用 LLM）

### 2.3 获取 DeepSeek API Key

1. 访问 https://platform.deepseek.com/
2. 注册账号 → 充值（建议首充 ¥10 用于测试）
3. 「API Keys」→「Create API Key」→ 复制 `sk-xxxxxxxxxxxxxxxx` 格式的 Key
4. 妥善保管 Key，**不要写入代码或提交到 Git**

---

## 3. 模式 A：Windows 本地部署（exe）

### 3.1 获取 exe

**方式一：从源码构建（推荐用于内部分发）**

```powershell
# 1. 在开发机克隆项目
git clone https://github.com/ruyunai/SpecMind-Desktop.git
cd SpecMind-Desktop

# 2. 安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller==6.21.0

# 3. 构建
pyinstaller --noconfirm SpecMindDesktop.spec

# 4. 验证产物
dir dist\SpecMindDesktop.exe
# 期望：约 98.5 MB
```

**方式二：直接拷贝已构建的 exe**

从已构建的 `dist/` 目录复制 `SpecMindDesktop.exe` 到目标电脑任意目录（如 `C:\SpecMind\` 或 `D:\Tools\`）。

### 3.2 首次启动

```powershell
# 双击 SpecMindDesktop.exe，或在 PowerShell 中启动：
.\SpecMindDesktop.exe
```

**首次启动行为**：
- Windows SmartScreen 可能弹出「Windows 已保护你的电脑」→ 点击「更多信息」→「仍要运行」（exe 未代码签名）
- 首次启动耗时 5-10 秒（解压 + ChromaDB 初始化）
- 自动创建数据目录：`C:\Users\<用户名>\AppData\Roaming\SpecMindDesktop\`
- 状态栏显示「⚠ 知识库为空！请上传企业文档」（正常现象）

### 3.3 配置 API Key

1. 应用启动后，按 `Ctrl + ,` 打开模型配置对话框
2. 在「全局 API Key」输入框粘贴 DeepSeek API Key（`sk-...`）
3. 「Base URL」保持默认 `https://api.deepseek.com/v1`
4. 「模型」保持默认 `deepseek-chat`（或按需改为 `deepseek-reasoner`）
5. 点击「保存」→ Key 通过 Fernet + PBKDF2 + 机器绑定加密存储到 `config\secrets.enc`
6. 关闭对话框，状态栏应显示「就绪」

**环境变量方式（临时，不加密）**：
```powershell
$env:SPECMIND_API_KEY="sk-your-key-here"
.\SpecMindDesktop.exe
```

### 3.4 验证安装

按 [第 8 节：部署验证](#8-部署验证) 执行完整验证流程。

---

## 4. 模式 B：U 盘便携部署

### 4.1 准备 U 盘

| 项目 | 要求 |
|------|------|
| 容量 | ≥ 1 GB |
| 文件系统 | **NTFS** 或 **exFAT**（FAT32 单文件 4GB 限制对 98.5MB exe 无影响，但日志可能超限，不推荐） |
| 接口 | USB 3.0+（提升 ChromaDB 读写速度） |

**格式化 U 盘为 NTFS**（如当前是 FAT32）：
```powershell
# 在 PowerShell 中（替换 X 为 U 盘盘符）
# 警告：会清除 U 盘所有数据！
format X: /FS:NTFS /Q
```

### 4.2 创建便携目录结构

```powershell
# 假设 U 盘盘符为 E:
mkdir E:\SpecMindDesktop
copy dist\SpecMindDesktop.exe E:\SpecMindDesktop\

# 创建便携模式标记文件（空文件即可）
New-Item -Path E:\SpecMindDesktop\portable.dat -ItemType File
```

最终目录结构：
```
E:\SpecMindDesktop\
  ├── SpecMindDesktop.exe    (98.5 MB, 主程序)
  └── portable.dat            (0 KB, 便携模式标记)
```

> **关键**：`portable.dat` 文件的存在会让程序自动进入便携模式，所有数据写入 exe 同级目录而非 `%APPDATA%`。

### 4.3 首次启动便携版

```powershell
# 在任意电脑上，插入 U 盘后
E:\SpecMindDesktop\SpecMindDesktop.exe
```

**首次启动行为**：
- 检测到 `E:\SpecMindDesktop\portable.dat` → 进入便携模式
- 自动创建数据目录于 exe 同级：
  ```
  E:\SpecMindDesktop\
    ├── SpecMindDesktop.exe
    ├── portable.dat
    ├── data\
    │   ├── chroma\          (向量知识库)
    │   ├── specmind.db      (审计 + 资产 FTS)
    │   └── checkpoints.db   (LangGraph 状态)
    ├── config\
    │   ├── app.json
    │   ├── secrets.enc      (加密 API Key)
    │   └── .keyseed         (加密种子)
    └── logs\
        └── specmind.log
  ```
- 后续所有数据写入 U 盘，**不污染宿主电脑**

### 4.4 配置 API Key（便携版）

便携版的 API Key 配置与本地版相同（`Ctrl + ,` → 输入 → 保存），但 Key 加密后存储在 U 盘的 `config\secrets.enc`，**与 U 盘绑定**。

> **重要**：便携版的加密种子 `.keyseed` 也存于 U 盘。U 盘丢失 = API Key 无法解密。建议：
> 1. U 盘做物理备份（双 U 盘冗余）
> 2. API Key 在 DeepSeek 平台设置使用额度上限（防丢失后滥用）
> 3. 不要在 U 盘存放除 SpecMind 外的其他敏感数据

---

## 5. 模式 C：源码部署（开发者）

### 5.1 环境准备

```powershell
# 1. 安装 Python 3.12+（推荐 3.14）
python --version  # 验证

# 2. 安装 Git
git --version

# 3. 克隆项目
git clone https://github.com/ruyunai/SpecMind-Desktop.git
cd SpecMind-Desktop
```

### 5.2 安装依赖

```powershell
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装全部依赖（含 GUI、LangGraph、ChromaDB、PyInstaller 等）
pip install -r requirements.txt

# 验证关键依赖
python -c "import PySide6; print('PySide6:', PySide6.__version__)"
python -c "import langgraph; print('langgraph:', langgraph.__version__)"
python -c "import chromadb; print('chromadb:', chromadb.__version__)"
```

### 5.3 启动应用

```powershell
# 开发模式启动（带控制台日志，便于调试）
python src/main.py
```

### 5.4 运行测试

```powershell
# 全套测试
pytest tests/ -v

# 核心功能稳定性测试（推荐部署后验证用）
python tests/test_stability_core.py

# 生产就绪验证（含 LLM 重试、空 KB 检测）
python tests/test_production_readiness.py
```

---

## 6. 首次启动配置

无论选择哪种部署模式，首次启动后都需要完成以下配置：

### 6.1 配置 API Key

详见 [3.3 节](#33-配置-api-key)。

### 6.2 配置模型路由（可选）

按 `Ctrl + ,` 打开模型配置，可逐 Agent 自定义：

| Agent | 默认模型 | 建议场景 |
|-------|---------|---------|
| SAR | deepseek-chat | 需求清洗，轻量任务 |
| Legal | deepseek-chat | 合规预检 |
| PM | deepseek-chat | PRD 生成（如需更强推理用 `deepseek-reasoner`） |
| Commercial | （不调 LLM） | 公式驱动 |
| Contract | deepseek-chat | 合同比对 |
| Review | deepseek-chat | 三维评审 |
| Planner | deepseek-chat | 交付计划 |

### 6.3 配置成本参数（可选）

`Ctrl + ,` → 「成本参数」Tab，按企业实际填写：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `person_day_rate` | 人天费率（元） | 1500 |
| `days_per_std_feature` | 标准功能人天/个 | 5 |
| `custom_multiplier` | 定制功能倍率 | 2.0 |
| `margin_rate` | 毛利率 | 0.3 |
| `maintenance_rate` | 维护费率 | 0.15 |

修改后点击「保存」，下次工作流执行时 Commercial Agent 会用新参数计算报价。

---

## 7. 知识库初始化

### 7.1 加载种子数据（快速开始）

```powershell
# 源码模式
python -m storage.seed_data

# exe 模式：跳过此步，直接上传企业文档
```

种子数据包含：
- 法规库：个人信息保护法、数据安全法、未成年人保护法、广告法
- 合同模板：维护条款、性能条款、知识产权条款
- 标准功能：CRUD、排课、直播、作业、支付、看板等

### 7.2 上传企业自有文档

1. 在应用左栏「企业资产库」点击「上传」按钮
2. 选择文档（支持 `.docx` / `.pdf` / `.txt` / `.json`）
3. 选择分类：
   - **法规库 (regulation)**：按法条分块
   - **合同模板 (contract)**：按条款分块
   - **历史 PRD (prd)**：按 8 模块分块
   - **标准功能 (feature)**：通用分块
   - **其他通用 (generic)**：通用分块
4. 点击「上传到知识库」→ 后台异步执行（UI 不冻结）
5. 上传完成后弹出结果：「新增 N 条，跳过 M 条（重复）」

> **去重机制**：相同内容（hash 相同）即使 source 名不同也会跳过，避免重复向量化。如需重新入库，先在资产库右键删除旧文档。

### 7.3 验证知识库

左栏展开三个分类节点，应能看到上传的文档：
- 标准功能清单
- 法规库
- 合同模板库

每个文档项右键可：
- **查看详情**：显示完整内容与元数据
- **删除**：从 ChromaDB 物理移除

---

## 8. 部署验证

### 8.1 启动验证

| 检查项 | 期望结果 |
|--------|---------|
| 双击 exe 启动 | 5-10 秒内显示三栏主窗口 |
| 状态栏 | 显示「就绪」或知识库提示 |
| 左栏资产库 | 三个分类可展开（可能为空） |
| 中栏工作区 | 需求输入框可输入 |
| 右栏画布 | 7 节点拓扑图可见 |

### 8.2 API 连通性验证

1. 在中栏需求输入框输入测试需求：
   ```
   客户：测试客户
   需求：在线教育平台，含课程管理和支付。
   ```
2. 点击「开始执行」（或按 `Ctrl+Enter`）
3. 观察：
   - 右栏 7 个节点依次变绿（约 60-90 秒）
   - 状态栏进度更新
   - 中栏 PRD 区域生成完整内容
4. 若节点变红或日志报错 `401 Unauthorized` → API Key 错误，重新配置
5. 若报错 `timeout` → 网络问题或 DeepSeek 服务降级，等几分钟后重试（已含 3 次指数退避重试）

### 8.3 自动化稳定性测试（源码模式）

```powershell
# 运行核心功能稳定性测试
python tests/test_stability_core.py
```

期望输出：
```
============================================================
✅ 全部 54 项检查通过
   上传管线: 通过
   删除管线: 通过
   分类管理: 通过
   线程终止: 通过
   BUG 回归: 通过
============================================================
```

### 8.4 生产就绪验证

```powershell
python tests/test_production_readiness.py
```

覆盖：LLM 重试机制、空 KB 检测、端到端工作流（含真实 LLM 调用）。

---

## 9. U 盘迁移完整流程

### 9.1 场景一：从公司电脑迁移到 U 盘

**前提**：已在公司电脑（模式 A）完成配置并上传了知识库文档。

```powershell
# 1. 在 U 盘创建便携目录
mkdir E:\SpecMindDesktop
New-Item -Path E:\SpecMindDesktop\portable.dat -ItemType File

# 2. 复制 exe
copy C:\SpecMind\SpecMindDesktop.exe E:\SpecMindDesktop\

# 3. 复制已配置的数据目录（含 API Key、知识库、日志）
#    注意：路径中的 <用户名> 替换为实际用户名
xcopy "%APPDATA%\SpecMindDesktop" E:\SpecMindDesktop\ /E /I

# 4. 验证 U 盘目录结构
dir E:\SpecMindDesktop\
# 期望：
#   SpecMindDesktop.exe
#   portable.dat
#   data\
#   config\
#   logs\
```

**首次在 U 盘启动验证**：
```powershell
E:\SpecMindDesktop\SpecMindDesktop.exe
```
- 应直接进入应用，无需重新配置 API Key
- 左栏资产库应显示已上传的文档
- 中栏输入需求可正常执行工作流

### 9.2 场景二：U 盘迁移到另一台电脑

**前提**：U 盘已按 9.1 完成便携化部署。

1. 将 U 盘插入目标电脑（如客户现场电脑）
2. 直接双击 `E:\SpecMindDesktop\SpecMindDesktop.exe`
3. 应用启动后：
   - 自动检测 `portable.dat` → 便携模式
   - 从 U 盘读取加密的 API Key（`.keyseed` + `secrets.enc` 配对解密）
   - 从 U 盘加载 ChromaDB 知识库
   - **不向宿主电脑 C 盘写入任何数据**
4. 使用完毕，直接拔出 U 盘（建议先关闭应用）

> **关键**：便携模式下，宿主电脑只需满足「Windows 10+ 64 位」即可，无需预装 Python、无需管理员权限、不写入注册表。

### 9.3 场景三：U 盘数据同步回公司电脑

```powershell
# 1. 在公司电脑关闭 SpecMind 应用

# 2. 从 U 盘反向同步数据（覆盖本地）
xcopy E:\SpecMindDesktop\data "%APPDATA%\SpecMindDesktop\data" /E /Y
xcopy E:\SpecMindDesktop\config "%APPDATA%\SpecMindDesktop\config" /E /Y
# 注意：不要覆盖 logs，保留本地日志历史

# 3. 启动公司电脑的 SpecMind，验证数据已同步
```

### 9.4 U 盘迁移注意事项

| 注意点 | 说明 |
|--------|------|
| **加密种子绑定** | `.keyseed` + `secrets.enc` 必须一起迁移，否则 API Key 无法解密 |
| **盘符变化** | U 盘在不同电脑可能盘符不同（E: / F: / G:），程序使用相对路径，不受影响 |
| **ChromaDB 锁文件** | 异常拔出可能导致 `chroma/` 下遗留 `.lock` 文件，下次启动会自动清理 |
| **跨版本兼容** | 升级 exe 后，旧版数据目录结构如有变化需执行迁移脚本（见 [11.2](#12-升级)） |
| **杀软误报** | 部分杀毒软件可能误报 PyInstaller exe，需加白名单 |

---

## 10. 数据备份与恢复

### 10.1 关键数据清单

| 路径 | 内容 | 优先级 |
|------|------|--------|
| `config\secrets.enc` | 加密的 API Key | 高（丢失需重新配置） |
| `config\.keyseed` | 加密种子 | 高（丢失则 secrets.enc 无法解密） |
| `data\chroma\` | 向量知识库 | 高（重建耗时） |
| `data\specmind.db` | 审计日志 + 资产 FTS 索引 | 中 |
| `data\checkpoints.db` | LangGraph 运行状态 | 低（仅用于回溯） |
| `logs\` | 应用日志 | 低（用于排障） |

### 10.2 备份方法

**方法一：手动复制**
```powershell
# 关闭 SpecMind 应用后
# 本地模式
xcopy "%APPDATA%\SpecMindDesktop" D:\Backup\SpecMind_20260714\ /E /I

# 便携模式
xcopy E:\SpecMindDesktop D:\Backup\SpecMind_20260714\ /E /I
```

**方法二：压缩归档**
```powershell
Compress-Archive -Path "%APPDATA%\SpecMindDesktop\*" -DestinationPath D:\Backup\SpecMind_20260714.zip
```

### 10.3 恢复方法

```powershell
# 1. 关闭 SpecMind
# 2. 恢复数据
xcopy D:\Backup\SpecMind_20260714\* "%APPDATA%\SpecMindDesktop\" /E /Y
# 3. 启动 SpecMind，验证数据完整
```

### 10.4 推荐备份策略

| 部署模式 | 备份频率 | 备份位置 |
|---------|---------|---------|
| 本地模式 | 每周 / 每次上传新文档后 | 网络盘 / 移动硬盘 |
| 便携模式 | 每次变更后 | 第二个 U 盘 / 公司电脑 |
| 源码模式 | Git 提交 + 数据目录定期归档 | Git 远程 + 本地归档 |

---

## 11. 升级与卸载

### 11.1 升级

**exe 模式**：
1. 关闭 SpecMind
2. 备份 `data/` 和 `config/` 目录（见 [10.2](#102-备份方法)）
3. 替换 `SpecMindDesktop.exe` 为新版本
4. 启动新版本，验证数据正常加载

**便携模式**：
1. 关闭应用
2. 仅替换 `SpecMindDesktop.exe`，保留 `portable.dat` / `data/` / `config/`
3. 启动验证

**源码模式**：
```powershell
git pull origin master
pip install -r requirements.txt --upgrade
python tests/test_stability_core.py  # 升级后回归测试
```

### 11.2 卸载

**exe 模式**：
```powershell
# 1. 关闭 SpecMind
# 2. 删除 exe
Remove-Item C:\SpecMind\SpecMindDesktop.exe

# 3. 删除数据目录（可选，会丢失所有历史记录和知识库）
Remove-Item -Recurse $env:APPDATA\SpecMindDesktop
```

**便携模式**：
直接格式化 U 盘或删除 `SpecMindDesktop\` 目录即可，宿主电脑无残留。

**源码模式**：
```powershell
Remove-Item -Recurse .venv
Remove-Item -Recurse data
Remove-Item -Recurse logs
# 项目目录可保留或整体删除
```

---

## 12. 常见问题排查

### 12.1 启动问题

| 现象 | 排查 | 解决 |
|------|------|------|
| 双击 exe 无反应 | 任务管理器查进程 | 可能被杀软拦截，加白名单后重试 |
| 启动报错「缺 VCRUNTIME140.dll」 | 缺 VC++ 运行库 | 安装 [VC++ Redistributable 2015-2022](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| SmartScreen 拦截 | exe 未签名 | 「更多信息」→「仍要运行」 |
| 启动后白屏 | 显卡驱动兼容性 | 右键 exe → 属性 → 兼容性 → 勾选「禁用全屏优化」 |
| 启动慢（>30 秒） | 杀软实时扫描 | 将 exe 加入杀软白名单 |

### 12.2 API 调用问题

| 现象 | 排查 | 解决 |
|------|------|------|
| `401 Unauthorized` | API Key 错误 | `Ctrl + ,` 重新输入 Key |
| `429 Rate Limit` | 并发过多 / 额度用尽 | 等待 60 秒重试；DeepSeek 平台查看额度 |
| `timeout` | 网络问题 | 已含 3 次重试，仍失败则检查网络代理 |
| `model not found` | 模型名错误 | `Ctrl + ,` 改为 `deepseek-chat` |
| 节点变红 | 查看 `logs\specmind.log` | 大部分为 LLM 调用失败，Agent 会自动回退到 mock |

### 12.3 知识库问题

| 现象 | 排查 | 解决 |
|------|------|------|
| 上传后 RAG 召回为空 | 检查分类是否选对 | 法规文档必须选「法规库」，不能选「通用」 |
| 上传大文档 UI 卡顿 | 检查是否为旧版本 | 升级到 BUG-022 修复后的版本（QThread 异步上传） |
| 重复上传不跳过 | hash 计算异常 | 检查文档内容是否真的相同（空白字符也会影响 hash） |
| 右键删除失败 | 权限问题 | 关闭其他 SpecMind 实例（ChromaDB 锁） |
| 法规库展开报错 | BUG-021 残留 | 升级到最新版本 |

### 12.4 便携模式问题

| 现象 | 排查 | 解决 |
|------|------|------|
| 便携版启动后仍写入 C 盘 | `portable.dat` 不存在 | 在 exe 同级创建空文件 `portable.dat` |
| U 盘换电脑后 API Key 失效 | `.keyseed` 丢失 | 确保 `config\.keyseed` 和 `config\secrets.enc` 一起迁移 |
| U 盘插入后盘符变化 | Windows 自动分配 | 不影响使用（程序使用相对路径） |
| ChromaDB 启动报「lock」 | 上次异常退出 | 删除 `data\chroma\*.lock` 文件后重启 |

### 12.5 线程终止问题

| 现象 | 排查 | 解决 |
|------|------|------|
| 关闭窗口后进程不退出 | QThread 未终止 | 升级到 BUG-020 修复后的版本（三层终止策略） |
| 任务管理器残留 SpecMind 进程 | 强制终止失败 | 任务管理器 → 结束任务 |
| 上传中关闭对话框卡死 | 旧版 QThread 未清理 | 升级到 BUG-022 修复后的版本 |

### 12.6 日志查看

**日志位置**：
- 本地模式：`%APPDATA%\SpecMindDesktop\logs\specmind.log`
- 便携模式：`<exe同级>\logs\specmind.log`
- 源码模式：`<项目根>\logs\specmind.log`

**快速查看最近日志**：
```powershell
# PowerShell 查看最后 50 行
Get-Content "$env:APPDATA\SpecMindDesktop\logs\specmind.log" -Tail 50

# 过滤 ERROR
Select-String -Path "$env:APPDATA\SpecMindDesktop\logs\specmind.log" -Pattern "ERROR"
```

**日志轮转**：5 MB × 3 个文件（`specmind.log` / `specmind.log.1` / `specmind.log.2`），自动覆盖最旧的。

---

## 附录 A：数据目录结构

```
SpecMindDesktop/                    # 应用根目录
├── SpecMindDesktop.exe             # 主程序（98.5 MB）
├── portable.dat                    # 便携模式标记（仅便携模式有）
│
├── data/                           # 数据目录
│   ├── chroma/                     # ChromaDB 向量库
│   │   ├── chroma.sqlite3          # 主数据库
│   │   └── *.lock                  # 运行时锁文件
│   ├── specmind.db                 # SQLite（审计 + FTS5 BM25）
│   └── checkpoints.db              # LangGraph 状态快照
│
├── config/                         # 配置目录
│   ├── app.json                    # 应用配置（base_url/data_dir/模型路由）
│   ├── secrets.enc                 # 加密的 API Key（Fernet）
│   └── .keyseed                    # 加密种子（PBKDF2 + 机器绑定）
│
└── logs/                           # 日志目录
    ├── specmind.log                # 当前日志
    ├── specmind.log.1              # 上一轮（5 MB 滚动）
    ├── specmind.log.2              # 上上轮
    └── specmind.log.3              # 最旧
```

---

## 附录 B：命令速查表

### 部署相关

```powershell
# 构建 exe
pyinstaller --noconfirm SpecMindDesktop.spec

# 启动（exe 模式）
.\SpecMindDesktop.exe

# 启动（源码模式）
python src/main.py

# 加载种子数据（源码模式）
python -m storage.seed_data
```

### 测试相关

```powershell
# 核心功能稳定性测试（54 项检查）
python tests/test_stability_core.py

# 生产就绪验证（18 项）
python tests/test_production_readiness.py

# 全套 pytest
pytest tests/ -v

# 单个测试
pytest tests/test_langgraph_workflow.py -v
```

### 数据管理

```powershell
# 备份（本地模式）
Compress-Archive -Path "$env:APPDATA\SpecMindDesktop\*" -DestinationPath D:\Backup\specmind.zip

# 恢复（本地模式）
Expand-Archive -Path D:\Backup\specmind.zip -DestinationPath "$env:APPDATA\SpecMindDesktop" -Force

# 创建便携 U 盘
mkdir E:\SpecMindDesktop
copy dist\SpecMindDesktop.exe E:\SpecMindDesktop\
New-Item -Path E:\SpecMindDesktop\portable.dat -ItemType File
```

### 日志查看

```powershell
# 最近 50 行
Get-Content "$env:APPDATA\SpecMindDesktop\logs\specmind.log" -Tail 50

# 过滤 ERROR
Select-String "$env:APPDATA\SpecMindDesktop\logs\specmind.log" -Pattern "ERROR"

# 实时跟踪
Get-Content "$env:APPDATA\SpecMindDesktop\logs\specmind.log" -Wait -Tail 10
```

---

## 文档版本

- 版本：v1.0
- 更新日期：2026-07-14
- 适用 SpecMind 版本：v0.1.0+
- 维护者：SpecMind 团队

如遇本手册未覆盖的问题，请：
1. 查看 `logs\specmind.log` 中的 ERROR 行
2. 查阅 `memory-bank\修复日志.md` 中是否已记录类似问题
3. 提交 Issue 到 https://github.com/ruyunai/SpecMind-Desktop/issues
