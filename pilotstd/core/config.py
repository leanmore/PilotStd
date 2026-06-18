# pilotstd/core/config.py
# 配置管理器：JSON 持久化，点号分隔的键路径，支持默认值及运行期覆盖
#
# 键路径设计：
#   配置键使用点号分隔的层级结构，如 "appearance.theme"、"scan.skip_folders"。
#   get/set 自动处理中间层级的创建和读取。
#
#   存储位置：
#     - 开发模式：项目根目录/data/config.json
#     - 打包模式(exe)：exe所在目录/config/，不可写则回退 %APPDATA%/PilotStd/
#
#   线程安全：
#     所有读写操作通过 threading.Lock 保护，支持多线程并发访问。

import json
import os
import sys
import threading
from typing import Any, Dict, Optional

from .frozen import is_frozen


def _get_config_dir() -> str:
    """返回配置文件目录。

    exe 模式下优先 exe 同级的 config/，不可写则回退到 %APPDATA%。
    开发模式下返回项目 data/ 目录。
    """
    if is_frozen():
        # 打包为 exe 后运行
        exe_dir = os.path.dirname(sys.executable)
        cfg_dir = os.path.join(exe_dir, "config")
        try:
            os.makedirs(cfg_dir, exist_ok=True)
            # 写入测试：确保目录可写
            test = os.path.join(cfg_dir, ".write_test")
            with open(test, "w") as f:
                f.write("")
            os.remove(test)
            return cfg_dir
        except OSError:
            pass
        # 不可写时使用用户 AppData 目录
        appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd")
        os.makedirs(appdata, exist_ok=True)
        return appdata
    else:
        # 开发模式：项目 data/ 目录
        return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def get_data_dir() -> str:
    """返回可写数据目录（数据库、缓存、下载文件等）。

    优先级：exe/data/ → 开发/data/ → %APPDATA%/PilotStd/
    """
    if is_frozen():
        exe_dir = os.path.dirname(sys.executable)
        data_dir = os.path.join(exe_dir, "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
        except OSError:
            appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd")
            os.makedirs(appdata, exist_ok=True)
            return appdata
    return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def get_db_path() -> str:
    """返回 SQLite 数据库完整路径。"""
    return os.path.join(get_data_dir(), "pilotstd.db")


def get_network_timeout(config: "ConfigManager") -> int:
    """返回网络请求超时秒数（从配置读取，默认30）。"""
    return config.get("network.timeout", 30)


def get_library_root(config: "ConfigManager") -> str:
    """返回标准库根目录路径（环境变量 STANDARD_ROOT 优先，其次配置，最后默认值）。
    路径不存在时自动创建，不可写时记录错误。"""
    import logging
    _log = logging.getLogger("pilotstd.config")
    # Docker/容器环境通过 STANDARD_ROOT 注入路径，优先使用
    root = os.environ.get("STANDARD_ROOT") or config.get("storage.root_dir", os.path.expanduser("~/标准"))
    root = os.path.abspath(os.path.normpath(root))
    if not os.path.exists(root):
        try:
            os.makedirs(root, exist_ok=True)
            _log.info("已创建库根目录: %s", root)
        except OSError as e:
            _log.error("无法创建库根目录 %s: %s", root, e)
    elif not os.access(root, os.W_OK):
        _log.error("库根目录不可写: %s", root)
    return root


# ════════════════════════════════════════════════════════════════
# 出厂默认值（模块常量）
# 新增默认 key 会通过 populate_defaults() 自动迁移到已有配置文件
# ════════════════════════════════════════════════════════════════
FACTORY_DEFAULTS = {
    "appearance.theme": "经典白",
    "appearance.language": "zh_CN",
    "appearance.column_visibility": [True] * 9,
    "appearance.icon_theme": "default",
    "appearance.skip_welcome": False,
    "appearance.hyphen_style": True,         # 短横代替一字线
    "storage.root_dir": os.path.expanduser("~/标准"),
    "storage.expire_folder": "过期作废",
    "storage.downloads_dir": None,  # null=回退到 data/downloads
    "storage.mirror_skipped_dirs": True,   # 归档时将扫描跳过的目录镜像到输出
    "storage.mirror_fallback": True,       # 归档收尾：将源目录残留文件镜像到输出
    "organize.auto_clean_source": False,  # 归档目标已存在时自动清理源文件（需SHA-256确认）
    "network.proxy": "",
    "network.ua_rotation": True,
    "network.timeout": 30,                 # HTTP 请求默认超时秒数
    "query.site_order": [],               # 空=使用默认路由
    "query.use_cache": True,
    "scan.skip_folders": ["过期作废", "征求意见稿", "培训课件", "建设项目过程资料及交工资料标准", "吊车性能", "标准图集"],
    "scan.exclude_patterns": ["征求意见稿", "培训课件", "建设项目过程资料及交工资料标准", "吊车性能", "标准图集"],  # 扫描排除关键词
    "scan.extensions": [".pdf", ".doc", ".docx", ".txt"],
    "announcement.enabled": False,           # 公告自动更新（Windows默认关，Docker默认开）
    "ocr.provider": "",                      # 已废弃——多 provider 共存时忽略，各 provider 独立配置
    "ocr.baidu_api_key": "",                 # 百度云 API Key
    "ocr.baidu_secret_key": "",              # 百度云 Secret Key
    "ocr.tencent_secret_id": "",             # 腾讯云 Secret ID
    "ocr.tencent_secret_key": "",            # 腾讯云 Secret Key
    "ocr.aliyun_access_key_id": "",          # 阿里云 Access Key ID
    "ocr.aliyun_access_key_secret": "",      # 阿里云 Access Key Secret
    "file.clear_readonly": True,             # 移动文件前自动清除只读属性
    "watchdog.enabled": False,             # 启动时开启增量文件监控（需安装watchdog包）
}


class ConfigManager:
    """配置管理器，提供 get/set/reset 接口，数据存于本地 JSON 文件。

    特性：
      - 点号分层键（"a.b.c"）
      - 线程安全（threading.Lock）
      - 懒加载 + 自动创建默认值
      - populate_defaults 只填充缺失键，不覆盖已有值
    """

    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            filepath = os.path.join(_get_config_dir(), "config.json")
        self._filepath = os.path.abspath(filepath)
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}
        self._load()
        # Docker/容器环境：STANDARD_ROOT 环境变量覆盖配置文件中的路径
        if os.environ.get("STANDARD_ROOT"):
            self.set("storage.root_dir", os.environ["STANDARD_ROOT"])
        # OCR 密钥可通过环境变量注入（压测子进程等场景）
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

    # ════════════════════════════════════════════════════════════════
    # 公共 API
    # ════════════════════════════════════════════════════════════════

    def get(self, key: str, default: Any = None) -> Any:
        """读取配置项，key 支持点号分层如 'scan.skip_folders'。

        未找到时返回 default（默认 None）。
        """
        with self._lock:
            node = self._data
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node

    def set(self, key: str, value: Any) -> None:
        """设置配置项，自动创建不存在的中间层级字典。"""
        with self._lock:
            parts = key.split(".")
            node = self._data
            # 逐层深入，缺失的中间层自动创建空字典
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

    def save(self) -> None:
        """持久化到 JSON 文件（敏感字段自动加密，原子写入）。"""
        with self._lock:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            tmp_path = self._filepath + ".tmp"
            # 敏感字段加密后再写入磁盘
            data_on_disk = self._walk_sensitive(self._data, encrypt=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data_on_disk, f, ensure_ascii=False, indent=2)
            if os.name != "nt":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._filepath)

    def reset(self, key: Optional[str] = None) -> None:
        """重置配置。

        Args:
            key: 指定键路径则只重置该键，None 则清空全部配置。
        """
        with self._lock:
            if key is None:
                self._data.clear()
                return
            parts = key.split(".")
            node = self._data
            # 逐层查找父节点
            for part in parts[:-1]:
                if part not in node:
                    return
                node = node[part]
            node.pop(parts[-1], None)

    def populate_defaults(self, defaults: dict) -> None:
        """只填充缺失的键，不覆盖已有值。

        典型用法：
          cfg.populate_defaults({"scan.extensions": [".pdf"]})
          # 如果 scan.extensions 已有值则保持不变
          cfg.set("scan.extensions", [".txt"])       # 手动覆盖
          cfg.populate_defaults({"scan.extensions": [".pdf"]})  # 不生效，已有值
        """
        for k, v in defaults.items():
            if self.get(k) is None:
                self.set(k, v)

    # ════════════════════════════════════════════════════════════════
    # 内部
    # ════════════════════════════════════════════════════════════════

    def _migrate_ui_keys(self):
        """将旧版 ui.* 键迁移到 appearance.* 前缀（v0.5.x → v0.6 兼容）。"""
        _map = {
            "ui.column_widths": "appearance.column_widths",
            "ui.window_geometry": "appearance.window_geometry",
            "ui.main_splitter": "appearance.main_splitter",
            "ui.right_splitter": "appearance.right_splitter",
            "ui.sort_column": "appearance.sort_column",
            "ui.sort_order": "appearance.sort_order",
            "ui.last_import_path": "appearance.last_import_path",
        }
        for old, new in _map.items():
            val = self.get(old)
            if val is not None:
                # 新键不存在才迁移，不覆盖已有值
                if self.get(new) is None:
                    self.set(new, val)
                # 删旧键（用内部 _data 直接操作，避免 set 回写旧键）
                node = self._data
                parts = old.split(".")
                for p in parts[:-1]:
                    if isinstance(node, dict) and p in node:
                        node = node[p]
                    else:
                        node = None
                        break
                if node and isinstance(node, dict) and parts[-1] in node:
                    del node[parts[-1]]

    def _load(self) -> None:
        """加载 JSON 配置文件，文件不存在时自动创建并填充默认值。
        文件损坏时自动备份并重建默认配置。启动时清理残留 .tmp 文件。"""
        import logging
        from datetime import datetime
        _log = logging.getLogger("pilotstd.config")
        # 清理上次进程崩溃可能残留的 .tmp 文件
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
                # 敏感字段解密
                self._data = self._walk_sensitive(raw, encrypt=False)
                # 补入新增默认 key，确保已有配置文件不缺失新版本增加的默认值
                self.populate_defaults(FACTORY_DEFAULTS)
                self._migrate_ui_keys()
                self.save()
                return
        except (json.JSONDecodeError, OSError) as e:
            backup = self._filepath + ".corrupted." + datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                os.rename(self._filepath, backup)
                _log.error("配置文件损坏已备份至 %s，重建默认配置", backup)
            except OSError:
                _log.error("配置文件损坏且无法备份: %s", e)
        self._data = {}
        self._populate_first_run()

    def _populate_first_run(self) -> None:
        """初次运行时写入所有出厂默认值。

        遍历模块常量 FACTORY_DEFAULTS，确保用户开箱即用。
        """
        for k, v in FACTORY_DEFAULTS.items():
            self.set(k, v)
        self.save()

    # ── 敏感字段加密 ──

    # 完整键路径（含层级前缀）以此结尾的为敏感字段
    _SENSITIVE_SUFFIXES = (
        ".api_key", ".secret_key", ".secret_id",
        ".access_key_id", ".access_key_secret",
    )

    def _get_fernet(self):
        """懒初始化 Fernet——密钥存于 config 目录，首次自动生成。"""
        if hasattr(self, "_fernet"):
            return self._fernet
        from cryptography.fernet import Fernet
        key_path = os.path.join(os.path.dirname(self._filepath), ".fernet_key")
        try:
            with open(key_path, "rb") as f:
                key = f.read()
        except FileNotFoundError:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "wb") as f:
                f.write(key)
            if os.name != "nt":
                os.chmod(key_path, 0o600)
        self._fernet = Fernet(key)
        return self._fernet

    def _walk_sensitive(self, data: dict, *, encrypt: bool, prefix: str = "") -> dict:
        """递归遍历嵌套字典，对所有敏感字段加密/解密。内存中始终明文。"""
        result: dict[str, Any] = {}
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result[k] = self._walk_sensitive(v, encrypt=encrypt, prefix=full_key)
            elif isinstance(v, str) and v and self._is_sensitive(full_key):
                fernet = self._get_fernet()
                if encrypt:
                    result[k] = fernet.encrypt(v.encode()).decode()
                else:
                    # 兼容旧版明文配置：Fernet 密文以 "gAAAAA" 开头
                    if v.startswith("gAAAAA"):
                        try:
                            result[k] = fernet.decrypt(v.encode()).decode()
                        except Exception:
                            result[k] = ""  # 密钥轮换/数据损坏，清空让用户重配
                    else:
                        result[k] = v  # 明文，保留原值，下次 save 自动加密
            else:
                result[k] = v
        return result

    @classmethod
    def _is_sensitive(cls, full_key: str) -> bool:
        return any(full_key.endswith(s) for s in cls._SENSITIVE_SUFFIXES)
