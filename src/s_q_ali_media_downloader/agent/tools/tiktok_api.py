"""TikTok listing data via customer-authorized requests (web API + HTML).

TikTok no longer serves #tag / /search listing data to anonymous clients:
the web app renders an empty JS shell and the JSON APIs require the
browser VM signature (X-Bogus) plus session cookies. This module gives
the TikTok Agent its best-effort capability:

1. Netscape cookies.txt loader (values are never logged).
2. X-Bogus signing (pure Python, custom Base64 + RC4) for the
   challenge/item_list and search/item/full endpoints.
3. Cookies-aware HTML harvesting of www/m tag and search pages.

When TikTok still rejects the request, callers get an explicit reason
("listing blocked") instead of a silent zero so the UI can guide the
user to seed profiles (@handles / profile URLs), which always work.
"""

import base64
import hashlib
import logging
import re
import struct
import time
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

CUSTOM_B64_ALPHABET = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe="
STANDARD_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
UA_RC4_KEY = bytes([0x00, 0x01, 0x0E])
PAYLOAD_RC4_KEY = bytes([0xFF])
LEADING_BYTE = 0x40
MAGIC_CONSTANT = 0x4A41279F

WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HANDLE_PATTERN = re.compile(r"tiktok\.com/@([A-Za-z0-9\._]{2,30})")
UNIQUE_ID_PATTERN = re.compile(r'"uniqueId"\s*:\s*"([A-Za-z0-9\._]{2,30})"')

EXCLUDED_HANDLES = {
    "tiktok",
    "foryou",
    "following",
    "explore",
    "live",
    "upload",
    "login",
    "signup",
    "discover",
    "music",
    "video",
}


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def _double_md5(data: str) -> bytes:
    first = hashlib.md5(data.encode("utf-8")).hexdigest()
    second = hashlib.md5(bytes.fromhex(first)).hexdigest()
    return bytes.fromhex(second)


def _md5_user_agent(user_agent: str) -> bytes:
    encrypted = _rc4(UA_RC4_KEY, user_agent.encode("utf-8"))
    b64 = base64.b64encode(encrypted).decode("latin-1")
    return bytes.fromhex(hashlib.md5(b64.encode("latin-1")).hexdigest())


def generate_xbogus(query_string: str, user_agent: str, timestamp: int | None = None) -> str:
    if timestamp is None:
        timestamp = int(time.time())
    params_md5 = _double_md5(query_string)
    body_md5 = _double_md5("")
    ua_md5 = _md5_user_agent(user_agent)

    payload = bytearray()
    payload.append(LEADING_BYTE)
    payload.extend(UA_RC4_KEY)
    payload.extend(params_md5[14:16])
    payload.extend(body_md5[14:16])
    payload.extend(ua_md5[14:16])
    payload.extend(struct.pack(">I", timestamp))
    payload.extend(struct.pack(">I", MAGIC_CONSTANT))
    xor_check = 0
    for byte in payload:
        xor_check ^= byte
    payload.append(xor_check & 0xFF)

    final = bytes([0x02, 0xFF]) + _rc4(PAYLOAD_RC4_KEY, bytes(payload))
    standard = base64.b64encode(final).decode("ascii")
    return standard.translate(str.maketrans(STANDARD_B64_ALPHABET, CUSTOM_B64_ALPHABET))


