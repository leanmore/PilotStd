"""企业微信回调加解密（WXBizMsgCrypt 标准实现的等价物，T-43）。

## 为什么自实现而不引第三方库

`wechatpy`（企微生态最常用的实现）是全功能 SDK，为一段 80 行的算法引入整棵依赖树不划算，
且其入口是"Flask/Django 式"的请求对象耦合；本仓需要的是**纯函数式**的
"密文入 → 明文出"，便于单测与复用。算法本身是公开且稳定的（企微《加解密方案说明》）。

## 算法（**不得自创**，逐条对应官方口径）

1. **签名**：``sha1("".join(sorted([token, timestamp, nonce, encrypt_or_echostr])))``，
   与请求参数 ``msg_signature``（小写十六进制）比对；
2. **密钥**：``key = base64.b64decode(encoding_aes_key + "=")`` ⇒ 32 字节（AES-256），
   ``iv = key[:16]``；**AES-256-CBC**；
3. **明文布局**：``random(16B) + struct.pack(">I", len(msg)) + msg + receiveid``；
4. **填充**：PKCS#7，但企微按 **32 字节块**对齐（不是 AES 的 16 字节块）——
   官方实现先把明文补齐到 32 的整数倍，再交给 CBC（16 字节块）逐块加密；
5. **receiveid 校验**：解密后**必须**比对 ``receiveid``（企微为 corpid），不匹配即拒绝——
   这是防"把发给别的企业/应用的回调密文重放到我们接口"的唯一边界。

## 加密函数为什么必须实现

本机离线拿不到企微官方的回调测试向量（官方文档正文 JS 渲染，本仓取证记录见
`docs/plans/notification-redesign/14-MoviePilot源码侦查报告.md` §2.1）。因此算法正确性
由**自加密 → 自解密往返**锁定：`encrypt_message` 与 `decrypt_message` 互为逆运算，
且填充/布局/签名三处口径在同一个模块内自洽。加密本身也是后续"被动回复"（加密 XML 响应）
所需的能力，故不是测试专用代码。

## 安全口径

- 签名比对用 ``hmac.compare_digest``（常量时间），**不得**用 ``==`` 短路比较——
  `msg_signature` 是外部输入，短路比较会把签名逐字节暴露给计时探测；
- 任何失败路径都**明确拒绝**（抛 `WeChatCryptoError`）并记 `logger.warning`，
  绝不"容错放行"；调用方负责转成 401/403；
- 错误信息只进本地日志，**不回给**调用方（避免给探测者反馈）。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import os
import struct
import xml.etree.ElementTree as ET
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

__all__ = [
    "WeChatCrypto",
    "WeChatCryptoError",
    "compute_signature",
    "credentials_from",
    "extract_encrypt",
    "parse_plain_xml",
]

logger = logging.getLogger(__name__)

# 企微 PKCS#7 按 **32 字节块**对齐（官方口径；AES 的 CBC 再用 16 字节块切分）
_PKCS7_BLOCK_SIZE = 32
# AES-256 密钥长度与 IV 长度（IV 取密钥前 16 字节，官方口径）
_AES_KEY_SIZE = 32
_IV_SIZE = 16
# 明文布局里的 4 字节大端消息长度
_LENGTH_FIELD_SIZE = 4


class WeChatCryptoError(Exception):
    """企微回调加解密失败（签名不符/密文非法/receiveid 不匹配/字段缺失）。

    对外一律表现为"验签失败"，**不细分原因**（避免给探测者反馈）；
    具体原因只进本地日志。
    """


def _pad(data: bytes, block_size: int = _PKCS7_BLOCK_SIZE) -> bytes:
    """PKCS#7 填充到 ``block_size`` 的整数倍（企微按 32 字节块）。"""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len


def _unpad(data: bytes, block_size: int = _PKCS7_BLOCK_SIZE) -> bytes:
    """去掉 PKCS#7 填充；非法填充直接拒绝（不做"尽力而为"的截断）。"""
    if not data:
        raise WeChatCryptoError("empty plaintext")
    pad_len = data[-1]
    # 边界三重校验：填充长度落在 (0, block_size] 且尾部 pad_len 字节全等于 pad_len
    if pad_len <= 0 or pad_len > block_size or pad_len > len(data):
        raise WeChatCryptoError(f"invalid pkcs7 padding length: {pad_len}")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise WeChatCryptoError("invalid pkcs7 padding bytes")
    return data[:-pad_len]


