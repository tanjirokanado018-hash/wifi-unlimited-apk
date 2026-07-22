#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# WiFi Core Logic – requests-only (no aiohttp, no C extensions)
# Developed by LaMinPaing

import os
import re
import time
import base64
import urllib.parse
import urllib.request
import urllib.error
import hashlib
import json

try:
    import requests
    from requests.exceptions import RequestException
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from Crypto.Random import get_random_bytes
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False


def _get(url, params=None, headers=None, timeout=10, session=None):
    req = session or requests
    return req.get(url, params=params, headers=headers, timeout=timeout,
                   allow_redirects=True)


def _post(url, data=None, json_data=None, headers=None, timeout=10, session=None):
    req = session or requests
    if json_data is not None:
        return req.post(url, json=json_data, headers=headers, timeout=timeout)
    return req.post(url, data=data, headers=headers, timeout=timeout)


# ─── WifiSetup ────────────────────────────────────────────────────────────────

class WifiSetup:
    def __init__(self, log_cb=None):
        self.baseurl            = "http://10.44.77.240:2060"
        self.username_get_url   = self.baseurl + "/username_get"
        self.online_info_url    = self.baseurl + "/user/online_info"
        self.logout_url         = self.baseurl + "/user/logout"
        self.enc_key            = "RjYkhwzx$2018!"
        self._log = log_cb or (lambda msg, lvl='info': print(msg))

    def run_full_setup(self):
        self._log("Ruijie WiFi setup starting…", "info")

        status = self._unbind()
        if not status:
            self._log("Could not unbind old session (continuing).", "warn")
        else:
            self._log("Old session unbound ✓ – waiting 6 s…", "success")
            time.sleep(6)

        self._log("Fetching gateway IP and session URL…", "info")
        try:
            sess = requests.Session()
            sess.headers.update({'User-Agent':
                'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'})

            r0  = sess.get("http://192.168.0.1", timeout=10)
            localhost = r0.url
            ip  = re.search(r'gw_address=(.*?)&', localhost).group(1)

            r1   = sess.get(localhost, timeout=10)
            path = re.search(r"href='(.*?)'</script>", r1.text).group(1)
            session_url = "https://portal-as.ruijienetworks.com" + path

            self._save_cache(ip, session_url)
            self._log(f"Setup complete – gateway: {ip}", "success")
            return ip, session_url

        except Exception as err:
            self._log(f"Setup error: {err}", "error")
            return self._load_cache()

    def _save_cache(self, ip, session_url):
        try:
            d = os.path.dirname(os.path.abspath(__file__))
            open(os.path.join(d, ".ip"), "w").write(ip)
            open(os.path.join(d, ".session_url"), "w").write(session_url)
        except Exception:
            pass

    def _load_cache(self):
        try:
            d   = os.path.dirname(os.path.abspath(__file__))
            ip  = open(os.path.join(d, ".ip")).read().strip()
            url = open(os.path.join(d, ".session_url")).read().strip()
            if ip and url:
                self._log("Loaded cached gateway info.", "warn")
                return ip, url
        except Exception:
            pass
        return None, None

    # ── Unbind helpers ────────────────────────────────────────────────────────

    def _unbind(self):
        username = self._username_get()
        if not username:
            return False
        info = self._get_online_info(username)
        if not info:
            return False
        data = self._arrange_data(info)
        return self._logout(data, username)

    def _username_get(self):
        try:
            return requests.get(self.username_get_url, timeout=5).json().get("username")
        except Exception:
            return None

    def _get_online_info(self, username):
        try:
            r = requests.get(self.online_info_url,
                             params={"username": username, "usertype": "wifidog"},
                             timeout=5).json()
            return r["data"]["list"][0]
        except Exception:
            return None

    def _arrange_data(self, info):
        mac  = info["mac"].replace(":", "")
        segs = [mac[i:i+4] for i in range(0, len(mac), 4)]
        return {"ip": info["ip"], "mac": info["mac"],
                "ip_req": info["ip"], "mac_req": ".".join(segs)}

    def _get_data(self):
        try:
            return requests.get(self.baseurl, timeout=5).text
        except Exception:
            return None

    def _extract_chap(self, data):
        m = re.search(r"chap_id=([^&]+)&chap_challenge=([^']+)", data)
        return {"chap_id": m.group(1), "chap_challenge": m.group(2)} if m else None

    def _encrypt_cryptojs(self, auth, key):
        if not CRYPTO_OK:
            return ""
        salt   = get_random_bytes(8)
        kiv    = b''
        prev   = b''
        while len(kiv) < 48:
            prev = hashlib.md5(prev + key.encode() + salt).digest()
            kiv += prev
        cipher = AES.new(kiv[:32], AES.MODE_CBC, kiv[32:48])
        ct     = cipher.encrypt(pad(auth.encode(), AES.block_size))
        return base64.b64encode(b"Salted__" + salt + ct).decode()

    def _get_auth(self, username):
        data = self._get_data()
        if not data:
            return None
        chaps = self._extract_chap(data)
        if not chaps:
            return None
        chap_id   = urllib.parse.unquote(chaps["chap_id"])
        chap_chal = urllib.parse.unquote(chaps["chap_challenge"])
        return self._encrypt_cryptojs(chap_id + chap_chal + username, self.enc_key)

    def _logout(self, data, username):
        auth = self._get_auth(username)
        if not auth:
            return False
        payload = (f"ip={data['ip']}&mac={data['mac']}"
                   f"&ip_req={data['ip_req']}&mac_req={data['mac_req']}&auth={auth}")
        try:
            r = requests.post(self.logout_url, data=payload, timeout=5).json()
            return bool(r.get("success"))
        except Exception:
            return False


