# SpecMind Desktop - 部署文档

## 概述

SpecMind Desktop 是一款 AI 招标助手桌面应用，支持两种部署模式：

| 模式 | 适用场景 | 数据位置 |
|------|---------|---------|
| **单文件 exe** | 任意 Windows 电脑，无需预装 Python | `%APPDATA%/SpecMindDesktop/` |
| **U 盘便携** | 随 U 盘迁移，拔插即用 | U 盘 `data/` 目录 |

---

## 方式一：单文件 exe 部署（推荐）

### 前提条件

- Windows 7/10/11（64 位）
- 无需安装 Python 或任何依赖
- 约 100MB 磁盘空间（exe 本体）
- 首次运行需联网（调用 DeepSeek API）

### 部署步骤

1. **获取 exe**
   ```
   从项目 dist/ 目录复制 SpecMindDesktop.exe 到目标电脑
   文件大小：约 98.5MB
   ```

2. **双击运行**
   ```
   双击 SpecMindDesktop.exe 即可启动
   首次启动自动创建数据目录：
     C:\Users\<用户名>\AppData\Roaming\SpecMindDesktop\
       ├── data\
       │   ├── chroma\       (向量知识库)
       │   ├── specmind.db   (审计日志 + 资产库)
       │   └── logs\         (运行日志)
       └── config\
           ├── app.json      (配置文件)
           ├── secrets.enc   (加密 API Key)
           └── .keyseed      (加密种子)
   ```

3. **配置 API Key**
   ```
   启动后按 Ctrl+, 打开模型配置对话框
   在「全局 API Key」中输入 DeepSeek API Key
   点击「保存」— Key 加密存储
   ```
   或者设置环境变量（临时）：
   ```powershell
   $env:SPECMIND_API_KEY="sk-your-key"
   .\SpecMindDesktop.exe
   ```

4. **验证运行**
   ```
   在需求输入框输入测试需求 → 点击执行
   预期：7 个节点依次执行，约 60-90 秒完成
   ```

### 卸载

```powershell
# 删除 exe
Remove-Item SpecMindDesktop.exe

# 删除数据（可选，会丢失所有历史记录）
Remove-Item -Recurse $env:APPDATA\SpecMindDesktop
```

---

## 方式二：U 盘便携部署

### 适用于

- 在多台电脑间切换使用
- 数据跟随 U 盘
- 无法或不愿在 C 盘写入数据

### 打包步骤

1. **创建便携文件夹**
   ```
   U盘:\SpecMindDesktop\
     ├── SpecMindDesktop.exe    (主程序)
     ├── portable.dat            (空文件，标记为便携模式)
     └── *
   ```

2. **创建 portable.dat 标记文件**
   ```powershell
   # 在 exe 同级目录创建空文件
   New-Item -Path "U盘:\SpecMindDesktop\portable.dat" -ItemType File
   ```

3. **首次运行**
   ```
   双击 U 盘中的 SpecMindDesktop.exe
   自动在 exe 同目录创建：
     U盘:\SpecMindDesktop\
       ├── data\
       │   ├── chroma\      (向量知识库)
       │   ├── specmind.db  (审计日志)
       │   └── logs\        (日志)
       └── config\
           ├── app.json
           ├── secrets.enc
           └── .keyseed
   ```

4. **迁移**
   ```
   拔出 U 盘 → 插入另一台电脑 → 直接双击 exe
   数据自动跟随，无需重新配置
   ```

### 注意事项

- **`.keyseed` 与 API Key 绑定**：`.keyseed` 包含加密密钥种子，如 U 盘丢失，加密的 API Key 无法解密。建议做好 U 盘备份
- **Chromadb 兼容性**：Chromadb 使用 SQLite3 + 向量索引，跨 Windows 版本兼容
- **文件系统**：建议 U 盘格式为 NTFS 或 exFAT（FAT32 单文件最大 4GB，但 exe 98.5MB 在限制内）

---

## 方式三：源码部署（开发）

### 前提条件

- Python 3.12+
- Git

### 部署步骤

```powershell
git clone https://github.com/ruyunai/SpecMind-Desktop.git
cd SpecMind-Desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

---

## 构建 exe（从源码）

```powershell
# 安装 PyInstaller
pip install pyinstaller==6.21.0

# 构建
pyinstaller SpecMindDesktop.spec

# 产出在 dist/SpecMindDesktop.exe
```

---

## 常见问题

### Q: Windows SmartScreen 阻止运行？
A: 点击「更多信息」→「仍要运行」。如需发布给用户，需购买代码签名证书。

### Q: 启动报错"未配置 API Key"？
A: 按 Ctrl+, 打开模型配置，输入 DeepSeek API Key 后保存。

### Q: 便携模式下 API Key 要重新配置？
A: 如果 U 盘从旧机器迁移到新机器，且 `.keyseed` + `secrets.enc` 都在，不需要重新配置。如果丢失这两个文件，需重新输入 API Key。

### Q: 如何更换模型？
A: Ctrl+, → 模型配置 → 选择预设路由（如「全 DeepSeek-R1」），或手动为每个 Agent 选择模型。

### Q: exe 启动慢？
A: 首次启动约 5-10 秒（解压 + Chromadb 初始化），后续启动会更快。

### Q: 支持 macOS/Linux 吗？
A: 当前仅支持 Windows。如需跨平台，可源码运行（`python src/main.py`）。
