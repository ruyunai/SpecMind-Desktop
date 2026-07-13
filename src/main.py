"""SpecMind Desktop 应用入口。

启动流程：
1. 创建 QApplication
2. 加载深色主题
3. 实例化三栏主窗口
4. 进入事件循环

PyInstaller 打包兼容：
- 资源文件（QSS）通过 sys._MEIPASS 定位
- 数据目录（chroma/sqlite）使用 %APPDATA%
"""
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from gui.main_window import MainWindow


def _is_frozen() -> bool:
    """是否为 PyInstaller 打包后的 exe 运行。"""
    return getattr(sys, "frozen", False)


def _get_resource_path(relative: str) -> Path:
    """获取资源文件路径（兼容 dev 和 frozen 模式）。"""
    if _is_frozen():
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent / relative


def load_stylesheet(app: QApplication) -> None:
    """加载深色主题 QSS。"""
    qss_path = _get_resource_path("gui/styles/dark_theme.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    """应用主入口。"""
    app = QApplication(sys.argv)
    app.setApplicationName("SpecMind Desktop")
    app.setOrganizationName("SpecMind")
    app.setApplicationVersion("0.1.0")

    load_stylesheet(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
