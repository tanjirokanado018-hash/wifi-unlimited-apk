#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# WiFi Unlimited Tool – Kivy App (requests-only, no aiohttp)
# Developed by LaMinPaing

import os
import time
import threading

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.animation import Animation
from kivy.core.window import Window


# ─── Colour Palette ────────────────────────────────────────────────────────────
BG      = (0.05, 0.07, 0.12, 1)
CARD    = (0.08, 0.11, 0.18, 1)
CARD2   = (0.10, 0.14, 0.22, 1)
ACCENT  = (0.18, 0.62, 1.00, 1)
SUCCESS = (0.18, 0.85, 0.55, 1)
DANGER  = (1.00, 0.35, 0.35, 1)
WARN    = (1.00, 0.78, 0.20, 1)
TEXT    = (0.90, 0.93, 1.00, 1)
SUBTEXT = (0.50, 0.58, 0.72, 1)
BORDER  = (0.18, 0.26, 0.42, 1)


# ─── Helpers ───────────────────────────────────────────────────────────────────
class Card(BoxLayout):
    def __init__(self, radius=18, bg_color=None, **kw):
        super().__init__(**kw)
        self._r  = radius
        self._bg = bg_color or CARD
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self._r])


class PulseDot(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.color = list(SUBTEXT)
        self.size_hint = (None, None)
        self.size = (dp(12), dp(12))
        self._alpha = 1.0
        self._dir   = -1
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_interval(self._pulse, 0.03)

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self.color[:3], self._alpha)
            Ellipse(pos=self.pos, size=self.size)

    def _pulse(self, dt):
        self._alpha += self._dir * 0.025
        if self._alpha <= 0.3:
            self._dir = 1
        elif self._alpha >= 1.0:
            self._dir = -1
        self._draw()


class WiFiIcon(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._bars = 0
        self.size_hint = (None, None)
        self.size = (dp(60), dp(48))
        self.bind(pos=self._draw, size=self._draw)

    def set_bars(self, n):
        self._bars = n
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        cx = self.x + self.width / 2
        by = self.y + dp(2)
        with self.canvas:
            Color(*ACCENT if self._bars > 0 else SUBTEXT)
            Ellipse(pos=(cx - dp(4), by), size=(dp(8), dp(8)))
            for i, (w, h) in enumerate([(dp(18), dp(12)),
                                        (dp(30), dp(20)),
                                        (dp(42), dp(28))]):
                Color(*ACCENT if i < self._bars else SUBTEXT)
                Line(ellipse=(cx - w/2, by, w, h), width=dp(2.2))


class GlowButton(Button):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.background_normal = ''
        self.background_color  = (0, 0, 0, 0)
        self.color             = (1, 1, 1, 1)
        self.font_size         = sp(16)
        self.bold              = True
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*(SUBTEXT if self.disabled else ACCENT))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])

    def on_press(self):
        Animation(opacity=0.5, duration=0.07).start(self)
        Animation(opacity=0.5, duration=0.07).start(self)

    def on_release(self):
        Animation(opacity=1, duration=0.07).start(self)


class LogConsole(ScrollView):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.do_scroll_x = False
        self._lbl = Label(
            text='',
            markup=True,
            size_hint_y=None,
            valign='top',
            halign='left',
            font_size=sp(12),
            color=TEXT,
            padding=(dp(10), dp(6)),
        )
        self._lbl.bind(texture_size=self._on_tex)
        self.add_widget(self._lbl)

    def _on_tex(self, lbl, ts):
        lbl.height     = ts[1]
        lbl.text_size  = (lbl.width, None)

    def append(self, msg, color='#C8D8FF'):
        ts   = time.strftime('%H:%M:%S')
        self._lbl.text += f'[color={color}][b]{ts}[/b]  {msg}[/color]\n'
        Clock.schedule_once(lambda *_: self.scroll_to(self._lbl), 0.05)

    def clear_log(self):
        self._lbl.text = ''