class WeChatCrypto:
    """企业微信回调的验签 + 加解密（一次构造成本 = 一次 base64 解码，可复用）。

    参数与企微后台"接收消息服务器配置"三项一一对应：
    · ``token``：``Token``（参与 SHA1 签名）；
    · ``encoding_aes_key``：``EncodingAESKey``（43 字符，base64 解码后 32 字节）；
    · ``receive_id``：``receiveid``，企微为 **corpid**（解密后必须相等，否则拒绝）。
    """

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        self._token = token or ""
        self._receive_id = receive_id or ""
        # 43 字符 + 补一个 "=" ⇒ 32 字节。先做格式预检：非法值应在**构造期**暴露，
        # 而不是等到每条回调进来才在解密里炸（构造失败由调用方按"凭证未配置"处理）。
        padded = f"{encoding_aes_key}="
        try:
            key = base64.b64decode(padded)
        except (binascii.Error, ValueError) as e:
            # 不打印密钥本身（长度也不打：长度可辅助暴力破解的可行性判断）
            logger.warning("wechat crypto: encoding_aes_key is not valid base64: %s", e)
            raise WeChatCryptoError("invalid encoding_aes_key") from e
        if len(key) != _AES_KEY_SIZE:
            logger.warning(
                "wechat crypto: encoding_aes_key decodes to %d bytes, expected %d",
                len(key),
                _AES_KEY_SIZE,
            )
            raise WeChatCryptoError("invalid encoding_aes_key length")
        self._key = key
        self._iv = key[:_IV_SIZE]

    # ── 签名 ────────────────────────────────────────────────────────────────

    def check_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypt: str) -> bool:
        """比对 ``msg_signature`` 与 SHA1(token, timestamp, nonce, encrypt)。

        ``encrypt``：URL 验证（GET）时是 ``echostr``，消息（POST）时是密文 ``Encrypt``。
        **常量时间比较**——短路比较会让外部输入逐字节可探测。
        """
        if not (self._token and msg_signature and timestamp and nonce and encrypt):
            logger.warning("wechat crypto: signature check rejected: missing token/signature/timestamp/nonce/encrypt")
            return False
        expected = compute_signature(self._token, timestamp, nonce, encrypt)
        ok = hmac.compare_digest(msg_signature, expected)
        if not ok:
            # 只记"不符"，不记签名值（签名值本身不敏感，但没必要扩大日志面）
            logger.warning("wechat crypto: msg_signature mismatch")
        return ok

    # ── 解密 / 加密 ─────────────────────────────────────────────────────────

    def decrypt_message(self, encrypt: str) -> str:
        """解密 base64 密文为明文字符串（企微标准的 5 步布局还原）。

        失败一律抛 `WeChatCryptoError`（不返回空串、不返回原文）：
        调用方据此 401，避免"解密失败却继续解析"。
        """
        if not encrypt:
            logger.warning("wechat crypto: decrypt rejected: empty ciphertext")
            raise WeChatCryptoError("empty ciphertext")
        try:
            raw = base64.b64decode(encrypt)
        except (binascii.Error, ValueError) as e:
            logger.warning("wechat crypto: ciphertext is not valid base64: %s", e)
            raise WeChatCryptoError("invalid ciphertext base64") from e
        if not raw or len(raw) % _IV_SIZE != 0:
            logger.warning("wechat crypto: ciphertext length %d is not a multiple of the AES block size", len(raw))
            raise WeChatCryptoError("invalid ciphertext length")

        decryptor = Cipher(algorithms.AES(self._key), modes.CBC(self._iv)).decryptor()
        plain = _unpad(decryptor.update(raw) + decryptor.finalize())

        # 布局：random(16) + len(4, 大端) + msg + receiveid
        if len(plain) < _IV_SIZE + _LENGTH_FIELD_SIZE:
            logger.warning("wechat crypto: decrypted payload too short (%d bytes)", len(plain))
            raise WeChatCryptoError("decrypted payload too short")
        (msg_len,) = struct.unpack(">I", plain[_IV_SIZE : _IV_SIZE + _LENGTH_FIELD_SIZE])
        body_start = _IV_SIZE + _LENGTH_FIELD_SIZE
        body_end = body_start + msg_len
        if body_end > len(plain):
            # 长度字段被篡改/密文被截断时必然走这里；不按"尽力截取"放行
            logger.warning(
                "wechat crypto: declared msg length %d exceeds payload (%d bytes available)",
                msg_len,
                len(plain) - body_start,
            )
            raise WeChatCryptoError("declared msg length exceeds payload")
        message = plain[body_start:body_end]
        received_id = plain[body_end:]

        self._assert_receive_id(received_id)
        try:
            return message.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.warning("wechat crypto: message is not valid utf-8: %s", e)
            raise WeChatCryptoError("message is not valid utf-8") from e

    def _assert_receive_id(self, received_id: bytes) -> None:
        """解密后比对 receiveid（企微为 corpid）；不匹配必须拒绝。

        未配置 `receive_id` 时**不做校验**：企微群机器人/未配置 corpid 的场景下无期望值，
        此时签名（SHA1(token,…)）仍是唯一验签边界；配置了就必须逐字节相等。
        """
        if not self._receive_id:
            return
        if received_id != self._receive_id.encode("utf-8"):
            logger.warning("wechat crypto: receiveid mismatch (rejected)")
            # 期望值/实到值都不进日志：它们标识企业身份，且对排查无必要
            raise WeChatCryptoError("receiveid mismatch")

    def encrypt_message(self, message: str) -> str:
        """把明文加密为 base64 密文（供测试往返与将来的被动回复使用）。

        **为什么要实现**：离线无官方测试向量 ⇒ 用"自加密 → 自解密往返"锁定算法；
        被动回复（加密 XML 响应）也需要它。见模块 docstring。
        """
        msg = message.encode("utf-8")
        # 布局固定：random(16) + 长度(4) + msg + receiveid；随机前缀每次不同（语义等价于 IV）
        body = os.urandom(_IV_SIZE) + struct.pack(">I", len(msg)) + msg + self._receive_id.encode("utf-8")
        encryptor = Cipher(algorithms.AES(self._key), modes.CBC(self._iv)).encryptor()
        cipher = encryptor.update(_pad(body)) + encryptor.finalize()
        return base64.b64encode(cipher).decode("utf-8")

    # ── 请求级入口（GET 验证 / POST 消息）──────────────────────────────────

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """URL 验证（GET）：验签 → 解密 echostr → 返回**明文**（响应体就是它）。

        失败抛 `WeChatCryptoError`；调用方（端点）转 401，**不得**回显任何内容。
        """
        if not self.check_signature(msg_signature, timestamp, nonce, echostr):
            raise WeChatCryptoError("signature mismatch")
        return self.decrypt_message(echostr)

    def decrypt_envelope(self, msg_signature: str, timestamp: str, nonce: str, body: bytes) -> str:
        """消息回调（POST）：从 XML 取 `<Encrypt>` → 验签 → 解密 → 返回明文 XML。

        XML 形态是企微标准（与另外三家的 JSON + header 签名形态不同），
        故解析在**解密之前**（签名覆盖的正是密文本身）。
        """
        encrypt = extract_encrypt(body)
        if not self.check_signature(msg_signature, timestamp, nonce, encrypt):
            raise WeChatCryptoError("signature mismatch")
        return self.decrypt_message(encrypt)


