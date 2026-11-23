# 容器//上传脚本—文件上传接口（登录页背景图等）
import os
import re
import uuid

from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..auth import require_role
from ..manager import get_manager_dep

router = APIRouter(tags=["upload"])

from pilotstd.core.config import get_data_dir  # noqa: E402

UPLOAD_DIR = os.path.join(get_data_dir(), "backgrounds")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

# 文件头魔数签名，用于校验上传文件的实际类型
_MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # RIFF....WEBP，需进一步验证
}
_MAX_SIZE = 10 * 1024 * 1024  # 10MB


class UploadResponse(BaseModel):
    """图片上传成功响应：可访问的 URL。"""

    url: str


class LoginBackgroundResponse(BaseModel):
    """登录页背景图 URL 响应（未配置时为空串）。"""

    url: str


def _validate_image(content: bytes, ext: str) -> None:
    """通过文件头魔数和扩展名双重校验图片类型。"""
    # 是文本，不适用魔数检测，简单检查是否以<开头
    if ext == ".svg":
        # ── SVG 的 XSS 风险必须单独处理（NEW-06）──
        # SVG 是 XML，可内嵌 <script>、<foreignObject>、事件属性（onload/onerror）、
        # 外部实体等。仅校验「以 <svg 或 <?xml 开头」**完全挡不住 XSS**：
        # `<?xml ...?><svg onload="alert(document.cookie)">` 能通过原校验。
        # 而 `/api/backgrounds/{filename}` 是同源 FileResponse（Content-Type 由扩展名
        # 推断为 image/svg+xml），浏览器会**按 SVG 文档执行其中脚本** → 存储型 XSS。
        #
        # 策略：拒绝一切可执行构造（宁可误杀，也不放行）。合法背景图不需要脚本、
        # 外部引用或事件属性，故这组黑名单对真实用途无损。
        lowered = content.decode("utf-8", errors="ignore").lower()
        _SVG_FORBIDDEN = (
            "<script",
            "<foreignobject",
            "<iframe",
            "<embed",
            "<object",
            "javascript:",
            "data:text/html",
            "<!entity",  # XXE
            "<!doctype svg [",  # 内联 DTD
        )
        for token in _SVG_FORBIDDEN:
            if token in lowered:
                raise HTTPException(  # i18n-allow: API 错误信息，前端按 code 映射，与同文件既有 8 条同口径
                    400, f"SVG 含不允许的构造（{token}），请用不含脚本的纯图形 SVG"
                )
        # 事件属性：onload= / onerror= / onclick= 等
        if re.search(r"\son[a-z]+\s*=", lowered):
            raise HTTPException(400, "SVG 含事件属性（on*=），请用不含脚本的纯图形 SVG")  # i18n-allow: 同上
        # 必须有 <svg 根元素（允许前置 XML 声明/注释/DOCTYPE）
        if "<svg" not in lowered.lstrip():
            raise HTTPException(400, "文件内容不是有效的 SVG 图片")
        return
    # :容器需检查标识（偏移8字节）
    if ext == ".webp":
        if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
            raise HTTPException(400, "文件内容不是有效的 WebP 图片")
        return
    # //:文件头魔数精确匹配
    for magic, mime in _MAGIC_SIGNATURES.items():
        if content.startswith(magic):
            # 额外校验：扩展名与魔数一致
            ext_to_mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
            }
            expected = ext_to_mime.get(ext)
            if expected and mime != expected:
                raise HTTPException(400, f"文件扩展名与内容不匹配：{ext}")
            return
    raise HTTPException(400, "无法识别的文件类型，仅允许 JPEG/PNG/GIF/WebP/SVG")


@router.post("/api/upload", response_model=UploadResponse)
@require_role("admin")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """上传图片，返回访问路径。"""
    ext = os.path.splitext(file.filename or ".png")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的格式: {ext}，允许: {', '.join(ALLOWED_EXT)}")
    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(400, f"文件不能超过 {_MAX_SIZE // 1024 // 1024}MB")
    _validate_image(content, ext)  # 魔数校验，防止伪造扩展名
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(content)
    return {"url": f"/api/backgrounds/{name}"}


@router.get("/api/backgrounds/{filename}")
def get_upload(filename: str):
    """访问上传的文件（防路径遍历）。"""
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        raise HTTPException(400, "文件名无效")
    path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(path)


@router.get("/api/login-background", response_model=LoginBackgroundResponse)
def get_login_background(mgr=Depends(get_manager_dep)):
    """返回登录页背景图 URL（公开接口，无需认证）。

    登录页在无会话时也必须能拿到背景图，因此不能复用 admin-only 的
    GET /api/settings（未登录 401 / 非 admin 403）。此接口只暴露
    appearance.login_bg 单字段，不泄露其余系统配置。
    """
    raw = mgr.cfg.get("appearance.login_bg", "")
    return {"url": raw if isinstance(raw, str) else ""}
