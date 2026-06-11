"""小红书 XYW_ 签名（data API 需此格式，XYS_ 会返回 406）。"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from xhshow import Xhshow
from xhshow.utils.url_utils import extract_uri

XYW_PREFIX = "XYW_"
XYW_SIGN_SVN = "56"
XYW_SIGN_TYPE = "x2"
XYW_SIGN_VERSION = "1"
XYW_AES_KEY = b"7cc4adla5ay0701v"
XYW_AES_IV = b"4uzjr7mbsibcaldp"
XYW_ENV_FLAGS = "0|0|0|1|0|0|1|0|0|0|1|0|0|0|0|1|0|0|1"


def build_xyw_payload_hex(full_uri: str, a1_value: str, timestamp_ms: str) -> str:
    x1 = hashlib.md5(f"url={full_uri}".encode()).hexdigest()
    message = f"x1={x1};x2={XYW_ENV_FLAGS};x3={a1_value};x4={timestamp_ms};".encode()
    plaintext = pad(base64.b64encode(message), AES.block_size)
    cipher = AES.new(XYW_AES_KEY, AES.MODE_CBC, XYW_AES_IV)
    return cipher.encrypt(plaintext).hex()


def sign_xyw(
    client: Xhshow,
    method: str,
    uri: str,
    a1_value: str,
    payload: dict[str, Any] | None = None,
    timestamp: float | None = None,
    xsec_appid: str = "xhs-pc-web",
) -> str:
    if timestamp is None:
        timestamp = time.time()
    uri_path = extract_uri(uri)
    content_string = client._build_content_string(method.upper(), uri_path, payload)
    timestamp_ms = str(client.get_x_t(timestamp))
    payload_hex = build_xyw_payload_hex(content_string, a1_value, timestamp_ms)
    xyw_data = {
        "signSvn": XYW_SIGN_SVN,
        "signType": XYW_SIGN_TYPE,
        "appId": xsec_appid,
        "signVersion": XYW_SIGN_VERSION,
        "payload": payload_hex,
    }
    xyw_json = json.dumps(xyw_data, separators=(",", ":"), ensure_ascii=False)
    return XYW_PREFIX + base64.b64encode(xyw_json.encode()).decode()


def sign_headers_get_xyw(
    client: Xhshow,
    uri: str,
    cookies: dict[str, Any] | str,
    params: dict[str, Any] | None = None,
    timestamp: float | None = None,
    xsec_appid: str = "xhs-pc-web",
) -> dict[str, str]:
    if timestamp is None:
        timestamp = time.time()
    cookie_dict = client._parse_cookies(cookies)
    a1_value = cookie_dict.get("a1")
    if not a1_value:
        raise ValueError("Missing 'a1' in cookies")

    x_s = sign_xyw(client, "GET", uri, a1_value, params, timestamp, xsec_appid)
    return {
        "x-s": x_s,
        "x-s-common": client.sign_xs_common(cookie_dict),
        "x-t": str(client.get_x_t(timestamp)),
        "x-b3-traceid": client.get_b3_trace_id(),
        "x-xray-traceid": client.get_xray_trace_id(timestamp=int(timestamp * 1000)),
    }
