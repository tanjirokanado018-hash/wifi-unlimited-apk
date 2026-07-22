#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# WiFi Unlimited Tool - Kivy App
# Developed by LaMinPaing

import os
import re
import sys
import time
import base64
import urllib.parse
import hashlib
import asyncio
import threading
from functools import partial

# --- Kivy imports ---
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.uix.progressbar import ProgressBar


# ─── Colour Palette ────────────────────────────────────────────────────────────
BG        = (0.05, 0.07, 0.12, 1)       # deep navy
CARD      = (0.08, 0.11, 0.18, 1)       # card bg
CARD2     = (0.10, 0.14, 0.22, 1)
ACCENT    = (0.18, 0.62, 1.00, 1)       # electric blue
ACCENT2   = (0.10, 0.45, 0.85, 1)
SUCCESS   = (0.18, 0.85, 0.55, 1)       # green
DANGER    = (1.00, 0.35, 0.35, 1)       # red
WARN      = (1.00, 0.78, 0.20, 1)       # yellow
TEXT      = (0.90, 0.93, 1.00, 1)       # near-white
SUBTEXT   = (0.50, 0.58, 0.72, 1)
BORDER    = (0.18, 0.26, 0.42, 1)


# ─── Rounded Card Widget ───────────────────────────────────────────────────────
class Card(BoxLayout):
    def __init__(self, radius=18, bg_color=None, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        self._bg = bg_color or CARD
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[self._radius])


# ─── Pulse Dot (status indicator) ─────────────────────────────────────────────
class PulseDot(Widget):
    color = (0.18, 0.62, 1.00, 1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._alpha = 1.0
        self.size_hint = (None, None)
        self.size = (dp(14), dp(14))
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_interval(self._pulse, 0.03)
        self._dir = -1
        self._alpha = 1.0

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self.color[:3], self._alpha)
            Ellipse(pos=self.pos, size=self.size)

    def _pulse(self, dt):
        self._alpha += self._dir * 0.025
        if self._alpha <= 0.25:
            self._dir = 1
        elif self._alpha >= 1.0:
            self._dir = -1
        self._draw()


# ─── WiFi Signal Icon (drawn with canvas) ─────────────────────────────────────
class WiFiIcon(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_bars = 0
        self.size_hint = (None, None)
        self.size = (dp(72), dp(56))
        self.bind(pos=self._draw, size=self._draw)

    def set_bars(self, n):
        self._active_bars = n
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        cx = self.x + self.width / 2
        by = self.y + dp(4)
        arcs = [
            (dp(10), dp(10), dp(20), 0.15, 0.85),
            (dp(20), dp(14), dp(26), 0.15, 0.85),
            (dp(32), dp(18), dp(32), 0.15, 0.85),
        ]
        with self.canvas:
            # dot
            Color(*ACCENT) if self._active_bars > 0 else Color(*SUBTEXT)
            Ellipse(pos=(cx - dp(5), by), size=(dp(10), dp(10)))
            # arcs approximated as ellipse segments
            for i, (w, h, radius, a0, a1) in enumerate(arcs):
                active = i < self._active_bars
                Color(*ACCENT if active else SUBTEXT)
                Line(ellipse=(cx - w/2, by, w, h), width=dp(2.5))


# ─── Animated Connect Button ───────────────────────────────────────────────────
class GlowButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.font_size = sp(17)
        self.bold = True
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])

    def on_press(self):
        anim = Animation(opacity=0.6, duration=0.08) + Animation(opacity=1, duration=0.08)
        anim.start(self)

    def set_disabled_look(self, disabled):
        if disabled:
            with self.canvas.before:
                Color(*SUBTEXT)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        else:
            self._draw()


