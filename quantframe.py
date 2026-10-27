"""Sends items to Quantframe (https://github.com/Kenya-DK/quantframe-react) through its local HTTP server.

In Quantframe: Settings > Advanced > HTTP Server > enable (default address 127.0.0.1, port 4808). Its routes (POST, JSON):
    /stock_item  {"raw": <market slug | name>, "quantity": n, "sub_type": {"rank": r}}   -> its stock (Live Scraper)
    /wish_list   the same body                                                         -> its wish list
Without a "bought" price no purchase is recorded. Only addresses on this computer are accepted: the items are
never sent anywhere else. Rivens are NOT sent (see README).
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from config import APP_DIR, CFG

SENT_FILE = APP_DIR / "quantframe_sent.json"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class QuantframeError(Exception):
    pass


def base_url() -> str:
    url = (CFG["quantframe_url"] or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    p = urllib.parse.urlparse(url)
    if p.scheme != "http" or p.hostname not in LOOPBACK or not p.port:
        raise QuantframeError("the address must be http://127.0.0.1:PORT (this computer only)")
    return f"http://{p.hostname if p.hostname != '::1' else '[::1]'}:{p.port}"


def item_payload(slug: str, quantity: int, rank=None) -> dict:
    body = {"raw": slug, "quantity": int(quantity)}
    if rank is not None:
        body["sub_type"] = {"rank": int(rank)}
    return body


def post(path: str, payload: dict, timeout: float = 8.0) -> str:
    """POSTs the JSON; returns Quantframe's answer text. Raises QuantframeError with a readable reason."""
    url = base_url() + path
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(200_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read(2000).decode("utf-8", errors="replace")
        raise QuantframeError(f"HTTP {e.code}: {_short(body)}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise QuantframeError(f"cannot reach Quantframe at {url} ({type(e).__name__}): is it running, with the "
                              f"HTTP server enabled in its settings?")


def _short(body: str) -> str:
    try:
        d = json.loads(body)
        if isinstance(d, dict):
            msg = d.get("message") or d.get("error") or d.get("msg")
            if msg:
                return str(msg)[:240]
    except ValueError:
        pass
    return " ".join(body.split())[:240]


def send_stock(slug, quantity, rank=None) -> str:
    return post("/stock_item", item_payload(slug, quantity, rank))


def send_wish(slug, quantity, rank=None) -> str:
    return post("/wish_list", item_payload(slug, quantity, rank))


# ---------- what was already sent (sending twice would add the quantity twice) ----------
def _key(kind, slug, rank):
    return f"{kind}|{slug}|{'' if rank is None else rank}"


def load_sent() -> dict:
    try:
        d = json.loads(SENT_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def mark_sent(kind, slug, rank, quantity):
    d = load_sent()
    k = _key(kind, slug, rank)
    d[k] = {"qty": int(d.get(k, {}).get("qty", 0)) + int(quantity), "t": int(time.time())}
    try:
        SENT_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def sent_before(kind, slug, rank):
    return load_sent().get(_key(kind, slug, rank))
