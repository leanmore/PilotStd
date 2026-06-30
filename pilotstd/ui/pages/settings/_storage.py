# pilotstd/ui/pages/settings/_storage.py
# 存储设置 Tab 构建 mixin — 路径、自动清理、看门狗

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _StorageTab:
    """存储路径、过期文件夹、自动清理、镜像、看门狗、下载目录设置。"""

    def _build_storage_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("storage_group"))
        form = QFormLayout(gb)
        self.root_dir = QLineEdit()
        self.root_dir.setPlaceholderText("默认为当前用户文档目录")
        root_layout = QHBoxLayout()
        root_layout.addWidget(self.root_dir)
        btn_browse = QPushButton(_("btn_browse"))
        btn_browse.clicked.connect(self._browse_root)
        root_layout.addWidget(btn_browse)
        form.addRow(_("storage_root"), root_layout)
        note = QLabel(_("storage_note"))
        note.setStyleSheet("color: #888; font-size: 9pt;")
        form.addRow(note)
        self.expire_name = QLineEdit()
        form.addRow(_("expire_folder"), self.expire_name)
        self.auto_clean_cb = QCheckBox(_("auto_clean_source"))
        form.addRow(self.auto_clean_cb)
        self.clear_readonly_cb = QCheckBox(_("clear_readonly"))
        form.addRow(self.clear_readonly_cb)
        self.mirror_skipped_cb = QCheckBox(_("mirror_skipped_dirs"))
        form.addRow(self.mirror_skipped_cb)
        self.mirror_fallback_cb = QCheckBox(_("mirror_fallback"))
        form.addRow(self.mirror_fallback_cb)
        self.watchdog_cb = QCheckBox(_("watchdog_enabled"))
        form.addRow(self.watchdog_cb)
        self.downloads_dir = QLineEdit()
        dl_layout = QHBoxLayout()
        dl_layout.addWidget(self.downloads_dir)
        btn_dl_browse = QPushButton(_("btn_browse"))
        btn_dl_browse.clicked.connect(self._browse_downloads_dir)
        dl_layout.addWidget(btn_dl_browse)
        form.addRow(_("download_dir_label"), dl_layout)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("storage_group"), w)

    def _browse_root(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_library"))
        if path:
            self.root_dir.setText(path)

    def _browse_downloads_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_temp_dl"))
        if path:
            self.downloads_dir.setText(path)