# ─── Log Console ───────────────────────────────────────────────────────────────
class LogConsole(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self._log_label = Label(
            text='',
            markup=True,
            size_hint_y=None,
            valign='top',
            halign='left',
            font_size=sp(12.5),
            color=TEXT,
            padding=(dp(12), dp(8)),
        )
        self._log_label.bind(texture_size=self._on_texture)
        self.add_widget(self._log_label)

    def _on_texture(self, lbl, texture_size):
        lbl.height = texture_size[1]
        lbl.text_size = (lbl.width, None)

    def append(self, msg, color='#E6EAff'):
        ts = time.strftime('%H:%M:%S')
        line = f'[color={color}][b]{ts}[/b]  {msg}[/color]\n'
        self._log_label.text += line
        Clock.schedule_once(lambda *_: self.scroll_to(self._log_label), 0.05)

    def clear(self):
        self._log_label.text = ''


# ─── Home Screen ───────────────────────────────────────────────────────────────
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._running = False
        self._build_ui()

    def _build_ui(self):
        root = FloatLayout()

        # Background
        with root.canvas.before:
            Color(*BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        # Main vertical layout
        main = BoxLayout(
            orientation='vertical',
            padding=(dp(20), dp(36), dp(20), dp(16)),
            spacing=dp(14),
            size_hint=(1, 1),
        )

        # ── Header ──
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(64),
            spacing=dp(12),
        )
        self._wifi_icon = WiFiIcon()
        header.add_widget(self._wifi_icon)

        title_col = BoxLayout(orientation='vertical', spacing=dp(2))
        title_col.add_widget(Label(
            text='[b]WiFi Unlimited[/b]',
            markup=True,
            font_size=sp(22),
            color=TEXT,
            halign='left',
            valign='middle',
            size_hint_y=0.6,
        ))
        title_col.add_widget(Label(
            text='[color=#809BC8]Ruijie Portal Authenticator[/color]',
            markup=True,
            font_size=sp(12),
            halign='left',
            valign='top',
            size_hint_y=0.4,
        ))
        header.add_widget(title_col)

        # Status pill
        self._status_box = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(110), dp(32)),
            spacing=dp(6),
            padding=(dp(10), 0),
        )
        with self._status_box.canvas.before:
            Color(*CARD2)
            RoundedRectangle(pos=self._status_box.pos, size=self._status_box.size, radius=[dp(16)])
        self._status_box.bind(pos=self._upd_status_pill, size=self._upd_status_pill)

        self._pulse = PulseDot()
        self._status_box.add_widget(self._pulse)
        self._status_lbl = Label(
            text='Idle',
            font_size=sp(12),
            color=SUBTEXT,
            halign='left',
            valign='middle',
        )
        self._status_box.add_widget(self._status_lbl)
        header.add_widget(self._status_box)

        main.add_widget(header)

        # ── Voucher Card ──
        voucher_card = Card(
            orientation='vertical',
            padding=dp(18),
            spacing=dp(12),
            size_hint_y=None, height=dp(130),
        )
        voucher_card.add_widget(Label(
            text='[b]Voucher Code[/b]',
            markup=True,
            font_size=sp(13),
            color=SUBTEXT,
            halign='left',
            size_hint_y=None, height=dp(22),
        ))

        ti_wrap = BoxLayout(
            size_hint_y=None, height=dp(52),
            spacing=0,
        )
        with ti_wrap.canvas.before:
            Color(*BORDER)
            self._ti_border = RoundedRectangle(pos=ti_wrap.pos, size=ti_wrap.size, radius=[dp(12)])
        ti_wrap.bind(pos=self._upd_ti, size=self._upd_ti)

        self._voucher_input = TextInput(
            hint_text='  Enter voucher code…',
            font_size=sp(18),
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            hint_text_color=list(SUBTEXT),
            cursor_color=list(ACCENT),
            multiline=False,
            padding=(dp(14), dp(12)),
        )
        ti_wrap.add_widget(self._voucher_input)
        voucher_card.add_widget(ti_wrap)
        voucher_card.add_widget(Label(
            text='[color=#809BC8]Input the Ruijie portal voucher code[/color]',
            markup=True,
            font_size=sp(11),
            halign='left',
            size_hint_y=None, height=dp(18),
        ))
        main.add_widget(voucher_card)

        # ── Action Buttons ──
        btn_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(54),
            spacing=dp(12),
        )
        self._setup_btn = GlowButton(text='⚙  Setup')
        self._setup_btn.bind(on_press=self._on_setup)
        btn_row.add_widget(self._setup_btn)

        self._connect_btn = GlowButton(text='⚡  Connect')
        self._connect_btn.bind(on_press=self._on_connect)
        btn_row.add_widget(self._connect_btn)
        main.add_widget(btn_row)

        self._clear_btn = Button(
            text='Clear Log',
            font_size=sp(13),
            background_color=(0, 0, 0, 0),
            color=list(SUBTEXT),
            size_hint_y=None, height=dp(32),
        )
        self._clear_btn.bind(on_press=lambda *_: self._console.clear())
        main.add_widget(self._clear_btn)

        # ── Console ──
        console_card = Card(
            radius=14,
            bg_color=CARD2,
            orientation='vertical',
            padding=dp(4),
        )
        self._console = LogConsole()
        console_card.add_widget(self._console)
        main.add_widget(console_card)

        # ── Footer ──
        main.add_widget(Label(
            text='[color=#3A5080]Developed by  [/color][b][color=#3A72CC]LaMinPaing[/color][/b]',
            markup=True,
            font_size=sp(11),
            halign='center',
            size_hint_y=None, height=dp(24),
        ))

        root.add_widget(main)
        self.add_widget(root)

        self._console.append('Ready. Press [b]Setup[/b] first, then [b]Connect[/b].', '#809BC8')

    # ── canvas helpers ──
    def _upd_bg(self, w, *_):
        self._bg_rect.pos = w.pos
        self._bg_rect.size = w.size

    def _upd_status_pill(self, w, *_):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*CARD2)
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(16)])

    def _upd_ti(self, w, *_):
        self._ti_border.pos = w.pos
        self._ti_border.size = w.size

    # ── public helpers ──
    def log(self, msg, level='info'):
        color_map = {
            'info':    '#C8D8FF',
            'success': '#35D98C',
            'warn':    '#F5C842',
            'error':   '#FF6060',
        }
        Clock.schedule_once(lambda *_: self._console.append(msg, color_map.get(level, '#C8D8FF')))

    def set_status(self, text, color=None):
        def _upd(*_):
            self._status_lbl.text = text
            self._pulse.color = color or SUBTEXT
        Clock.schedule_once(_upd)

    def set_wifi_bars(self, n):
        Clock.schedule_once(lambda *_: self._wifi_icon.set_bars(n))

    def set_busy(self, busy):
        def _upd(*_):
            self._setup_btn.disabled = busy
            self._connect_btn.disabled = busy
            self._setup_btn.opacity = 0.5 if busy else 1
            self._connect_btn.opacity = 0.5 if busy else 1
        Clock.schedule_once(_upd)

    # ── button handlers ──
    def _on_setup(self, *_):
        if self._running:
            return
        self._running = True
        self.set_busy(True)
        self.set_status('Setting up…', WARN)
        self.set_wifi_bars(1)
        self.log('Starting Ruijie WiFi setup…', 'info')
        threading.Thread(target=self._run_setup, daemon=True).start()

    def _on_connect(self, *_):
        if self._running:
            return
        voucher = self._voucher_input.text.strip()
        if not voucher:
            self.log('Please enter a voucher code first!', 'warn')
            return
        ip = getattr(self, '_ip', None)
        session_url = getattr(self, '_session_url', None)
        if not ip or not session_url:
            self.log('Run Setup first to get gateway info.', 'warn')
            return
        self._running = True
        self.set_busy(True)
        self.set_status('Connecting…', ACCENT)
        self.set_wifi_bars(2)
        self.log(f'Connecting with voucher: [b]{voucher}[/b]', 'info')
        threading.Thread(
            target=self._run_connect,
            args=(voucher, ip, session_url),
            daemon=True,
        ).start()

    # ── background workers ──
    def _run_setup(self):
        try:
            from wifi_core import WifiSetup
            setup = WifiSetup(log_cb=self.log)
            ip, session_url = setup.run_full_setup()
            if ip and session_url:
                self._ip = ip
                self._session_url = session_url
                self.log(f'Gateway IP: [b]{ip}[/b]', 'success')
                self.log('Session URL obtained ✓', 'success')
                self.set_status('Ready', SUCCESS)
                self.set_wifi_bars(3)
            else:
                self.log('Setup failed. Check network connection.', 'error')
                self.set_status('Failed', DANGER)
                self.set_wifi_bars(0)
        except Exception as e:
            self.log(f'Setup error: {e}', 'error')
            self.set_status('Error', DANGER)
        finally:
            self._running = False
            self.set_busy(False)

    def _run_connect(self, voucher, ip, session_url):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._async_connect(voucher, ip, session_url))
        except Exception as e:
            self.log(f'Connection error: {e}', 'error')
            self.set_status('Error', DANGER)
        finally:
            self._running = False
            self.set_busy(False)

    async def _async_connect(self, voucher, ip, session_url):
        import aiohttp
        from wifi_core import (
            get_session_id, login_voucher, auth_gateway
        )
        async with aiohttp.ClientSession() as session:
            self.log('Fetching session ID…', 'info')
            session_id = await get_session_id(session, session_url, self.log)
            self.log(f'Session ID: [b]{session_id[:16]}…[/b]', 'info')

            self.log('Logging in with voucher…', 'info')
            token = await login_voucher(session, session_id, voucher, self.log)
            if token:
                self.log('Voucher accepted ✓', 'success')
                self.set_wifi_bars(3)
                await auth_gateway(session, voucher, ip, token, session_url, self.log)
                self.set_status('Connected!', SUCCESS)
            else:
                self.log('Failed to get token. Check voucher code.', 'error')
                self.set_status('Auth Failed', DANGER)
                self.set_wifi_bars(1)


# ─── App ───────────────────────────────────────────────────────────────────────
class WiFiApp(App):
    def build(self):
        Window.clearcolor = BG
        sm = ScreenManager(transition=FadeTransition(duration=0.25))
        sm.add_widget(HomeScreen(name='home'))
        return sm

    def on_start(self):
        self.title = 'WiFi Unlimited'


if __name__ == '__main__':
    WiFiApp().run()
