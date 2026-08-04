# 项目/核心/_脚本—路径遍历防护统一校验函数
import os

# 环境允许访问的额外目录（独立挂载点，与库根目录分离）
_DOCKER_EXTRA_ROOTS = ["/inbox", "/standards"]


def get_allowed_roots(config_root: str = "") -> list[str]:
    """返回允许访问的根目录列表。

    包含：用户配置的库根目录 + STANDARD_ROOT 环境变量 + Docker 固定挂载点。
    路径经 os.path.realpath 规范化，自动去重。
    """
    roots: list[str] = []
    if config_root:
        roots.append(os.path.realpath(config_root))
    std_root = os.environ.get("STANDARD_ROOT", "")
    if std_root:
        std_real = os.path.realpath(std_root)
        if std_real not in roots:
            roots.append(std_real)
    for extra in _DOCKER_EXTRA_ROOTS:
        extra_real = os.path.realpath(extra)
        if extra_real not in roots:
            roots.append(extra_real)
    return roots


def validate_path_in_root(path: str, root: str) -> str:
    """校验 path 解析后的真实路径在 root 范围内，否则 raise ValueError。

    返回 path 的规范化绝对路径。
    用于下载引擎、扫描器等需要确保写入路径不越界的场景。
    """
    real_path = os.path.realpath(path)
    real_root = os.path.realpath(root)
    if not real_path.startswith(real_root + os.sep) and real_path != real_root:
        raise ValueError(f"路径越界，拒绝写入: {path}")
    return real_path
