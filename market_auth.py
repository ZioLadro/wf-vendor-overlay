"""warframe.market account: sign in and place sell orders.

Uses the v1 REST API (the same one already used for volumes):
  POST /v1/auth/signin          body {"email", "password", "auth_type": "header"}  -> JWT in the
                                 "Authorization" response header
  POST /v1/profile/orders       body {"item_id", "order_type", "platinum", "quantity", "visible", "rank"}
                                 header "Authorization: JWT <token>"
Only the session token is stored (market_session.json), never the password. "Sign out" deletes it.
NB: written from the public client libraries' behaviour and not testable against the live site from the
development sandbox: failures are reported with the HTTP status and the server's message.
"""
import json
import os
import time

import requests

from config import APP_DIR
from market import HEADERS, V1

SESSION_FILE = APP_DIR / "market_session.json"


class MarketError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _detail(r) -> str:
    """Server's error message, short."""
    try:
        j = r.json()
        err = j.get("error") or j.get("errors") or j
        text = json.dumps(err, ensure_ascii=False)
    except Exception:
        text = (r.text or "")[:200]
    return text[:300]


class MarketAccount:
    def __init__(self, market):
        self.market = market
        self.token = None
        self.user = None
        self._load()

    # ---------- session ----------
    @property
    def logged_in(self) -> bool:
        return bool(self.token)

    def _load(self):
        try:
            d = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            self.token, self.user = d.get("token"), d.get("user")
        except Exception:
            self.token = self.user = None

    def _save(self):
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"token": self.token, "user": self.user, "saved": int(time.time())}),
                       encoding="utf-8")
        os.replace(tmp, SESSION_FILE)

    def logout(self):
        self.token = self.user = None
        try:
            SESSION_FILE.unlink()
        except OSError:
            pass

    def _headers(self, authed: bool) -> dict:
        h = dict(HEADERS, **{"Content-Type": "application/json"})
        h["Authorization"] = f"JWT {self.token}" if authed else "JWT"
        return h

    # ---------- sign in ----------
    def login(self, email: str, password: str) -> str:
        """Signs in and keeps the session token. Returns the user name. Raises MarketError."""
        self.market.throttle()
        try:
            r = requests.post(V1 + "/auth/signin", headers=self._headers(False), timeout=15,
                              json={"email": email, "password": password, "auth_type": "header"})
        except requests.RequestException as e:
            raise MarketError(f"network error: {type(e).__name__}")
        if r.status_code != 200:
            raise MarketError(_detail(r) or f"HTTP {r.status_code}", r.status_code)
        auth = r.headers.get("Authorization", "")
        token = auth.split(" ", 1)[1] if auth.upper().startswith("JWT ") else auth
        if not token:
            try:
                token = r.json()["payload"]["user"].get("token", "")
            except Exception:
                token = ""
        if not token:
            raise MarketError("sign-in worked but no session token was returned")
        try:
            user = r.json()["payload"]["user"].get("ingame_name") or email
        except Exception:
            user = email
        self.token, self.user = token, user
        self._save()
        return user

    # ---------- orders ----------
    def order_request(self, item_id: str, platinum: int, quantity: int, rank=None, visible=True,
                      order_type: str = "sell") -> dict:
        """The request that create_order would send (shown to the user before confirming)."""
        body = {"item_id": item_id, "order_type": order_type, "platinum": int(platinum),
                "quantity": int(quantity), "visible": bool(visible)}
        if rank is not None:
            body["rank"] = int(rank)
        return {"method": "POST", "url": V1 + "/profile/orders", "body": body}

    def create_order(self, item_id: str, platinum: int, quantity: int, rank=None, visible=True):
        """Places a sell order. Returns the order id (None if the server did not say). Raises MarketError."""
        if not self.logged_in:
            raise MarketError("not signed in", 401)
        if platinum < 1 or quantity < 1 or not item_id:
            raise MarketError("invalid order")
        req = self.order_request(item_id, platinum, quantity, rank, visible)
        self.market.throttle()
        try:
            r = requests.post(req["url"], headers=self._headers(True), json=req["body"], timeout=15)
        except requests.RequestException as e:
            raise MarketError(f"network error: {type(e).__name__}")
        if r.status_code == 401:
            self.logout()                            # expired / invalid token
            raise MarketError("session expired: sign in again", 401)
        if r.status_code not in (200, 201):
            raise MarketError(_detail(r) or f"HTTP {r.status_code}", r.status_code)
        try:
            return r.json()["payload"]["order"]["id"]
        except Exception:
            return None