# ─── Home Screen ───────────────────────────────────────────────────────────────
class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._busy = False
        self._ip   = None
        self._url  = None
        self._build()

    def _build(self):
        root = FloatLayout()
        with root.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda w, *_: setattr(self._bg, 'pos', w.pos),
                  size=lambda w, *_: setattr(self._bg, 'size', w.size))

        main = BoxLayout(orientation='vertical',
                         padding=(dp(18), dp(32), dp(18), dp(12)),
                         spacing=dp(12))

        # ── Header ──────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(10))

        self._icon = WiFiIcon()
        hdr.add_widget(self._icon)

        titles = BoxLayout(orientation='vertical', spacing=dp(1))
        titles.add_widget(Label(text='[b]WiFi Unlimited[/b]', markup=True,
                                font_size=sp(21), color=TEXT,
                                halign='left', valign='middle', size_hint_y=0.6))
        titles.add_widget(Label(
            text='[color=#6080A8]Ruijie Portal Authenticator[/color]',
            markup=True, font_size=sp(11.5),
            halign='left', valign='top', size_hint_y=0.4))
        hdr.add_widget(titles)

        pill = BoxLayout(orientation='horizontal',
                         size_hint=(None, None), size=(dp(100), dp(28)),
                         spacing=dp(5), padding=(dp(8), 0))
        with pill.canvas.before:
            Color(*CARD2)
            self._pill_bg = RoundedRectangle(pos=pill.pos, size=pill.size,
                                             radius=[dp(14)])
        pill.bind(pos=self._upd_pill, size=self._upd_pill)

        self._dot = PulseDot()
        pill.add_widget(self._dot)
        self._status_lbl = Label(text='Idle', font_size=sp(11.5),
                                 color=list(SUBTEXT), halign='left', valign='middle')
        pill.add_widget(self._status_lbl)
        hdr.add_widget(pill)
        main.add_widget(hdr)

        # ── Voucher Card ────────────────────────────────────────────────────
        vc = Card(orientation='vertical', padding=dp(16), spacing=dp(10),
                  size_hint_y=None, height=dp(118))
        vc.add_widget(Label(text='[b]Voucher Code[/b]', markup=True,
                            font_size=sp(12.5), color=list(SUBTEXT),
                            halign='left', size_hint_y=None, height=dp(20)))

        ti_wrap = BoxLayout(size_hint_y=None, height=dp(50))
        with ti_wrap.canvas.before:
            Color(*BORDER)
            self._ti_bg = RoundedRectangle(pos=ti_wrap.pos, size=ti_wrap.size,
                                           radius=[dp(11)])
        ti_wrap.bind(pos=lambda w, *_: setattr(self._ti_bg, 'pos', w.pos),
                     size=lambda w, *_: setattr(self._ti_bg, 'size', w.size))
        self._voucher = TextInput(
            hint_text='  Enter voucher code…',
            font_size=sp(17),
            background_color=(0, 0, 0, 0),
            foreground_color=list(TEXT),
            hint_text_color=list(SUBTEXT),
            cursor_color=list(ACCENT),
            multiline=False,
            padding=(dp(12), dp(10)),
        )
        ti_wrap.add_widget(self._voucher)
        vc.add_widget(ti_wrap)
        vc.add_widget(Label(
            text='[color=#607898]Input your Ruijie portal voucher code[/color]',
            markup=True, font_size=sp(10.5), halign='left',
            size_hint_y=None, height=dp(16)))
        main.add_widget(vc)

        # ── Buttons ─────────────────────────────────────────────────────────
        btns = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        self._setup_btn   = GlowButton(text='⚙  Setup')
        self._connect_btn = GlowButton(text='⚡  Connect')
        self._setup_btn.bind(on_press=self._on_setup)
        self._connect_btn.bind(on_press=self._on_connect)
        btns.add_widget(self._setup_btn)
        btns.add_widget(self._connect_btn)
        main.add_widget(btns)

        clr = Button(text='Clear Log', font_size=sp(12),
                     background_color=(0, 0, 0, 0), color=list(SUBTEXT),
                     size_hint_y=None, height=dp(28))
        clr.bind(on_press=lambda *_: self._console.clear_log())
        main.add_widget(clr)

        # ── Console ─────────────────────────────────────────────────────────
        cc = Card(radius=12, bg_color=CARD2, orientation='vertical', padding=dp(2))
        self._console = LogConsole()
        cc.add_widget(self._console)
        main.add_widget(cc)

        # ── Footer ──────────────────────────────────────────────────────────
        main.add_widget(Label(
            text='[color=#2A4070]Developed by  [/color][b][color=#3A72CC]LaMinPaing[/color][/b]',
            markup=True, font_size=sp(11), halign='center',
            size_hint_y=None, height=dp(22)))

        root.add_widget(main)
        self.add_widget(root)
        self._console.append('Ready. Tap [b]Setup[/b] first, then [b]Connect[/b].', '#809BC8')

    def _upd_pill(self, w, *_):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*CARD2)
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(14)])

    # ── Helpers ─────────────────────────────────────────────────────────────
    def log(self, msg, level='info'):
        clr = {'info': '#C8D8FF', 'success': '#35D98C',
                'warn': '#F5C842',  'error':   '#FF6060'}.get(level, '#C8D8FF')
        Clock.schedule_once(lambda *_: self._console.append(msg, clr))

    def _set_status(self, text, color):
        def _u(*_):
            self._status_lbl.text  = text
            self._dot.color        = list(color)
        Clock.schedule_once(_u)

    def _set_busy(self, busy):
        def _u(*_):
            for btn in (self._setup_btn, self._connect_btn):
                btn.disabled = busy
                btn.opacity  = 0.45 if busy else 1
                btn._draw()
        Clock.schedule_once(_u)

    # ── Button handlers ──────────────────────────────────────────────────────
    def _on_setup(self, *_):
        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self._set_status('Setting up…', WARN)
        Clock.schedule_once(lambda *_: self._icon.set_bars(1))
        self.log('Starting Ruijie WiFi setup…')
        threading.Thread(target=self._run_setup, daemon=True).start()

    def _on_connect(self, *_):
        if self._busy:
            return
        voucher = self._voucher.text.strip()
        if not voucher:
            self.log('Please enter a voucher code first!', 'warn')
            return
        if not self._ip or not self._url:
            self.log('Run Setup first to get gateway info.', 'warn')
            return
        self._busy = True
        self._set_busy(True)
        self._set_status('Connecting…', ACCENT)
        Clock.schedule_once(lambda *_: self._icon.set_bars(2))
        self.log(f'Connecting with voucher: [b]{voucher}[/b]')
        threading.Thread(target=self._run_connect,
                         args=(voucher, self._ip, self._url),
                         daemon=True).start()

    # ── Background workers ───────────────────────────────────────────────────
    def _run_setup(self):
        try:
            from wifi_core import WifiSetup
            ip, url = WifiSetup(log_cb=self.log).run_full_setup()
            if ip and url:
                self._ip  = ip
                self._url = url
                self.log(f'Gateway IP: [b]{ip}[/b]', 'success')
                self.log('Session URL obtained ✓', 'success')
                self._set_status('Ready', SUCCESS)
                Clock.schedule_once(lambda *_: self._icon.set_bars(3))
            else:
                self.log('Setup failed. Make sure you are on Ruijie WiFi.', 'error')
                self._set_status('Failed', DANGER)
                Clock.schedule_once(lambda *_: self._icon.set_bars(0))
        except Exception as e:
            self.log(f'Setup error: {e}', 'error')
            self._set_status('Error', DANGER)
        finally:
            self._busy = False
            self._set_busy(False)

    def _run_connect(self, voucher, ip, session_url):
        try:
            from wifi_core import get_session_id, login_voucher, auth_gateway

            self.log('Fetching session ID…')
            sid = get_session_id(session_url, self.log)
            if not sid:
                self.log('Failed to get session ID.', 'error')
                self._set_status('Failed', DANGER)
                return
            self.log(f'Session ID: [b]{sid[:16]}…[/b]')

            self.log('Logging in with voucher…')
            token = login_voucher(sid, voucher, self.log)
            if not token:
                self.log('Voucher rejected or expired.', 'error')
                self._set_status('Auth Failed', DANGER)
                Clock.schedule_once(lambda *_: self._icon.set_bars(1))
                return

            self.log('Voucher accepted ✓', 'success')
            Clock.schedule_once(lambda *_: self._icon.set_bars(3))
            ok = auth_gateway(voucher, ip, token, session_url, self.log)
            if ok:
                self._set_status('Connected!', SUCCESS)
            else:
                self._set_status('Auth Failed', DANGER)
        except Exception as e:
            self.log(f'Connection error: {e}', 'error')
            self._set_status('Error', DANGER)
        finally:
            self._busy = False
            self._set_busy(False)


# ─── App ───────────────────────────────────────────────────────────────────────
class WiFiApp(App):
    def build(self):
        Window.clearcolor = BG
        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(HomeScreen(name='home'))
        return sm

    def on_start(self):
        self.title = 'WiFi Unlimited'


if __name__ == '__main__':
    WiFiApp().run()
