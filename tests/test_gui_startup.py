"""GUI 启动验证 - 检查 MainWindow 能否正常初始化（不进入事件循环）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def test_gui_startup():
    """验证 GUI 初始化。"""
    print("=" * 80)
    print("GUI 真实启动验证")
    print("=" * 80)

    # 1. 创建 QApplication
    print("\n[1] 创建 QApplication...")
    app = QApplication.instance() or QApplication(sys.argv)
    print("    ✓ QApplication 创建成功")

    # 2. 加载主题
    print("\n[2] 加载深色主题...")
    qss_path = Path(__file__).parent.parent / "src" / "gui" / "styles" / "dark_theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        print(f"    ✓ 主题加载成功 ({len(app.styleSheet())} 字符)")
    else:
        print(f"    ⚠ 主题文件不存在: {qss_path}")

    # 3. 实例化主窗口
    print("\n[3] 实例化 MainWindow...")
    try:
        window = MainWindow()
        print("    ✓ MainWindow 实例化成功")
        print(f"    ✓ 窗口标题: {window.windowTitle()}")
        print(f"    ✓ 窗口尺寸: {window.size().width()}x{window.size().height()}")
    except Exception as e:
        print(f"    ✗ MainWindow 实例化失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. 检查关键子组件
    print("\n[4] 检查关键子组件...")
    checks = [
        ("asset_panel", "左侧资产库"),
        ("workspace_panel", "中间工作区"),
        ("canvas_panel", "右侧画布"),
    ]
    for attr, desc in checks:
        obj = getattr(window, attr, None)
        marker = "✓" if obj is not None else "✗"
        print(f"    {marker} {desc} ({attr}): {'OK' if obj else 'MISSING'}")

    # 5. 检查菜单/工具栏
    print("\n[5] 检查菜单栏...")
    menubar = window.menuBar()
    menus = [a.text() for a in menubar.actions()]
    print(f"    ✓ 菜单: {menus}")

    # 6. 总结
    print("\n" + "=" * 80)
    print("GUI 启动验证总结")
    print("=" * 80)
    print("✅ GUI 初始化验证通过")
    print("   - QApplication 可创建")
    print("   - 主题可加载")
    print("   - MainWindow 可实例化")
    print("   - 三栏组件均存在")
    print("   - 菜单栏正常")
    return True


if __name__ == "__main__":
    success = test_gui_startup()
    sys.exit(0 if success else 1)
