#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# WiFi Core Logic – adapted from original script
# Developed by LaMinPaing

import os
import re
import sys
import time
import base64
import urllib.parse
import hashlib
import asyncio

try:
    import requests
except ImportError:
    requests = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from Crypto.Random import get_random_bytes
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False


# ─── WifiSetup ────────────────────────────────────────────────────────────────

class WifiSetup:
    def __init__(self, log_cb=None):
        self.baseurl = "http://10.44.77.240:2060"
        self.username_get_url = self.baseurl + "/username_get"
        self.online_info_url  = self.baseurl + "/user/online_info"
        self.logout_url       = self.baseurl + "/user/logout"
        self.enc_key          = "RjYkhwzx$2018!"
        self._log = log_cb or (lambda msg, lvl='info': print(msg))

    def run_full_setup(self):
        self._log("Ruijie WiFi setup starting…", "info")

        status = self.unbind()
        if not status:
            self._log("Warning: could not unbind old session (continuing).", "warn")
        else:
            self._log("Old session unbound ✓ – waiting 6 s…", "success")
            time.sleep(6)

        self._log("Fetching gateway IP and session URL…", "info")
        try:
            localhost = requests.get("http://192.168.0.1", timeout=10).url
            ip = re.search(r'gw_address=(.*?)&', localhost).group(1)

            headers = {
                'authority':         'portal-as.ruijienetworks.com',
                'accept':            'text/html,application/xhtml+xml,application/xml;q=0.9,'
                                     'image/avif,image/webp,image/apng,*/*;q=0.8,'
                                     'application/signed-exchange;v=b3;q=0.7',
                'accept-language':   'en-US,en;q=0.9',
                'referer':           localhost,
                'user-agent':        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                                     '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            }
            req  = requests.get(localhost, headers=headers).text
            path = re.search(r"href='(.*?)'</script>", req).group(1)
            session_url = "https://portal-as.ruijienetworks.com" + path

            # Cache to files so app can reload without setup
            try:
                data_dir = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(data_dir, ".session_url"), "w") as f:
                    f.write(session_url)
                with open(os.path.join(data_dir, ".ip"), "w") as f:
                    f.write(ip)
            except Exception:
                pass

            self._log(f"Setup complete – gateway: {ip}", "success")
            return ip, session_url

        except Exception as err:
            self._log(f"Setup error: {err}", "error")
            # Try reading cached values
            return self._load_cached()

    def _load_cached(self):
        try:
            data_dir = os.path.dirname(os.path.abspath(__file__))
            ip  = open(os.path.join(data_dir, ".ip")).read().strip()
            url = open(os.path.join(data_dir, ".session_url")).read().strip()
            if ip and url:
                self._log("Loaded cached gateway info.", "warn")
                return ip, url
        except Exception:
            pass
        return None, None

    # ── Unbind helpers ────────────────────────────────────────────────────────

    def unbind(self):
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
        repmac = info["mac"].replace(":", "")
        repmac = [repmac[i:i+4] for i in range(0, len(repmac), 4)]
        return {
            "ip":     info["ip"],
            "mac":    info["mac"],
            "ip_req": info["ip"],
            "mac_req": ".".join(repmac),
        }

    def _get_data(self):
        try:
            return requests.get(self.baseurl, timeout=5).text
        except Exception:
            return None

    def _extract_chap(self, data):
        m = re.search(r"chap_id=([^&]+)&chap_challenge=([^']+)", data)
        return {"chap_id": m.group(1), "chap_challenge": m.group(2)} if m else None

    def _encrypt_cryptojs(self, auth, enc_key):
        if not CRYPTO_OK:
            return ""
        salt     = get_random_bytes(8)
        key_iv   = b''
        prev     = b''
        while len(key_iv) < 48:
            prev    = hashlib.md5(prev + enc_key.encode() + salt).digest()
            key_iv += prev
        key    = key_iv[:32]
        iv     = key_iv[32:48]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct     = cipher.encrypt(pad(auth.encode(), AES.block_size))
        return base64.b64encode(b"Salted__" + salt + ct).decode()

    def _get_auth(self, username):
        data = self._get_data()
        if not data:
            return None
        chaps = self._extract_chap(data)
        if not chaps:
            return None
        chap_id  = urllib.parse.unquote(chaps["chap_id"])
        chap_chal = urllib.parse.unquote(chaps["chap_challenge"])
        return self._encrypt_cryptojs(chap_id + chap_chal + username, self.enc_key)

    def _logout(self, data, username):
        auth = self._get_auth(username)
        if not auth:
            return False
        payload = (
            f"ip={data['ip']}&mac={data['mac']}"
            f"&ip_req={data['ip_req']}&mac_req={data['mac_req']}&auth={auth}"
        )
        try:
            r = requests.post(self.logout_url, data=payload, timeout=5).json()
            return bool(r.get("success"))
        except Exception:
            return False


# ─── Async helpers (called from main.py) ──────────────────────────────────────

