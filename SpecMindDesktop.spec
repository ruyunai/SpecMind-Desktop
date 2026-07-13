# -*- mode: python ; coding: utf-8 -*-
"""SpecMind Desktop - PyInstaller 打包配置。

打包命令:
    pyinstaller SpecMindDesktop.spec

输出: dist/SpecMindDesktop.exe（单文件, 无控制台, ~200-400MB）
"""

import sys
from pathlib import Path

# 项目根目录
PROJ_ROOT = Path(SPECPATH)  # SPECPATH 由 PyInstaller 提供 = .spec 所在目录

# ---- 基础配置 ----
a = Analysis(
    # 入口脚本
    [str(PROJ_ROOT / "src" / "main.py")],
    pathex=[str(PROJ_ROOT / "src")],

    # 二进制文件
    binaries=[],

    # 数据文件：QSS 主题
    datas=[
        (str(PROJ_ROOT / "src" / "gui" / "styles" / "dark_theme.qss"),
         "gui/styles"),
    ],

    # 隐性导入（PyInstaller 无法自动探测的模块）
    hiddenimports=[
        # --- PySide6 Qt 插件 ---
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtPrintSupport",

        # --- LangGraph ---
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.state",
        "langgraph.checkpoint",
        "langgraph.checkpoint.sqlite",
        "langgraph.prebuilt",
        "langgraph.constants",
        "langgraph.errors",
        "langgraph.types",

        # --- LangChain ---
        "langchain_openai",
        "langchain_core",
        "langchain_core.messages",

        # --- ChromaDB 内部依赖 ---
        "chromadb",
        "chromadb.db",
        "chromadb.db.impl",
        "chromadb.db.impl.sqlite",
        "chromadb.segment",
        "chromadb.segment.impl",
        "chromadb.segment.impl.vector",
        "chromadb.segment.impl.vector.local_hnsw",
        "chromadb.segment.impl.metadata",
        "chromadb.telemetry",
        "chromadb.telemetry.product",
        "chromadb.utils",
        "chromadb.utils.embedding_functions",
        "chromadb.api",
        "chromadb.api.models",
        "chromadb.config",
        "chromadb.auth",
        "chromadb.ingest",

        # --- ChromaDB 底层依赖 ---
        "onnxruntime",
        "hnswlib",
        "tokenizers",
        "tiktoken",
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        "pydantic",
        "pydantic.deprecated",
        "pydantic.deprecated.decorator",
        "yaml",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # starlette/fastapi/multipart —— chromadb 1.5.x 不依赖这些，无需 bundle

        # --- 加密 ---
        "cryptography",
        "cryptography.fernet",

        # --- 文件解析 ---
        "docx",
        "docx.opc",
        "docx.opc.constants",
        "PyPDF2",

        # --- 项目内部模块 ---
        "core",
        "core.config",
        "core.logger",
        "core.crypto",
        "core.orchestrator",
        "core.exporter",
        "graph",
        "graph.builder",
        "agents",
        "agents.state",
        "agents.mock_agents",
        "agents.rag_agents",
        "agents.prompts",
        "agents.confidence",
        "agents.query_rewriter",
        "storage",
        "storage.schema",
        "storage.chroma_store",
        "storage.sqlite_store",
        "storage.retriever",
        "parsers",
        "parsers.doc_parser",
        "parsers.chunker",
        "gui",
        "gui.main_window",
        "gui.widgets",
        "gui.widgets.asset_library",
        "gui.widgets.workspace",
        "gui.widgets.workflow_canvas",
        "gui.dialogs",
        "gui.dialogs.model_config_dialog",
        "gui.dialogs.asset_detail_dialog",

        # --- 标准库（有时会被遗漏）---
        "sqlite3",
        "hashlib",
        "json",
        "uuid",
        "datetime",
        "pathlib",
        "logging",
        "threading",
        "queue",
        "typing",
        "typing_extensions",
    ],

    # 钩子目录（自定义钩子放这里）
    hookspath=[],

    # 递归深度
    hooksconfig={},

    # 运行时钩子
    runtime_hooks=[],

    # 排除的模块（减少体积）
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy.testing",
        "scipy",
        "pandas",
        "PIL",
        "cv2",
        "test",
        "tests",
        "unittest",
        "pytest",
        "setuptools",
        "pip",
        "distutils",
    ],

    # 不加密（简化调试）
    noarchive=False,

    # 优化级别
    optimize=0,
)

# ---- 交叉引用检查 ----
a.datas += Tree(
    str(PROJ_ROOT / "src" / "gui" / "styles"),
    prefix="gui/styles",
)

# ---- PYZ（Python 字节码压缩包）----
pyz = PYZ(a.pure)

# ---- EXE（单文件）----
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpecMindDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,    # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

    # 图标（如果有的话）
    # icon=str(PROJ_ROOT / "assets" / "app.ico"),
)
