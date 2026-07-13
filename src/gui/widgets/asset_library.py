"""左栏：企业资产库面板 - 接入 ChromaStore 真实数据。

展示企业标准资产：
- 标准功能清单（STANDARD_FEATURE）
- 法规库（REGULATION）
- 合同模板库（CONTRACT_TEMPLATE）

懒加载：首次展开分类时才从 ChromaDB 拉取数据，避免启动时卡顿。
"""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMenu,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal


# 资产分类定义（顺序 = 展示顺序）
CATEGORY_GROUPS = [
    ("标准功能清单", "standard_feature", "企业标准能力库（CRUD/排课/直播/作业/支付/看板等）"),
    ("法规库", "regulation", "本地法规库（个人信息保护法/数据安全法/未成年人保护法/广告法等）"),
    ("合同模板库", "contract", "标准合同模板（维护条款/性能条款/知识产权条款/定制条款）"),
]


class AssetLibraryPanel(QWidget):
    """左栏企业资产库 - 接入真实 ChromaStore 数据。"""

    # 信号：用户点击资产项（预览用，可后续接入详情面板）
    asset_clicked = Signal(str, str)  # category, doc_id

    def __init__(self) -> None:
        super().__init__()
        self._chroma = None
        self._loaded_categories: set = set()
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化资产树。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("企业资产库")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        # 搜索栏
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索已加载资产...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        search_bar.addWidget(self.search_edit, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部分类", "")
        for cat_name, cat_key, _ in CATEGORY_GROUPS:
            self.filter_combo.addItem(cat_name, cat_key)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        search_bar.addWidget(self.filter_combo)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        search_bar.addWidget(self.refresh_btn)

        self.upload_btn = QPushButton("上传")
        self.upload_btn.clicked.connect(self._on_upload)
        self.upload_btn.setToolTip("上传企业自有文档到知识库（支持 Word/PDF/TXT/JSON）")
        search_bar.addWidget(self.upload_btn)
        layout.addLayout(search_bar)

        hint = QLabel("双击分类展开真实数据，双击资产查看详情")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 占位：3 个资产分类（展开时懒加载真实数据）
        for cat_name, cat_key, desc in CATEGORY_GROUPS:
            cat_item = QTreeWidgetItem([f"{cat_name}\n{desc}"])
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setData(1, Qt.UserRole, cat_key)
            # 加一个占位子节点，让分类显示展开箭头
            placeholder = QTreeWidgetItem(["（点击展开加载真实数据...）"])
            cat_item.addChild(placeholder)
            self.tree.addTopLevelItem(cat_item)

        layout.addWidget(self.tree)

        # 底部统计区
        self.stats_label = QLabel("总资产: 加载中...")
        self.stats_label.setObjectName("statsLabel")
        layout.addWidget(self.stats_label)

    def _ensure_chroma(self):
        """延迟初始化 ChromaStore（避免启动时加载 chromadb 拖慢 GUI）。"""
        if self._chroma is None:
            try:
                from storage.chroma_store import ChromaStore
                self._chroma = ChromaStore()
            except Exception as e:
                return None, f"加载失败: {e}"
        return self._chroma, None

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """分类展开时懒加载真实数据。"""
        if item.data(0, Qt.UserRole) != "category":
            return

        cat_key = item.data(1, Qt.UserRole)
        if cat_key in self._loaded_categories:
            return  # 已加载

        chroma, err = self._ensure_chroma()
        if err:
            # 显示错误
            for i in range(item.childCount()):
                child = item.child(i)
                child.setText(0, f"⚠ {err}")
            return

        # 清空占位子节点
        while item.childCount() > 0:
            item.removeChild(item.child(0))

        # 拉真实数据
        from storage.schema import AssetCategory
        category = AssetCategory(cat_key)
        try:
            assets = chroma.list_assets(category, limit=100)
        except Exception as e:
            err_item = QTreeWidgetItem([f"⚠ 加载失败: {e}"])
            item.addChild(err_item)
            return

        if not assets:
            empty_item = QTreeWidgetItem(["（空 - 请运行 python -m storage.seed_data 加载种子数据）"])
            empty_item.setForeground(0, self._gray_brush())
            item.addChild(empty_item)
        else:
            for asset in assets:
                source = asset.get("source", "未知")
                version = asset.get("version", "")
                # 取文本前 30 字符作为预览
                preview = asset.get("text", "")[:30].replace("\n", " ")
                label = f"[{source}] {preview}..."
                child = QTreeWidgetItem([label])
                child.setData(0, Qt.UserRole, "asset")
                child.setData(1, Qt.UserRole, {
                    "category": cat_key,
                    "source": source,
                    "version": version,
                    "text": asset.get("text", ""),
                })
                child.setToolTip(0, asset.get("text", "")[:200])
                item.addChild(child)

        self._loaded_categories.add(cat_key)
        self._update_stats()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """点击资产项 - 发信号供主窗口或详情面板使用。"""
        if item.data(0, Qt.UserRole) != "asset":
            return
        data = item.data(1, Qt.UserRole) or {}
        self.asset_clicked.emit(data.get("category", ""), data.get("source", ""))

    def _on_upload(self) -> None:
        """打开上传对话框。"""
        from gui.dialogs.upload_dialog import UploadDialog
        dialog = UploadDialog(parent=self)
        if dialog.exec():
            # 上传成功后刷新资产库
            self._loaded_categories.clear()
            self.refresh()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击资产项 - 打开详情对话框。"""
        if item.data(0, Qt.UserRole) != "asset":
            return
        data = item.data(1, Qt.UserRole) or {}
        from gui.dialogs.asset_detail_dialog import AssetDetailDialog
        dialog = AssetDetailDialog(data, parent=self)
        dialog.exec()

    def _on_search_text_changed(self, text: str) -> None:
        """根据搜索词过滤已加载的资产项。"""
        keyword = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_key = cat_item.data(1, Qt.UserRole)
            if cat_key not in self._loaded_categories:
                continue
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.data(0, Qt.UserRole) != "asset":
                    continue
                data = child.data(1, Qt.UserRole) or {}
                asset_text = data.get("text", "").lower()
                source = data.get("source", "").lower()
                match = (keyword in asset_text) or (keyword in source)
                child.setHidden(bool(keyword) and not match)

    def _on_filter_changed(self, index: int) -> None:
        """根据筛选下拉框显示/隐藏分类。"""
        selected_key = self.filter_combo.itemData(index) or ""
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_key = cat_item.data(1, Qt.UserRole)
            if not selected_key:
                cat_item.setHidden(False)
            else:
                cat_item.setHidden(cat_key != selected_key)

    def _update_stats(self) -> None:
        """更新底部统计。"""
        total = sum(
            self.tree.topLevelItem(i).childCount()
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).data(1, Qt.UserRole) in self._loaded_categories
        )
        loaded = len(self._loaded_categories)
        # 统计可见资产数（考虑搜索过滤）
        visible = 0
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            if cat_item.isHidden():
                continue
            for j in range(cat_item.childCount()):
                if not cat_item.child(j).isHidden():
                    visible += 1
        self.stats_label.setText(
            f"已加载 {loaded}/{len(CATEGORY_GROUPS)} 分类, 共 {total} 条资产, 当前显示 {visible} 条"
        )

    @staticmethod
    def _gray_brush():
        """灰色画笔（占位提示样式）。"""
        from PySide6.QtGui import QBrush, QColor
        return QBrush(QColor("#6c7086"))

    def refresh(self) -> None:
        """强制重新加载所有分类（外部调用）。"""
        self._loaded_categories.clear()
        self.search_edit.clear()
        self.filter_combo.setCurrentIndex(0)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            # 清空子节点重新加载
            while item.childCount() > 0:
                item.removeChild(item.child(0))
            placeholder = QTreeWidgetItem(["（点击展开加载真实数据...）"])
            item.addChild(placeholder)
            item.setExpanded(False)
            item.setHidden(False)
        self.stats_label.setText("总资产: 加载中...")
