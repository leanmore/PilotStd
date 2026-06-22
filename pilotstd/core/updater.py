# pilotstd/core/updater.py
# 半自动升级：GitHub Release 检查、下载、校验、生成更新脚本
#
# UI 层只负责对话框交互，本模块处理所有网络/文件/校验逻辑。

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
import zipfile
from typing import Optional

from pilotstd import __version__

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/leanmore/PilotStd/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/leanmore/PilotStd/releases/latest"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _make_request(url: str, timeout: int = 10) -> urllib.request.Request:
    """构建带 User-Agent 和可选 Token 的请求对象。"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", f"PilotStd/{__version__}")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    return req


def check_latest_version() -> Optional[dict]:
    """检查 GitHub 最新 Release。

    成功返回 {'tag_name': str, 'body': str, 'download_url': str, 'filename': str}
    失败返回 None。
    """
    try:
        req = _make_request(GITHUB_API_URL)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        tag_name = data.get("tag_name", "")
        if not tag_name:
            logger.warning("GitHub Release 缺少 tag_name 字段")
            return None

        body = data.get("body", "")

        # 找到 zip 下载资源
        download_url = ""
        filename = f"PilotStd-{tag_name}.zip"
        for a in data.get("assets", []):
            name = a.get("name", "")
            if name.endswith(".zip") and "PilotStd" in name:
                download_url = a.get("browser_download_url", "")
                filename = name
                break

        if not download_url:
            logger.warning("GitHub Release 缺少 zip 下载资源")
            return None

        return {
            "tag_name": tag_name,
            "body": body,
            "download_url": download_url,
            "filename": filename,
        }
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as e:
        logger.warning("检查更新失败: %s", e)
        return None


def is_newer_version(latest: str, current: str) -> bool:
    """语义化版本比较：latest > current → True。v 前缀自动去除。"""

    def _parse(v: str) -> tuple:
        v = v.lstrip("v")
        parts: list[int] = []
        for p in v.split("."):
            digits = "".join(c for c in p if c.isdigit())
            parts.append(int(digits) if digits else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    return _parse(latest) > _parse(current)


def extract_sha256_from_body(body: str) -> str:
    """从 Release body 中提取 SHA256 校验值。"""
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("sha256:"):
            return line.split(":", 1)[1].strip()
    return ""


def download_update(
    download_url: str, save_path: str, expected_sha256: str = ""
) -> bool:
    """下载更新包并校验完整性。

    校验项：Content-Length 大小匹配、合法 zip 格式、SHA256（如提供）。
    返回 True 表示下载成功且校验通过。
    """
    try:
        req = _make_request(download_url)
        expected_size = 0
        actual_size = 0
        with urllib.request.urlopen(req, timeout=300) as src:
            content_length = src.headers.get("Content-Length", "")
            if content_length:
                expected_size = int(content_length)
            with open(save_path, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
                    actual_size += len(chunk)

        # Content-Length 大小校验
        if expected_size and actual_size != expected_size:
            logger.error(
                "下载不完整：期望 %s 字节，实际 %s", expected_size, actual_size
            )
            return False

        # 合法 zip 校验
        if not zipfile.is_zipfile(save_path):
            logger.error("下载的文件不是有效的 zip 包")
            return False

        # SHA256 校验
        if expected_sha256 and not verify_checksum(save_path, expected_sha256):
            return False

        return True
    except urllib.error.URLError as e:
        logger.error("下载失败: %s", e)
        return False


def verify_checksum(file_path: str, expected_sha256: str) -> bool:
    """校验文件 SHA256 是否匹配。"""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
        if sha256.hexdigest() != expected_sha256:
            logger.error("SHA256 校验失败: 期望 %s...", expected_sha256[:16])
            return False
        return True
    except OSError as e:
        logger.error("读取文件校验失败: %s", e)
        return False


def generate_update_script(zip_path: str, exe_dir: str) -> str:
    """生成 update.bat 更新批处理脚本。返回脚本路径。"""
    exe_path = os.path.join(exe_dir, "PilotStd.exe")
    bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "echo 等待 PilotStd 退出...\r\n"
        ":wait\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        'tasklist /fi "IMAGENAME eq PilotStd.exe" 2>nul | find /i "PilotStd.exe" >nul\r\n'
        "if not errorlevel 1 goto wait\r\n"
        "echo 正在解压更新...\r\n"
        f'powershell -Command "Start-Process -Verb RunAs -ArgumentList \'Expand-Archive -Path \\"{zip_path}\\" -DestinationPath \\"{exe_dir}\\" -Force\'" \r\n'
        f'if exist "{zip_path}" del /q "{zip_path}"\r\n'
        "echo 更新完成，正在启动...\r\n"
        f'start "" "{exe_path}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path = os.path.join(exe_dir, "update.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)
    return bat_path