def compute_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    """企微签名：`sha1("".join(sorted([token, timestamp, nonce, encrypt])))`（小写十六进制）。"""
    joined = "".join(sorted([token, timestamp, nonce, encrypt]))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def extract_encrypt(body: bytes) -> str:
    """从回调 XML 取 `<Encrypt>` 文本；缺失/畸形/非法 XML 一律抛 `WeChatCryptoError`。

    用标准库 `ElementTree`：企微回调体是我方 HTTPS 端点收到的报文，不做自定义实体解析
    （`ElementTree` 默认不解析外部实体），且这里**只读一个字段**，不把报文交给业务层。
    """
    if not body:
        logger.warning("wechat crypto: empty callback body")
        raise WeChatCryptoError("empty callback body")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        logger.warning("wechat crypto: callback body is not valid xml: %s", e)
        raise WeChatCryptoError("invalid callback xml") from e
    node = root.find(".//Encrypt")
    text = node.text if node is not None else None
    if not text:
        logger.warning("wechat crypto: callback xml has no <Encrypt> payload")
        raise WeChatCryptoError("missing <Encrypt>")
    return text.strip()


def parse_plain_xml(xml_text: str) -> dict[str, str]:
    """把解密后的明文 XML 解析为**扁平字典**（只取叶子字段，不含命名空间处理）。

    明文字段名即企微协议字段（`MsgType`/`Event`/`EventKey`/`FromUserName`/`ToUserName`/…）；
    取不到时返回空字典由调用方按"未知动作"拒绝——**不做**字段存在性假设。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("wechat crypto: decrypted message is not valid xml: %s", e)
        return {}
    # 去 CDATA 由 ElementTree 自动完成（CDATA 会被并入 text）
    result: dict[str, str] = {}
    for child in root:
        if child.text and str(child.text).strip():
            result[str(child.tag)] = str(child.text).strip()
    return result


def credentials_from(raw: dict[str, Any] | None) -> tuple[str, str, str]:
    """从渠道凭据字典取 `(token, encoding_aes_key, receive_id=corpid)`（缺键取空串）。

    单独成函数：端点与服务层都要做同一件事，避免"两处各写一遍键名"的漂移。
    """
    creds = raw or {}
    return (
        str(creds.get("token") or "").strip(),
        str(creds.get("encoding_aes_key") or "").strip(),
        str(creds.get("corpid") or "").strip(),
    )
