# pilotstd/core/config/manager.py
# ConfigManager 核心类 — 从 config.py 拆分

import json
import os
import threading
from datetime import datetime
from typing import Any

from .defaults import FACTORY_DEFAULTS  # 工厂默认值字典，所有未设置键的兜底
from .migrate import _migrate_ui_keys  # 旧版 ui.* → appearance.* 迁移


class ConfigManager:
    """配置管理器，提供 get/set/reset 接口，数据存于本地 JSON 文件。"""

    def __init__(self, filepath: str | None = None):
        """初始化配置管理器：加载 JSON 文件 → 合并环境变量覆盖 → 填充工厂默认值。"""
        if filepath is None:
            from .paths import _get_config_dir

            filepath = os.path.join(_get_config_dir(), "config.json")
        # 转为绝对路径，避免后续工作目录变化导致路径失效
        self._filepath = os.path.abspath(filepath)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

        # 环境变量覆盖：优先级高于文件配置，用于 Docker/CI 场景
        if os.environ.get("STANDARD_ROOT"):
            self.set("storage.root_dir", os.environ["STANDARD_ROOT"])
        # OCR 密钥映射：标准化的环境变量名 → 配置键名，统一走 set 接口
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
        """按点分隔路径读取配置值，不存在时返回 default。"""
        with self._lock:
            node = self._data
            # 逐级深入嵌套字典，支持 "appearance.column_widths" 形式
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node

    def set(self, key: str, value: Any) -> None:
        """按点分隔路径写入配置值，中间节点不存在时自动创建。"""
        with self._lock:
            parts = key.split(".")
            node = self._data
            # 逐级创建中间节点，确保 set("a.b.c", v) 在 a 或 a.b 不存在时也能正常写入
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

    def save(self) -> None:
        """将当前配置原子写入 JSON 文件（先写 .tmp 再 replace，敏感字段加密）。"""
        with self._lock:
            # 确保配置目录存在（首次运行时可能不存在）
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            tmp_path = self._filepath + ".tmp"
            from .crypto import _get_fernet, _walk_sensitive

            f = _get_fernet(os.path.dirname(self._filepath))
            # 磁盘数据需加密敏感字段（密钥、密码等），防止明文泄露
            data_on_disk = _walk_sensitive(self._data, encrypt=True, fernet=f)
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data_on_disk, fh, ensure_ascii=False, indent=2)
            # Unix 下限制权限为仅当前用户可读写
            if os.name != "nt":
                os.chmod(tmp_path, 0o600)
            # 原子替换：先写临时文件再 rename，避免写入中途崩溃导致文件损坏
            os.makedirs(os.path.dirname(self._filepath) or ".", exist_ok=True)
            os.replace(tmp_path, self._filepath)

    def reset(self, key: str | None = None) -> None:
        """重置配置项。key 为 None 时清空全部配置，否则删除指定键。"""
        with self._lock:
            # key=None 为全量重置，用于"恢复出厂设置"场景
            if key is None:
                self._data.clear()
                return
            parts = key.split(".")
            node = self._data
            # 定位到父节点后删除叶子键
            for part in parts[:-1]:
                if part not in node:
                    return
                node = node[part]
            node.pop(parts[-1], None)

    def populate_defaults(self, defaults: dict[str, Any]) -> None:
        """将工厂默认值中尚未设置的键填充到当前配置（不覆盖已有值）。"""
        # 仅在键值为 None 时才填充，保留用户已有的自定义值
        for k, v in defaults.items():
            if self.get(k) is None:
                self.set(k, v)

    def export_rules(self, file_path: str) -> bool:
        """将当前所有站点规则导出到指定 JSON 文件。返回 True/False 表示成功/失败。"""
        # 委托给 migrate 模块的 export_rules 函数，保持单一导出逻辑入口
        from .migrate import export_rules as _export

        return _export(self, file_path)

    def import_rules(self, file_path: str) -> int:
        """从 JSON 文件导入规则并合并到已有配置。返回成功导入数量，-1 表示失败。"""
        # 委托给 migrate 模块的 import_rules 函数，保证导入逻辑唯一
        from .migrate import import_rules as _import

        return _import(self, file_path)

    # ── 内部 ────────────────────────

    def _load(self) -> None:
        """从 JSON 文件加载配置：先清理残留 .tmp → 读取解密 → 填充默认值 → 迁移旧键。"""
        # 清理上次崩溃可能残留的 .tmp 文件，避免占用磁盘
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
                # 解密敏感字段后才是内存中的可用数据
                self._data = _walk_sensitive(raw, encrypt=False, fernet=f_obj)
                # 填充默认值 + 迁移旧键后立即保存，确保后续读取一致性
                self.populate_defaults(FACTORY_DEFAULTS)
                _migrate_ui_keys(self)
                self.save()
                return
        except (json.JSONDecodeError, OSError):
            # JSON 损坏时备份原文件，避免数据彻底丢失
            backup = self._filepath + ".corrupted." + datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                os.rename(self._filepath, backup)
            except OSError:
                pass
        # 文件不存在或解析失败时，用工厂默认值初始化
        self._data = {}
        self._populate_first_run()

    def _populate_first_run(self) -> None:
        """首次运行时用工厂默认值初始化并保存。"""
        # 逐键 set 确保中间节点正确创建
        for k, v in FACTORY_DEFAULTS.items():
            self.set(k, v)
        self.save()
