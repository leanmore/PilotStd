# 模块：项目/核心/配置/管理器脚本
# 核心类—从配置脚本拆分

import copy
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .defaults import FACTORY_DEFAULTS  # 工厂默认值字典，所有未设置键的兜底
from .migrate import _migrate_ui_keys  # 旧版 ui.* → appearance.* 迁移

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，提供 get/set/reset 接口，数据存于本地 JSON 文件。"""

    def __init__(self, filepath: str | None = None):
        """初始化配置管理器：加载 JSON 文件 → 合并环境变量覆盖 → 填充工厂默认值。"""
        # 缺省路径统一由 default_config_path() 推导（与共享实例缓存用同一键，#31-P1）
        self._filepath = default_config_path() if filepath is None else os.path.abspath(filepath)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

        # 环境变量覆盖：优先级高于文件配置，用于/持续集成场景
        if os.environ.get("STANDARD_ROOT"):
            self.set("storage.root_dir", os.environ["STANDARD_ROOT"])
        # 文字识别密钥映射：标准化的环境变量名→配置键名，统一走接口
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

    # ──公共接口────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """按点分隔路径读取配置值，不存在时返回 default。"""
        with self._lock:
            node = self._data
            # 逐级深入嵌套字典，支持"._"形式
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
            # 逐级创建中间节点，确保("..",)在或.不存在时也能正常写入
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

    def save(self, retries: int = 3, delay: float = 0.1) -> None:
        """将当前配置原子写入 JSON 文件（先写 .tmp 再 replace，敏感字段加密）。

        mkdir / open / os.replace 全部纳入重试循环，消除 xdist 并发竞态。

        写盘成功后发布**显式失效通知**（#31-P1 / R14-3b）：他方实例持有同一路径的共享缓存时，
        该缓存被移除（陈旧），并回调已注册的监听者——保证 GUI 设置页写盘后热路径能读到新值。
        通知在释放实例锁之后发出，避免监听者回调时反向取锁。
        """
        target = Path(self._filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(target.suffix + ".tmp")

        from .crypto import _get_fernet, _walk_sensitive

        wrote = False
        with self._lock:
            for attempt in range(retries):
                try:
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    os.makedirs(os.path.dirname(str(target)), exist_ok=True)
                    f = _get_fernet(os.path.dirname(self._filepath))
                    data_on_disk = _walk_sensitive(self._data, encrypt=True, fernet=f)
                    with open(tmp_path, "w", encoding="utf-8") as fh:
                        json.dump(data_on_disk, fh, ensure_ascii=False, indent=2)
                    # T-35 再保险（R15）：不做跨进程文件锁，但让"丢一次写"可恢复——
                    # 覆盖前留一份可回滚副本；备份失败不阻断写盘主流程。
                    if target.exists():
                        try:
                            shutil.copyfile(str(target), str(target) + ".bak")
                        except OSError:
                            pass
                    os.replace(tmp_path, str(target))
                    os.chmod(str(target), 0o600)
                    wrote = True
                    break
                except (PermissionError, FileNotFoundError, OSError):
                    if attempt == retries - 1:
                        raise
                    time.sleep(delay * (2**attempt))
        if wrote:
            _publish_config_written(self)

    def reset(self, key: str | None = None) -> None:
        """重置配置项。key 为 None 时清空全部配置，否则删除指定键。"""
        with self._lock:
            # =为全量重置，用于"恢复出厂设置"场景
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

    def reload(self) -> None:
        """从磁盘重新加载配置，丢弃内存中未保存的修改。

        供运行时配置同步使用：外部修改配置文件后调用本方法刷新内存态。
        """
        with self._lock:
            self._data = {}
        self._load()

    def populate_defaults(self, defaults: dict[str, Any]) -> None:
        """将工厂默认值中尚未设置的键填充到当前配置（不覆盖已有值）。"""
        # 仅在键值为时才填充，保留用户已有的自定义值
        for k, v in defaults.items():
            if self.get(k) is None:
                self.set(k, v)

    def export_rules(self, file_path: str) -> bool:
        """将当前所有站点规则导出到指定 JSON 文件。返回 True/False 表示成功/失败。"""
        # 委托给迁移模块的_规则函数，保持单一导出逻辑入口
        from .migrate import export_rules as _export

        return _export(self, file_path)

    def import_rules(self, file_path: str) -> int:
        """从 JSON 文件导入规则并合并到已有配置。返回成功导入数量，-1 表示失败。"""
        # 委托给迁移模块的_规则函数，保证导入逻辑唯一
        from .migrate import import_rules as _import

        return _import(self, file_path)

    # ── 内部 ────────────────────────

    def _load(self) -> None:
        """从 JSON 文件加载配置：先清理残留 .tmp → 读取解密 → 填充默认值 → 迁移旧键。

        写盘语义（#31-P2 / R14-3a，2026-10-01）：**仅当补默认值或迁移旧键实际改动了内存态时**
        才写回文件。原实现无条件 `save()`，等价于“每构造一次 = 读一次 + 写一次”——
        热路径（`scorer.get_profile` 每次新建实例）单批查询触发 ≈126 次整份 config.json 覆盖写
        （实测 ≈0.58 s ／ ≈519 KiB），既放大“多实例 last-writer-wins 丢配置”的窗口，也拖慢查询。
        保持的契约：① 文件不存在（首次运行）仍写盘；② 补默认值/迁移有变更写盘一次；
        ③ 显式 `set()` + `save()` 仍持久化；④ 损坏文件仍先备份 `.corrupted.<ts>` 再以默认值初始化并写盘。
        """
        # 清理上次崩溃可能残留的.文件，避免占用磁盘
        cfg_dir = os.path.dirname(self._filepath)
        if os.path.isdir(cfg_dir):
            for name in os.listdir(cfg_dir):
                if name.endswith(".tmp"):
                    try:
                        os.remove(os.path.join(cfg_dir, name))
                    except OSError:
                        # 已知可忽略：临时文件清理失败不影响主流程
                        pass
        try:
            if os.path.exists(self._filepath):
                with open(self._filepath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                from .crypto import _get_fernet, _walk_sensitive

                f_obj = _get_fernet(os.path.dirname(self._filepath))
                # 解密敏感字段后才是内存中的可用数据
                self._data = _walk_sensitive(raw, encrypt=False, fernet=f_obj)
                # #31-P2：先留存改动前快照，仅当补默认值/迁移旧键真的改了内容才写回
                before = copy.deepcopy(self._data)
                self.populate_defaults(FACTORY_DEFAULTS)
                _migrate_ui_keys(self)
                if self._data != before:
                    self.save()
                return
        except (json.JSONDecodeError, OSError):
            # T-35 再保险（R15）：主文件损坏时**优先**尝试写前备份回滚
            bak = self._filepath + ".bak"
            if os.path.exists(bak):
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    from .crypto import _get_fernet, _walk_sensitive

                    f_obj = _get_fernet(os.path.dirname(self._filepath))
                    self._data = _walk_sensitive(raw, encrypt=False, fernet=f_obj)
                    self.populate_defaults(FACTORY_DEFAULTS)
                    _migrate_ui_keys(self)
                    logger.warning("配置解析失败，已从写前备份回滚: %s", bak)
                    self.save()
                    return
                except (json.JSONDecodeError, OSError):
                    # 备份同样不可用 → 走原有"备份损坏文件 + 默认值初始化"路径（契约④不变）
                    pass
            # 数据损坏时备份原文件，避免数据彻底丢失
            backup = self._filepath + ".corrupted." + datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                os.rename(self._filepath, backup)
            except OSError:
                # 已知可忽略：损坏文件备份失败，仍以默认值初始化
                pass
        # 文件不存在或解析失败时，用工厂默认值初始化
        self._data = {}
        self._populate_first_run()

    def _populate_first_run(self) -> None:
        """首次运行时用工厂默认值初始化并保存。"""
        # 逐键确保中间节点正确创建
        for k, v in FACTORY_DEFAULTS.items():
            self.set(k, v)
        self.save()


# ── 共享实例 + 显式配置失效通知（#31-P1 / R14-3b，2026-10-01）────────────────
# 背景：热路径 `query/routing/scorer.py::get_profile()` 原为“每次调用新建 ConfigManager”——
#   单批查询实测 133 次构造（R14-2 盘点）。P2 已让单次构造不再写盘，但重复构造仍需消除。
# 机制：**按绝对路径共享实例** + **显式失效通知**（写盘或显式调用触发）。
#   ① 自己写盘：内存态即权威 → 保留缓存实例，仅通知监听者；
#   ② 他方写盘（GUI 设置页 `_settings.py` / Web `docker/api/settings.py` 各自持有的实例）：
#      共享缓存已陈旧 → 移除该缓存并通知监听者，下次读取自动重建（读取新值）。
# 明确**不做**基于时间的静默 TTL 缓存——失效只能由写盘或 `invalidate_shared_config()` 触发，
#   否则会掩盖“配置已改但读不到”的 bug（用户约束）。
# 可重入锁（RLock）：构造 `ConfigManager` 时首次运行会在 `_load()` 内写盘并发布失效通知，
# 而通知路径同样要进入本锁——非重入锁会自锁死（R14-3b 实测）。重入锁同时保证：
# 同一路径的并发首次获取被串行化，所有调用方拿到**同一实例**。
# 注意：监听者在持锁上下文内被回调，必须保持轻量且不得阻塞等待其它需要本锁的线程。
_SHARED_LOCK = threading.RLock()
_SHARED_INSTANCES: dict[str, ConfigManager] = {}
_INVALIDATION_LISTENERS: list[Callable[[str], None]] = []


def default_config_path() -> str:
    """返回默认配置文件绝对路径（与 `ConfigManager()` 缺省路径同一口径）。"""
    from .paths import _get_config_dir

    return os.path.abspath(os.path.join(_get_config_dir(), "config.json"))


def get_shared_config(filepath: str | None = None) -> ConfigManager:
    """获取（并按需创建）该路径的共享 ConfigManager 实例——热路径应统一从这里取。

    线程安全：`_SHARED_LOCK` 为**可重入锁**，构造在锁内完成——首次运行会在 `_load()` 内
    写盘并发布失效通知（同线程重入本锁，非重入锁会死锁）；锁内构造也保证同一路径并发
    首次获取只产生一个实例、且所有调用方拿到同一对象。
    """
    path = default_config_path() if filepath is None else os.path.abspath(filepath)
    with _SHARED_LOCK:
        instance = _SHARED_INSTANCES.get(path)
        if instance is None:
            instance = ConfigManager(path)
            _SHARED_INSTANCES[path] = instance
        return instance


def invalidate_shared_config(filepath: str | None = None) -> int:
    """显式使共享实例失效（外部改动配置文件后调用）；返回被移除的实例数（0/1）。"""
    path = default_config_path() if filepath is None else os.path.abspath(filepath)
    with _SHARED_LOCK:
        removed = 1 if _SHARED_INSTANCES.pop(path, None) is not None else 0
    _notify_config_invalidated(path)
    return removed


def register_invalidation_listener(listener: Callable[[str], None]) -> None:
    """注册配置失效监听者（回调参数＝配置文件绝对路径）。重复注册同一回调不重复添加。"""
    with _SHARED_LOCK:
        if listener not in _INVALIDATION_LISTENERS:
            _INVALIDATION_LISTENERS.append(listener)


def unregister_invalidation_listener(listener: Callable[[str], None]) -> None:
    """注销配置失效监听者（不存在时静默）。"""
    with _SHARED_LOCK:
        if listener in _INVALIDATION_LISTENERS:
            _INVALIDATION_LISTENERS.remove(listener)


def _notify_config_invalidated(path: str) -> None:
    """同步回调所有监听者；单个监听者异常不得影响其它监听者与调用方。"""
    with _SHARED_LOCK:
        listeners = list(_INVALIDATION_LISTENERS)
    for listener in listeners:
        try:
            listener(path)
        except Exception:  # noqa: BLE001 - 监听者异常必须隔离，不能破坏写盘主流程
            logger.exception("配置失效监听者异常: %s", path)


def _publish_config_written(instance: ConfigManager) -> None:
    """写盘成功后发布失效通知（供 `ConfigManager.save()` 调用）。"""
    path = instance._filepath
    with _SHARED_LOCK:
        cached = _SHARED_INSTANCES.get(path)
        if cached is not None and cached is not instance:
            _SHARED_INSTANCES.pop(path, None)
    _notify_config_invalidated(path)