def _clean_handles(handles: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in handles:
        handle = raw.lstrip(".").lower()
        if (
            handle in seen
            or handle in EXCLUDED_HANDLES
            or "." in raw
            or len(handle) < 2
            or len(handle) > 30
        ):
            continue
        seen.add(handle)
        out.append(handle)
    return out


class TikTokApiSession:
    """Best-effort TikTok listing client backed by a Netscape cookies.txt."""

    def __init__(self, cookiefile: str | None = None, timeout: float = 20.0):
        self.cookiefile = cookiefile
        self.timeout = timeout
        self.user_agent = WEB_USER_AGENT
        self._flat_cookies: dict[str, str] = {}
        if cookiefile:
            self._flat_cookies = self._load_cookies(cookiefile)

    @staticmethod
    def _load_cookies(cookiefile: str) -> dict[str, str]:
        flat: dict[str, str] = {}
        try:
            with open(cookiefile, "r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("#HttpOnly_."):
                        line = line[len("#HttpOnly_") :]
                    parts = line.split("\t")
                    if len(parts) != 7:
                        continue
                    _, _subdomains, _path, _secure, _expiry, name, value = parts
                    if name and value:
                        flat[name] = value
        except Exception as e:
            logger.warning("Failed to load cookies file %s: %s", cookiefile, e)
            return {}
        if flat:
            logger.info("Loaded %d cookies from %s", len(flat), cookiefile)
        return flat

    @property
    def cookie_count(self) -> int:
        return len(self._flat_cookies)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={
                "User-Agent": self.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
                "Cookie": "; ".join(
                    f"{k}={v}" for k, v in self._flat_cookies.items()
                ),
            },
            cookies=self._flat_cookies,
            timeout=self.timeout,
            follow_redirects=True,
        )

    def _sign_base_params(self) -> dict:
        params = {
            "device_platform": "webapp",
            "aid": "1988",
            "app_language": "en",
            "language": "en",
            "region": "US",
            "os": "windows",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "en-US",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "124.0.0.0",
            "browser_online": "true",
            "verifyFp": "verify_" + self._flat_cookies.get("s_v_web_id", "0")[:22],
        }
        if "msToken" in self._flat_cookies:
            params["msToken"] = self._flat_cookies["msToken"]
        if "ttwid" in self._flat_cookies:
            params["ttwid"] = self._flat_cookies["ttwid"]
        return params

    def _signed_url(self, path: str, params: dict) -> str:
        query = urlencode(params)
        return f"https://www.tiktok.com{path}?{query}&X-Bogus={generate_xbogus(query, self.user_agent)}"

    def fetch_tag_handles(self, tag: str, limit: int = 40) -> list[str]:
        handles: list[str] = []
        params = self._sign_base_params()
        params.update({"challengeName": tag, "count": str(limit), "cursor": "0", "sort_type": "0"})
        handles += self._api_handles("/api/challenge/item_list/", params)
        if len(handles) >= limit:
            return _clean_handles(handles)[:limit]
        handles += self._html_handles(f"https://www.tiktok.com/tag/{tag}")
        if len(handles) >= limit:
            return _clean_handles(handles)[:limit]
        handles += self._html_handles(f"https://m.tiktok.com/tag/{tag}")
        return _clean_handles(handles)[:limit]

    def fetch_search_handles(self, keyword: str, limit: int = 40) -> list[str]:
        handles: list[str] = []
        params = self._sign_base_params()
        params.update({"keyword": keyword, "count": str(limit), "cursor": "0", "search_channel": "aweme_video_web"})
        handles += self._api_handles("/api/search/item/full/", params)
        if len(handles) >= limit:
            return _clean_handles(handles)[:limit]
        handles += self._html_handles(f"https://www.tiktok.com/search?q={keyword}")
        return _clean_handles(handles)[:limit]

    def _api_handles(self, path: str, params: dict) -> list[str]:
        url = self._signed_url(path, params)
        try:
            with self._client() as client:
                resp = client.get(url, headers={"Referer": "https://www.tiktok.com/"})
                if resp.status_code != 200 or not resp.text.strip():
                    logger.info("Signed API %s rejected (empty/%d)", path, resp.status_code)
                    return []
                data = resp.json()
        except Exception as e:
            logger.warning("Signed API %s failed: %s", path, e)
            return []
        if data.get("statusCode") not in (0, None):
            return []
        items = data.get("itemList") or data.get("item_list") or []
        handles = []
        for item in items:
            author = item.get("author") or {}
            unique_id = author.get("uniqueId") or author.get("unique_id") or ""
            if unique_id:
                handles.append(unique_id)
        return handles

    def _html_handles(self, url: str) -> list[str]:
        try:
            with self._client() as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return []
                html = resp.text
        except Exception as e:
            logger.warning("TikTok HTML harvest failed for %s: %s", url, e)
            return []
        handles = HANDLE_PATTERN.findall(html) + UNIQUE_ID_PATTERN.findall(html)
        return handles