# 容器//上传脚本—文件上传接口（登录页背景图等）
import os
import uuid

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

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


def _validate_image(content: bytes, ext: str) -> None:
    """通过文件头魔数和扩展名双重校验图片类型。"""
    # 是文本，不适用魔数检测，简单检查是否以<开头
    if ext == ".svg":
        text = content.decode("utf-8", errors="ignore").lstrip()
        if not (text.startswith("<svg") or text.startswith("<?xml")):
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


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
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
