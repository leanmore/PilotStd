"""企微回调加解密（WXBizMsgCrypt 等价实现）单测 —— T-43。

**为什么用"自加密 → 自解密往返"锁定算法**：本机离线取不到企微官方测试向量
（官方文档正文 JS 渲染，取证见 `docs/plans/notification-redesign/14-MoviePilot源码侦查报告.md` §2.1）。
故本文件同时锚定三件事：
① 往返一致（含中文、超长、空串）；
② **固定的签名期望值**（对已知输入的 SHA1 结果写死，防自实现悄悄改口径）；
③ 全部失败路径**明确拒绝**（抛 `WeChatCryptoError`）且**不抛未捕获异常**。
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from pilotstd.core.notification.wechat_crypto import (
    WeChatCrypto,
    WeChatCryptoError,
    compute_signature,
    credentials_from,
    extract_encrypt,
    parse_plain_xml,
)

TOKEN = "pilotstd-token"
# 43 字符合法 EncodingAESKey（base64.b64encode(bytes(range(32))) 去尾 "="，实测生成）
AES_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
CORP_ID = "wwtest"
TIMESTAMP = "1700000000"
NONCE = "n1"

# 固定向量：对已知 (token, timestamp, nonce, echostr) 的 SHA1 期望值（实测生成后写死）
KNOWN_ECHOSTR = "QUJDRA=="
KNOWN_SIGNATURE = "8689c6c93b0ba7f74c0e633bbd2d5fbc69a5b532"


def _crypto(receive_id: str = CORP_ID) -> WeChatCrypto:
    return WeChatCrypto(TOKEN, AES_KEY, receive_id)


def _sign(encrypt: str) -> str:
    return compute_signature(TOKEN, TIMESTAMP, NONCE, encrypt)


class TestRoundTrip:
    """自加密 → 自解密往返：算法正确性的**唯一**离线证据（无官方向量）。"""

    @pytest.mark.parametrize(
        "message",
        [
            "hello",
            "扫描完成：标准文件已下载",
            "",  # 空消息：长度字段为 0，是最容易写错的边界
            "<xml><EventKey>ignore:7:1</EventKey></xml>",
            "长" * 5000,  # 超长：跨 32 字节块的填充必须仍然自洽
            "a" * 31 + "中",  # 恰好在填充边界附近（31 字节 + 3 字节汉字）
        ],
    )
    def test_encrypt_then_decrypt_is_identity(self, message: str) -> None:
        crypto = _crypto()
        assert crypto.decrypt_message(crypto.encrypt_message(message)) == message

    def test_encrypt_is_randomized_but_decrypts_same(self) -> None:
        """两次加密同一明文结果不同（随机前缀）——防"随机位被写成常量"的实现退化。"""
        crypto = _crypto()
        first, second = crypto.encrypt_message("same"), crypto.encrypt_message("same")
        assert first != second
        assert crypto.decrypt_message(first) == crypto.decrypt_message(second) == "same"

    def test_ciphertext_is_multiple_of_16_bytes(self) -> None:
        """CBC 输入必须是 16 字节块的整数倍（32 字节 PKCS#7 填充的直接后果）。"""
        for message in ("a", "a" * 17, "a" * 33):
            raw = base64.b64decode(_crypto().encrypt_message(message))
            assert len(raw) % 16 == 0


class TestSignature:
    """签名口径：SHA1(sorted([token, timestamp, nonce, encrypt])) 的小写十六进制。"""

    def test_known_vector(self) -> None:
        assert _sign(KNOWN_ECHOSTR) == KNOWN_SIGNATURE

    def test_matches_independent_sha1(self) -> None:
        """与"就地手算的 SHA1"逐字节一致（防实现把排序/拼接写错）。"""
        encrypt = "QUJDRA=="
        expected = hashlib.sha1("".join(sorted([TOKEN, TIMESTAMP, NONCE, encrypt])).encode("utf-8")).hexdigest()
        assert _sign(encrypt) == expected

    def test_check_signature_accepts_and_rejects(self) -> None:
        crypto = _crypto()
        assert crypto.check_signature(KNOWN_SIGNATURE, TIMESTAMP, NONCE, KNOWN_ECHOSTR) is True
        assert crypto.check_signature(KNOWN_SIGNATURE.upper(), TIMESTAMP, NONCE, KNOWN_ECHOSTR) is False
        assert crypto.check_signature(KNOWN_SIGNATURE, TIMESTAMP, NONCE, "TUlORQ==") is False
        # 缺任一项一律 False（不抛异常）
        for args in (("", TIMESTAMP, NONCE, KNOWN_ECHOSTR), (KNOWN_SIGNATURE, "", NONCE, KNOWN_ECHOSTR)):
            assert crypto.check_signature(*args) is False

    def test_verify_url_returns_plaintext_and_rejects_bad_signature(self) -> None:
        crypto = _crypto()
        echostr = crypto.encrypt_message("1616140317555161")
        assert crypto.verify_url(_sign(echostr), TIMESTAMP, NONCE, echostr) == "1616140317555161"
        with pytest.raises(WeChatCryptoError):
            crypto.verify_url("0" * 40, TIMESTAMP, NONCE, echostr)


