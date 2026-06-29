# pilotstd/core/config/manager.py
# ConfigManager 核心类 — 从 config.py 拆分

import json
import os
import threading
from datetime import datetime
from typing import Any

from .defaults import FACTORY_DEFAULTS
from .migrate import _migrate_ui_keys


class ConfigManager:
    """配置管理器，提供 get/set/reset 接口，数据存于本地 JSON 文件。"""

    def __init__(self, filepath: str | None = None):
        if filepath is None:
            from .paths import _get_config_dir

            filepath = os.path.join(_get_config_dir(), "config.json")
        self._filepath = os.path.abspath(filepath)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

        if os.environ.get("STANDARD_ROOT"):
            self.set("storage.root_dir", os.environ["STANDARD_ROOT"])
        for key, env_var in [
            ("ocr.baidu_api_key", "OCR_BAIDU_API_KEY"),
            ("ocr.baidu_secret_key", "OCR_BAIDU_SECRET_KEY"),
            ("ocr.tencent_secret_id", "OCR_TENCENT_SECRET_ID"),
            ("ocr.tencent_secret_key", "OCR_TENCENT_SECRET_KEY"),
            ("ocr.aliyun_access_key_id", "OCR_ALIYUN_ACCESS_KEY_ID"),
            ("ocr.aliyun_access_key_secret", "OCR_ALIYUN_ACCESS_KEY_SECRET"),
        ]:
            if os.environ.get(env_var):
                self.set(key, os.environ[env_var])

    # ── 公共 API ────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            node = self._data
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            parts = key.split(".")
            node = self._data
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

    def save(self) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            tmp_path = self._filepath + ".tmp"
            from .crypto import _get_fernet, _walk_sensitive

            f = _get_fernet(os.path.dirname(self._filepath))
            data_on_disk = _walk_sensitive(self._data, encrypt=True, fernet=f)
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data_on_disk, fh, ensure_ascii=False, indent=2)
            if os.name != "nt":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._filepath)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
                return
            parts = key.split(".")
            node = self._data
            for part in parts[:-1]:
                if part not in node:
                    return
                node = node[part]
            node.pop(parts[-1], None)

    def populate_defaults(self, defaults: dict[str, Any]) -> None:
        for k, v in defaults.items():
            if self.get(k) is None:
                self.set(k, v)

    def export_rules(self, file_path: str) -> bool:
        from .migrate import export_rules as _export

        return _export(self, file_path)

    def import_rules(self, file_path: str) -> int:
        from .migrate import import_rules as _import

        return _import(self, file_path)

    # ── 内部 ────────────────────────

    def _load(self) -> None:
        cfg_dir = os.path.dirname(self._filepath)
        if os.path.isdir(cfg_dir):
            for name in os.listdir(cfg_dir):
                if name.endswith(".tmp"):
                    try:
                        os.remove(os.path.join(cfg_dir, name))
                    except OSError:
                        pass
        try:
            if os.path.exists(self._filepath):
                with open(self._filepath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                from .crypto import _get_fernet, _walk_sensitive

                f_obj = _get_fernet(os.path.dirname(self._filepath))
                self._data = _walk_sensitive(raw, encrypt=False, fernet=f_obj)
                self.populate_defaults(FACTORY_DEFAULTS)
                _migrate_ui_keys(self)
                self.save()
                return
        except (json.JSONDecodeError, OSError):
            backup = self._filepath + ".corrupted." + datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                os.rename(self._filepath, backup)
            except OSError:
                pass
        self._data = {}
        self._populate_first_run()

    def _populate_first_run(self) -> None:
        for k, v in FACTORY_DEFAULTS.items():
            self.set(k, v)
        self.save()