async def get_session_id(session, session_url: str, log_cb=None):
    log = log_cb or (lambda m, l='info': None)
    headers = {
        'accept':            'text/html,application/xhtml+xml,application/xml;q=0.9,'
                             'image/avif,image/webp,image/apng,*/*;q=0.8,'
                             'application/signed-exchange;v=b3;q=0.7',
        'accept-language':   'en-US,en;q=0.9',
        'user-agent':        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }
    try:
        async with session.get(session_url, headers=headers, allow_redirects=True) as resp:
            final_url = str(resp.url)
            m = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", final_url)
            if m:
                return m.group(1)
            log("Could not extract session ID from portal URL.", "error")
            return None
    except Exception as e:
        log(f"Session ID fetch error: {e}", "error")
        return None


async def _check_captcha(session, session_id: str, log_cb=None):
    """Returns 'SKIP' if no captcha, or the verified code, or None on failure."""
    log = log_cb or (lambda m, l='info': None)
    url = (
        f"https://portal-as.ruijienetworks.com/api/auth/captcha/image"
        f"?sessionId={session_id}&_t={int(time.time()*1000)}"
    )
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14)'}
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status in (404, 400):
                log("No CAPTCHA required ✓", "info")
                return "SKIP"
            if resp.status != 200:
                log(f"CAPTCHA endpoint returned {resp.status} – skipping.", "warn")
                return "SKIP"
            # On Android the app cannot display a CAPTCHA image easily;
            # we skip and let the server decide.
            log("CAPTCHA detected – attempting to skip…", "warn")
            return "SKIP"
    except Exception as e:
        log(f"CAPTCHA check error: {e}", "warn")
        return "SKIP"


async def login_voucher(session, session_id: str, voucher: str, log_cb=None):
    log = log_cb or (lambda m, l='info': None)
    captcha = await _check_captcha(session, session_id, log)

    api_url = base64.b64decode(
        b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM='
    ).decode()

    data = {
        "accessCode": voucher,
        "sessionId":  session_id,
        "apiVersion": 1,
    }
    if captcha and captcha != "SKIP":
        data["captcha"] = captcha

    headers = {
        "authority":         "portal-as.ruijienetworks.com",
        "accept":            "*/*",
        "accept-language":   "en-US,en;q=0.9",
        "content-type":      "application/json",
        "origin":            "https://portal-as.ruijienetworks.com",
        "referer":           (
            f"https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html"
            f"?RES=./../expand/res/mrlev58jlgslg49ervu&IS_EG=0&sessionId={session_id}"
        ),
        "sec-ch-ua-mobile":  "?1",
        "sec-ch-ua-platform": '"Android"',
        "user-agent":        "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    }
    try:
        async with session.post(api_url, json=data, headers=headers) as resp:
            text = await resp.text()
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


async def _one_click(session, token: str, log_cb=None):
    log = log_cb or (lambda m, l='info': None)
    headers = {
        'authority':         'portal-as.ruijienetworks.com',
        'accept':            '*/*',
        'accept-language':   'en-US,en;q=0.9,my;q=0.8',
        'content-type':      'application/json',
        'origin':            'https://portal-as.ruijienetworks.com',
        'sec-ch-ua-mobile':  '?1',
        'sec-ch-ua-platform': '"Android"',
        'user-agent':        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    }
    json_data = {'phoneNumber': '', 'sessionId': token}
    try:
        async with session.post(
            'https://portal-as.ruijienetworks.com/api/auth/direct/',
            params={'lang': 'en_US'},
            headers=headers,
            json=json_data,
        ) as resp:
            text  = await resp.text()
            m = re.search(r'token=(.*?)&', text)
            return m.group(1) if m else None
    except Exception as e:
        log(f"One-click error: {e}", "warn")
        return None


async def auth_gateway(session, voucher: str, ip: str, token: str,
                       session_url: str, log_cb=None, final=False):
    log = log_cb or (lambda m, l='info': None)
    headers = {
        'Accept':                  '*/*',
        'Accept-Language':         'en-US,en;q=0.9,my;q=0.8',
        'Connection':              'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent':              'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                                   '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    }
    params = {'token': token, 'phoneNumber': ''}
    try:
        async with session.get(
            f'http://{ip}:2060/wifidog/auth',
            params=params,
            headers=headers,
            allow_redirects=True,
        ) as resp:
            url = str(resp.url)
            if any(kw in url for kw in ("success", "www.baidu.com", "www.ruijie.com")):
                log("Gateway authenticated successfully ✓", "success")
                if not final:
                    await _auth_as_unlimited(session, voucher, ip, session_url, log)
            else:
                log(f"Gateway auth failed: {url[:80]}", "error")
    except Exception as e:
        log(f"Gateway error: {e}", "error")


async def _auth_as_unlimited(session, voucher: str, ip: str, session_url: str, log_cb=None):
    log = log_cb or (lambda m, l='info': None)
    for attempt in range(1, 4):
        log(f"Unlimited upgrade attempt {attempt}/3…", "info")
        session_id = await get_session_id(session, session_url, log)
        if not session_id:
            continue
        token = await login_voucher(session, session_id, voucher, log)
        if not token:
            log(f"Attempt {attempt}: login failed.", "warn")
            continue
        new_token = await _one_click(session, token, log)
        if new_token:
            await auth_gateway(session, voucher, ip, new_token, session_url, log, final=True)
            log("Switched to unlimited session ✓", "success")
            return
        log(f"Attempt {attempt}: one-click failed.", "warn")
    log("Could not upgrade to unlimited after 3 attempts.", "error")