# ─── Portal helpers (synchronous, run in threads) ─────────────────────────────

PORTAL = "https://portal-as.ruijienetworks.com"
UA_MOB  = ("Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36")
UA_DESK = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0")


def get_session_id(session_url: str, log_cb=None) -> str | None:
    log = log_cb or (lambda m, l='info': None)
    sess = requests.Session()
    sess.headers.update({'User-Agent': UA_DESK,
                         'Accept': ('text/html,application/xhtml+xml,application/xml;'
                                    'q=0.9,*/*;q=0.8'),
                         'Accept-Language': 'en-US,en;q=0.9'})
    try:
        r = sess.get(session_url, timeout=15, allow_redirects=True)
        m = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", r.url)
        if m:
            return m.group(1)
        log("Could not extract sessionId from portal URL.", "error")
        return None
    except Exception as e:
        log(f"Session ID fetch error: {e}", "error")
        return None


def _check_captcha(session_id: str, log_cb=None) -> str:
    log = log_cb or (lambda m, l='info': None)
    url = (f"{PORTAL}/api/auth/captcha/image"
           f"?sessionId={session_id}&_t={int(time.time()*1000)}")
    try:
        r = requests.get(url, headers={'User-Agent': UA_MOB}, timeout=8)
        if r.status_code in (404, 400):
            log("No CAPTCHA required ✓", "info")
            return "SKIP"
        log("CAPTCHA detected – skipping (mobile auto-mode).", "warn")
        return "SKIP"
    except Exception:
        return "SKIP"


def login_voucher(session_id: str, voucher: str, log_cb=None) -> str | None:
    log = log_cb or (lambda m, l='info': None)
    _check_captcha(session_id, log)

    api_url = base64.b64decode(
        b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM='
    ).decode()

    headers = {
        "Accept":            "*/*",
        "Accept-Language":   "en-US,en;q=0.9",
        "Content-Type":      "application/json",
        "Origin":            PORTAL,
        "Referer":           (f"{PORTAL}/download/static/maccauth/src/index.html"
                              f"?RES=./../expand/res/mrlev58jlgslg49ervu"
                              f"&IS_EG=0&sessionId={session_id}"),
        "User-Agent":        UA_MOB,
    }
    payload = {"accessCode": voucher, "sessionId": session_id, "apiVersion": 1}
    try:
        r    = requests.post(api_url, json=payload, headers=headers, timeout=15)
        text = r.text
        if any(kw in text for kw in ("Authentication failed", "expired", "Expired")):
            log("Voucher expired or incorrect.", "error")
            return None
        m = re.search(r'token=(.*?)&', text)
        if m:
            return m.group(1)
        log(f"Unexpected portal response: {text[:120]}", "error")
        return None
    except Exception as e:
        log(f"Login error: {e}", "error")
        return None


def one_click(token: str, log_cb=None) -> str | None:
    log = log_cb or (lambda m, l='info': None)
    headers = {
        "Accept":            "*/*",
        "Accept-Language":   "en-US,en;q=0.9,my;q=0.8",
        "Content-Type":      "application/json",
        "Origin":            PORTAL,
        "User-Agent":        UA_MOB,
    }
    try:
        r = requests.post(f"{PORTAL}/api/auth/direct/",
                          params={"lang": "en_US"},
                          json={"phoneNumber": "", "sessionId": token},
                          headers=headers, timeout=15)
        m = re.search(r'token=(.*?)&', r.text)
        return m.group(1) if m else None
    except Exception as e:
        log(f"One-click error: {e}", "warn")
        return None


def auth_gateway(voucher: str, ip: str, token: str, session_url: str,
                 log_cb=None, final=False) -> bool:
    log = log_cb or (lambda m, l='info': None)
    headers = {
        "Accept":                    "*/*",
        "Accept-Language":           "en-US,en;q=0.9,my;q=0.8",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent":                UA_MOB,
    }
    try:
        r = requests.get(f"http://{ip}:2060/wifidog/auth",
                         params={"token": token, "phoneNumber": ""},
                         headers=headers, timeout=15, allow_redirects=True)
        url = r.url
        if any(kw in url for kw in ("success", "www.baidu.com", "www.ruijie.com")):
            log("Gateway authenticated successfully ✓", "success")
            if not final:
                _auth_as_unlimited(voucher, ip, session_url, log)
            return True
        else:
            log(f"Gateway auth failed: {url[:80]}", "error")
            return False
    except Exception as e:
        log(f"Gateway error: {e}", "error")
        return False


def _auth_as_unlimited(voucher: str, ip: str, session_url: str, log_cb=None):
    log = log_cb or (lambda m, l='info': None)
    for attempt in range(1, 4):
        log(f"Unlimited upgrade attempt {attempt}/3…", "info")
        sid = get_session_id(session_url, log)
        if not sid:
            continue
        token = login_voucher(sid, voucher, log)
        if not token:
            log(f"Attempt {attempt}: login failed.", "warn")
            continue
        new_token = one_click(token, log)
        if new_token:
            ok = auth_gateway(voucher, ip, new_token, session_url, log, final=True)
            if ok:
                log("Switched to unlimited session ✓", "success")
                return
        log(f"Attempt {attempt}: one-click failed.", "warn")
    log("Could not upgrade to unlimited after 3 attempts.", "error")
