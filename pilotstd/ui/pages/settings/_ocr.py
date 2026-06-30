# pilotstd/ui/pages/settings/_ocr.py
# OCR 设置 Tab 构建 mixin — 百度云/腾讯云/阿里云 OCR 密钥

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _OcrTab:
    """OCR 服务密钥配置：百度云、腾讯云、阿里云。"""

    def _build_ocr_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("ocr_group"))
        form = QFormLayout(gb)
        self.ocr_api_key = QLineEdit()
        self.ocr_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_api_key.setPlaceholderText("百度云 API Key")
        form.addRow(_("ocr_baidu_api_key"), self.ocr_api_key)
        self.ocr_secret_key = QLineEdit()
        self.ocr_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_secret_key.setPlaceholderText("百度云 Secret Key")
        form.addRow(_("ocr_baidu_secret_key"), self.ocr_secret_key)
        self.ocr_secret_id = QLineEdit()
        self.ocr_secret_id.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_secret_id.setPlaceholderText("腾讯云 Secret ID")
        form.addRow(_("ocr_tencent_secret_id"), self.ocr_secret_id)
        self.ocr_tencent_secret_key = QLineEdit()
        self.ocr_tencent_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_tencent_secret_key.setPlaceholderText("腾讯云 Secret Key")
        form.addRow(_("ocr_tencent_secret_key"), self.ocr_tencent_secret_key)
        self.ocr_access_key_id = QLineEdit()
        self.ocr_access_key_id.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_access_key_id.setPlaceholderText("阿里云 Access Key ID")
        form.addRow(_("ocr_aliyun_access_key_id"), self.ocr_access_key_id)
        self.ocr_access_key_secret = QLineEdit()
        self.ocr_access_key_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_access_key_secret.setPlaceholderText("阿里云 Access Key Secret")
        form.addRow(_("ocr_aliyun_access_key_secret"), self.ocr_access_key_secret)
        note = QLabel(_("ocr_note"))
        note.setWordWrap(True)
        form.addRow(note)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("ocr_group"), w)