class TestDecryptRejections:
    """失败路径必须**明确拒绝**，且不得抛未捕获的其它异常类型。"""

    def test_illegal_base64_echostr_rejected(self) -> None:
        crypto = _crypto()
        with pytest.raises(WeChatCryptoError):
            crypto.decrypt_message("!!! not base64 !!!")
        # 非法 base64 经由 verify_url（先验签再解密）同样只是拒绝，不炸
        with pytest.raises(WeChatCryptoError):
            crypto.verify_url(_sign("!!! not base64 !!!"), TIMESTAMP, NONCE, "!!! not base64 !!!")

    def test_tampered_ciphertext_rejected(self) -> None:
        """密文被篡改 1 字节 ⇒ 拒绝（填充校验或长度字段必然对不上）。"""
        crypto = _crypto()
        raw = bytearray(base64.b64decode(crypto.encrypt_message("scan complete")))
        raw[16] ^= 0x01  # 翻转第二块的第一个字节（避开随机前缀）
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(WeChatCryptoError):
            crypto.decrypt_message(tampered)

    def test_truncated_ciphertext_rejected(self) -> None:
        crypto = _crypto()
        raw = base64.b64decode(crypto.encrypt_message("scan complete"))
        with pytest.raises(WeChatCryptoError):
            crypto.decrypt_message(base64.b64encode(raw[: len(raw) // 2]).decode())

    def test_receive_id_mismatch_rejected(self) -> None:
        """`receiveid` 不匹配 ⇒ 拒绝（防"发给别的企业的密文"被重放）。"""
        sender = WeChatCrypto(TOKEN, AES_KEY, "ww-other-corp")
        receiver = _crypto()  # corpid = wwtest
        with pytest.raises(WeChatCryptoError):
            receiver.decrypt_message(sender.encrypt_message("hello"))
        # 同 corpid 则解得出（证明上一条拒绝源于 receiveid，而不是"压根解不了"）
        assert _crypto("ww-other-corp").decrypt_message(sender.encrypt_message("hello")) == "hello"

    def test_empty_receive_id_skips_check(self) -> None:
        """未配置 corpid ⇒ 不做 receiveid 校验（签名仍是唯一验签边界），但不因此报错。"""
        assert WeChatCrypto(TOKEN, AES_KEY, "").decrypt_message(_crypto().encrypt_message("hi")) == "hi"

    def test_invalid_encoding_aes_key_rejected_at_construction(self) -> None:
        for bad in ("!!!not-base64!!!", "短", "QUJD"):  # 非法 base64 / 解出长度不是 32
            with pytest.raises(WeChatCryptoError):
                WeChatCrypto(TOKEN, bad, CORP_ID)

    def test_empty_ciphertext_rejected(self) -> None:
        with pytest.raises(WeChatCryptoError):
            _crypto().decrypt_message("")

    def test_wrong_key_cannot_decrypt(self) -> None:
        other = WeChatCrypto(TOKEN, base64.b64encode(bytes(range(32, 64))).decode().rstrip("="), CORP_ID)
        with pytest.raises(WeChatCryptoError):
            other.decrypt_message(_crypto().encrypt_message("secret"))


class TestEnvelope:
    """POST 信封：从 XML 取 `<Encrypt>` → 验签 → 解密。"""

    def test_decrypt_envelope_round_trip(self) -> None:
        crypto = _crypto()
        plain = "<xml><EventKey>ignore:7:1</EventKey><FromUserName>zhangsan</FromUserName></xml>"
        encrypt = crypto.encrypt_message(plain)
        body = (
            f"<xml><ToUserName><![CDATA[{CORP_ID}]]></ToUserName><Encrypt><![CDATA[{encrypt}]]></Encrypt></xml>"
        ).encode()
        assert crypto.decrypt_envelope(_sign(encrypt), TIMESTAMP, NONCE, body) == plain

    def test_bad_signature_rejected(self) -> None:
        crypto = _crypto()
        encrypt = crypto.encrypt_message("<xml/>")
        body = f"<xml><Encrypt><![CDATA[{encrypt}]]></Encrypt></xml>".encode()
        with pytest.raises(WeChatCryptoError):
            crypto.decrypt_envelope("0" * 40, TIMESTAMP, NONCE, body)

    def test_missing_encrypt_rejected(self) -> None:
        for body in (b"", b"<xml></xml>", b"not xml at all", b"<xml><Encrypt></Encrypt></xml>"):
            with pytest.raises(WeChatCryptoError):
                _crypto().decrypt_envelope(_sign("x"), TIMESTAMP, NONCE, body)

    def test_extract_encrypt_accepts_plain_and_cdata(self) -> None:
        assert extract_encrypt(b"<xml><Encrypt>abc</Encrypt></xml>") == "abc"
        assert extract_encrypt(b"<xml><Encrypt><![CDATA[abc]]></Encrypt></xml>") == "abc"


class TestPlainXmlParsing:
    """解密后的明文 XML → 扁平字典（不含命名空间处理，不做字段存在性假设）。"""

    def test_fields_extracted(self) -> None:
        xml = (
            "<xml><ToUserName><![CDATA[ww1]]></ToUserName>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<CreateTime>1348831860</CreateTime><MsgType><![CDATA[event]]></MsgType>"
            "<Event><![CDATA[click]]></Event><EventKey><![CDATA[ignore:7:1]]></EventKey></xml>"
        )
        parsed = parse_plain_xml(xml)
        assert parsed["FromUserName"] == "zhangsan"
        assert parsed["EventKey"] == "ignore:7:1"
        assert parsed["CreateTime"] == "1348831860"

    def test_invalid_xml_returns_empty(self) -> None:
        assert parse_plain_xml("<xml><unclosed>") == {}

    def test_blank_values_skipped(self) -> None:
        assert "EventKey" not in parse_plain_xml("<xml><EventKey>  </EventKey></xml>")


def test_credentials_from_reads_expected_keys() -> None:
    """凭据字典 → 三元组（缺键取空串），供端点与服务层共用同一键名口径。"""
    assert credentials_from({"token": " t ", "encoding_aes_key": "k", "corpid": "ww"}) == ("t", "k", "ww")
    assert credentials_from(None) == ("", "", "")
