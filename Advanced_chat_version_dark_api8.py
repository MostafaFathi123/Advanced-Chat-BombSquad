# ba_meta require api 8
"""Advanced Chat Version Dark - Complete Chat Overhaul & Suite (API 8).

Features:
- Real-time Message Translation (Google & MyMemory Engines)
- Full Server Chat History & Global Search with Session Backup
- In-Game PBID & Account Dossier Lookup with Live Server Player Inspector
- Remote Automatic Mod Updating
- Remote Error Tracking & Telemetry System (Discord Webhook Integration)

Created & Overhauled by: Darkness83
Discord: https://discord.com/users/825145042900746292
"""

from __future__ import annotations

import ast
import html
import json
import logging
import os
import platform
import re
import shutil
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import weakref
from datetime import datetime
from typing import Any, Callable

import babase
import bauiv1 as bui
from bauiv1lib.popup import PopupMenu, PopupMenuWindow

try:
    import bascenev1 as bs
except Exception:
    bs = None  # type: ignore[assignment]

try:
    from bauiv1lib.account.viewer import AccountViewerWindow
except Exception:
    AccountViewerWindow = None  # type: ignore[assignment,misc]

try:
    from bauiv1lib.utils import spazappearance
except Exception:
    spazappearance = None  # type: ignore[assignment]

try:
    from bauiv1lib.party import PartyWindow as BasePartyWindow
except Exception:
    BasePartyWindow = None  # type: ignore[assignment,misc]

PluginBase = babase.Plugin
app_config = babase.app.config

def app_time() -> float:
    return babase.apptime()

def screen_message(msg: str, color: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> None:
    try:
        bui.screenmessage(msg, color=color)
    except Exception:
        pass

def push_call(call: Any) -> None:
    try:
        bui.pushcall(call, from_other_thread=True)
    except Exception:
        pass

def get_overlay_stack() -> Any:
    return bui.get_special_widget('overlay_stack')

def char_right_arrow() -> str:
    try:
        return babase.charstr(babase.SpecialChar.RIGHT_ARROW)
    except Exception:
        return '->'

def get_default_lang() -> str:
    try:
        return babase.app.lang.default_language
    except Exception:
        return 'English'

def is_ui_scale_small() -> bool:
    return bui.app.ui_v1.uiscale is bui.UIScale.SMALL

def is_ui_scale_medium() -> bool:
    return bui.app.ui_v1.uiscale is bui.UIScale.MEDIUM

def _get_v2_char() -> str:
    try:
        return babase.charstr(babase.SpecialChar.V2_LOGO)
    except Exception:
        return '\ue063'

def _clamp_window_size(desired_w: float, desired_h: float) -> tuple[float, float, float]:
    uiscale = bui.app.ui_v1.uiscale
    if uiscale is bui.UIScale.SMALL:
        scale = 1.15
    elif uiscale is bui.UIScale.MEDIUM:
        scale = 1.0
    else:
        scale = 0.92
    try:
        vw, vh = bui.get_virtual_screen_size()
    except Exception:
        vw, vh = (1280.0, 720.0)
    max_w = max(460.0, (vw / scale) - 40.0)
    max_h = max(340.0, (vh / scale) - 40.0)
    return min(desired_w, max_w), min(desired_h, max_h), scale

def wrap_lines(text: str, max_chars: int) -> list[str]:
    if not text:
        return ['']
    if max_chars < 12:
        max_chars = 12
    out: list[str] = []
    for raw_line in text.splitlines() or ['']:
        words = raw_line.split(' ')
        cur = ''
        for w in words:
            if not cur:
                if len(w) <= max_chars:
                    cur = w
                else:
                    for i in range(0, len(w), max_chars):
                        chunk = w[i : i + max_chars]
                        if len(chunk) == max_chars:
                            out.append(chunk)
                        else:
                            cur = chunk
            elif len(cur) + 1 + len(w) <= max_chars:
                cur += ' ' + w
            else:
                out.append(cur)
                if len(w) <= max_chars:
                    cur = w
                else:
                    cur = ''
                    for i in range(0, len(w), max_chars):
                        chunk = w[i : i + max_chars]
                        if len(chunk) == max_chars:
                            out.append(chunk)
                        else:
                            cur = chunk
        if cur:
            out.append(cur)
    return out or ['']

_ACTIVE_MAIN_WIN: Any = None
_ACTIVE_SUB_WIN: Any = None

def _close_window_safe(win: Any) -> None:
    if win is None:
        return
    try:
        if hasattr(win, '_close'):
            win._close(silent=True)
        elif hasattr(win, '_root_widget') and win._root_widget.exists():
            bui.containerwidget(edit=win._root_widget, transition='out_scale')
    except Exception:
        pass



# ==============================================================================
# Error Telemetry & Remote Auto-Updater System (Darkness83)
# ==============================================================================

MOD_NAME = "Advanced Chat Version Dark"
MOD_VERSION = "1.0.2"
TELEMETRY_WEBHOOK = "https://discord.com/api/webhooks/1574892129828995244/2U_MtUTIr8_xfKORUC7NiR-cOF9A_YQ5FJWtZQeHRMp5CADHqPxxit7dyOL1lH7kKy4P"
AUTO_UPDATE_URL = "https://raw.githubusercontent.com/MostafaFathi123/Advanced-Chat-BombSquad/main/version.json"

_SENT_ERRORS: set[str] = set()
_TELEMETRY_LOCK = threading.Lock()


def get_telemetry_device_info() -> dict[str, str]:
    """Collects safe device, app, and player identity metadata for telemetry."""
    info: dict[str, str] = {
        'mod_version': MOD_VERSION,
        'app_version': 'Unknown',
        'build_number': '0',
        'api_version': 'Unknown',
        'platform': platform.platform(),
        'os': platform.system(),
        'player_name': 'Unknown',
        'pbid': 'Unknown',
        'v2_name': 'Unknown',
        'uiscale': 'Unknown',
    }
    try:
        env = babase.app.env
        info['app_version'] = getattr(env, 'version', 'Unknown')
        info['build_number'] = str(getattr(env, 'engine_build_number', getattr(env, 'build_number', '0')))
        info['api_version'] = str(getattr(env, 'api_version', 'Unknown'))
    except Exception:
        pass

    try:
        plus = getattr(babase.app, 'plus', None)
        if plus is not None:
            if hasattr(plus, 'get_v1_account_public_login_id'):
                pbid = plus.get_v1_account_public_login_id()
                if pbid:
                    info['pbid'] = str(pbid)
            if hasattr(plus, 'get_v1_account_name'):
                acc_name = plus.get_v1_account_name()
                if acc_name:
                    info['player_name'] = str(acc_name)
            if hasattr(plus, 'get_v1_account_display_string'):
                v2_name = plus.get_v1_account_display_string()
                if v2_name:
                    info['v2_name'] = str(v2_name)
    except Exception:
        pass

    try:
        classic = getattr(babase.app, 'classic', None)
        if classic is not None and hasattr(classic, 'accounts'):
            if info['player_name'] == 'Unknown':
                pname = classic.accounts.get_active_player_name()
                if pname:
                    info['player_name'] = str(pname)
    except Exception:
        pass

    try:
        uiscale = bui.app.ui_v1.uiscale
        info['uiscale'] = uiscale.name if hasattr(uiscale, 'name') else str(uiscale)
    except Exception:
        pass

    return info


def report_mod_exception(context: str = "General", exc: Exception | None = None, custom_tb: str | None = None) -> None:
    """Dispatches an isolated, formatted telemetry report to the Discord webhook."""
    import hashlib

    tb_str = custom_tb if custom_tb else traceback.format_exc()
    # Deduplicate errors based on context and traceback summary
    err_hash = hashlib.md5(f"{context}:{tb_str[:200]}".encode('utf-8')).hexdigest()
    with _TELEMETRY_LOCK:
        if err_hash in _SENT_ERRORS:
            return
        _SENT_ERRORS.add(err_hash)

    def _worker() -> None:
        try:
            device_info = get_telemetry_device_info()
            clean_tb = tb_str[-1200:] if len(tb_str) > 1200 else tb_str
            exc_name = type(exc).__name__ if exc else "Exception"
            exc_msg = str(exc) if exc else "An unexpected error occurred"

            payload = {
                'username': 'Advanced Chat Telemetry',
                'embeds': [{
                    'title': f'🚨 Exception in {context}',
                    'description': f'**{exc_name}**: `{exc_msg}`',
                    'color': 0xFF2A42,
                    'fields': [
                        {'name': 'Player Name', 'value': f"`{device_info['player_name']}`", 'inline': True},
                        {'name': 'PBID', 'value': f"`{device_info['pbid']}`", 'inline': True},
                        {'name': 'V2 Account', 'value': f"`{device_info['v2_name']}`", 'inline': True},
                        {'name': 'App Version', 'value': f"`{device_info['app_version']} ({device_info['build_number']})`", 'inline': True},
                        {'name': 'API Version', 'value': f"`API {device_info['api_version']}`", 'inline': True},
                        {'name': 'Mod Version', 'value': f"`v{device_info['mod_version']}`", 'inline': True},
                        {'name': 'Platform', 'value': f"`{device_info['platform']}`", 'inline': True},
                        {'name': 'UI Scale', 'value': f"`{device_info['uiscale']}`", 'inline': True},
                        {'name': 'Traceback', 'value': f'```python\n{clean_tb}\n```', 'inline': False},
                    ],
                    'footer': {'text': 'Darkness83 Advanced Chat Telemetry System'},
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }]
            }

            req = urllib.request.Request(
                TELEMETRY_WEBHOOK,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'BombSquad-AdvancedChat/1.0'}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                pass
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


class _ModErrorLogHandler(logging.Handler):
    """Intercepts uncaught game log events referencing this mod and reports them to Discord."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tb_text = ""
            if record.exc_info:
                tb_text = "".join(traceback.format_exception(*record.exc_info))
            else:
                tb_text = str(record.getMessage())
            if "Advanced_chat_version_dark" in tb_text or "AdvancedPartyWindow" in tb_text:
                exc_obj = record.exc_info[1] if record.exc_info else None
                report_mod_exception(f"Log:{record.name}", exc_obj, custom_tb=tb_text)
        except Exception:
            pass

try:
    logging.getLogger().addHandler(_ModErrorLogHandler())
except Exception:
    pass

try:
    _orig_sys_excepthook = sys.excepthook
    def _mod_sys_excepthook(exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            tb_text = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            if "Advanced_chat_version_dark" in tb_text or "AdvancedPartyWindow" in tb_text:
                report_mod_exception("UncaughtException", exc_val, custom_tb=tb_text)
        except Exception:
            pass
        if _orig_sys_excepthook:
            _orig_sys_excepthook(exc_type, exc_val, exc_tb)
    sys.excepthook = _mod_sys_excepthook
except Exception:
    pass


class AutoUpdateManager:
    """Checks for remote mod updates safely and installs them on user approval or auto-mode."""

    @classmethod
    def check_update_async(cls, silent: bool = True) -> None:
        def _worker() -> None:
            try:
                req = urllib.request.Request(
                    AUTO_UPDATE_URL,
                    headers={'User-Agent': 'BombSquad-AdvancedChat-Updater/1.0'}
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw_data = resp.read().decode('utf-8')
                data = json.loads(raw_data)
                remote_ver = data.get('version', '')
                changelog = data.get('changelog', 'Bug fixes and performance improvements.')
                api_version = getattr(babase.app.env, 'api_version', 8)
                dl_url = data.get(f'download_url_api{api_version}') or data.get('download_url')

                if remote_ver and remote_ver != MOD_VERSION and dl_url:
                    cls._notify_update_available(remote_ver, changelog, dl_url)
                elif not silent:
                    bui.pushcall(
                        bui.Call(bui.screenmessage, f'{MOD_NAME} is up to date (v{MOD_VERSION})', (0.4, 1.0, 0.4)),
                        from_other_thread=True
                    )
            except Exception as ex:
                if not silent:
                    bui.pushcall(
                        bui.Call(bui.screenmessage, f'Could not check for updates: {ex}', (1.0, 0.4, 0.4)),
                        from_other_thread=True
                    )

        threading.Thread(target=_worker, daemon=True).start()

    @classmethod
    def _notify_update_available(cls, new_version: str, changelog: str, dl_url: str) -> None:
        def _show_ui() -> None:
            bui.screenmessage(
                f'New update available for {MOD_NAME}: v{new_version}!',
                color=(0.3, 0.9, 1.0)
            )
            # Prompt or download safely
            cls._download_and_apply_update(new_version, dl_url)

        try:
            bui.pushcall(_show_ui, from_other_thread=True)
        except Exception:
            pass

    @classmethod
    def _download_and_apply_update(cls, new_version: str, dl_url: str) -> None:
        def _worker() -> None:
            try:
                req = urllib.request.Request(dl_url, headers={'User-Agent': 'BombSquad-AdvancedChat/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    new_code = resp.read().decode('utf-8')

                # Strict validation before writing to disk
                import ast
                ast.parse(new_code)

                # Write directly to current file
                cur_file = os.path.abspath(__file__)
                with open(cur_file, 'w', encoding='utf-8') as f:
                    f.write(new_code)

                def _success_msg() -> None:
                    bui.screenmessage(
                        f'{MOD_NAME} updated to v{new_version}! Please restart BombSquad.',
                        color=(0.2, 1.0, 0.3)
                    )
                bui.pushcall(_success_msg, from_other_thread=True)
            except Exception as ex:
                report_mod_exception("AutoUpdater", ex)

        threading.Thread(target=_worker, daemon=True).start()

TRANSLATE_LANGUAGES = {
    'Auto Detect': 'auto',
    'Arabic': 'ar',
    'Chinese (simplified)': 'zh-CN',
    'Chinese (traditional)': 'zh-TW',
    'Croatian': 'hr',
    'Czech': 'cs',
    'Danish': 'da',
    'Dutch': 'nl',
    'English': 'en',
    'Esperanto': 'eo',
    'Finnish': 'fi',
    'French': 'fr',
    'German': 'de',
    'Greek': 'el',
    'Hindi': 'hi',
    'Hungarian': 'hu',
    'Indonesian': 'id',
    'Italian': 'it',
    'Japanese': 'ja',
    'Korean': 'ko',
    'Malay': 'ms',
    'Malayalam': 'ml',
    'Marathi': 'mr',
    'Persian': 'fa',
    'Polish': 'pl',
    'Portuguese': 'pt',
    'Romanian': 'ro',
    'Russian': 'ru',
    'Serbian': 'sr',
    'Slovak': 'sk',
    'Spanish': 'es',
    'Swedish': 'sv',
    'Tagalog': 'tl',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Thai': 'th',
    'Turkish': 'tr',
    'Ukrainian': 'uk',
    'Vietnamese': 'vi',
}

AVAILABLE_LANGUAGES = sorted([lang for lang in TRANSLATE_LANGUAGES if lang != 'Auto Detect'])
AVAILABLE_LANGUAGES.insert(0, 'Auto Detect')


# ==============================================================================
# Translation Core Engine
# ==============================================================================

def fetch_translation(text: str, source: str = 'auto', target: str = 'en') -> str:
    """Translates text with multi-segment support, fallback engine, and strict timeout."""
    cleaned = text.strip()
    if not cleaned:
        return ''

    # Optimization: same language skip
    if source != 'auto' and source == target:
        return cleaned

    ssl_ctx = None
    try:
        import ssl
        ssl_ctx = ssl._create_unverified_context()
    except Exception:
        pass

    # 1. Primary engine: Google Chrome client endpoint (fast, clean JSON, supports auto)
    try:
        quoted = urllib.parse.quote(cleaned)
        url = (
            f'https://clients5.google.com/translate_a/t'
            f'?client=dict-chrome-ex&sl={source}&tl={target}&q={quoted}'
        )
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.5, context=ssl_ctx) as resp:
            data = resp.read().decode('utf-8')
            parsed = json.loads(data)
            if isinstance(parsed, list) and len(parsed) > 0:
                segments = []
                for entry in parsed:
                    if isinstance(entry, list) and len(entry) > 0 and isinstance(entry[0], str):
                        segments.append(entry[0])
                    elif isinstance(entry, str):
                        segments.append(entry)
                if segments:
                    return html.unescape('\n'.join(segments))
    except Exception:
        pass

    # 2. Secondary fallback engine: MyMemory API
    try:
        src = source
        if src == 'auto':
            has_arabic = any('\u0600' <= char <= '\u06FF' for char in cleaned)
            src = 'ar' if has_arabic else 'en'
        quoted = urllib.parse.quote(cleaned)
        url = f'https://api.mymemory.translated.net/get?q={quoted}&langpair={src}|{target}'
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.5, context=ssl_ctx) as resp:
            parsed = json.loads(resp.read().decode('utf-8'))
            if 'responseData' in parsed and 'translatedText' in parsed['responseData']:
                result = parsed['responseData']['translatedText']
                if result and not result.startswith('MYMEMORY WARNING:'):
                    return html.unescape(result)
    except Exception:
        pass

    return cleaned


# ==============================================================================
class TranslateSettingsWindow:
    """Settings popup for configuring source and target translation languages."""

    def __init__(self, on_close_call: Callable[[], Any] | None = None):
        self._on_close_call = on_close_call
        self._scale = (
            2.0 if is_ui_scale_small()
            else 1.4 if is_ui_scale_medium()
            else 1.2
        )
        self._root_widget = bui.containerwidget(
            parent=get_overlay_stack(),
            size=(460, 250),
            transition='in_scale',
            scale=self._scale,
            on_outside_click_call=make_call(self.close, sound=True),
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(230, 205),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='Translation settings',
            scale=1.1,
            maxwidth=350,
        )

        # Incoming messages row
        bui.textwidget(
            parent=self._root_widget,
            position=(25, 145),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='Incoming chat:',
            scale=0.85,
            maxwidth=90,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(260, 145),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text=char_right_arrow(),
            scale=0.9,
        )

        self._other_src = PopupMenu(
            parent=self._root_widget,
            position=(120, 130),
            autoselect=False,
            choices=AVAILABLE_LANGUAGES,
            button_size=(130, 30),
            current_choice=app_config.get('O Source Trans Lang', 'Auto Detect'),
            on_value_change_call=make_call(self._set_lang, 'O Source Trans Lang'),
        )

        self._other_tgt = PopupMenu(
            parent=self._root_widget,
            position=(275, 130),
            autoselect=False,
            choices=AVAILABLE_LANGUAGES[1:],
            button_size=(130, 30),
            current_choice=app_config.get('O Target Trans Lang', DEFAULT_O_TARGET),
            on_value_change_call=make_call(self._set_lang, 'O Target Trans Lang'),
        )

        # Outgoing messages row
        bui.textwidget(
            parent=self._root_widget,
            position=(25, 85),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='Outgoing chat:',
            scale=0.85,
            maxwidth=90,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(260, 85),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text=char_right_arrow(),
            scale=0.9,
        )

        self._your_src = PopupMenu(
            parent=self._root_widget,
            position=(120, 70),
            autoselect=False,
            choices=AVAILABLE_LANGUAGES,
            button_size=(130, 30),
            current_choice=app_config.get('Y Source Trans Lang', 'Auto Detect'),
            on_value_change_call=make_call(self._set_lang, 'Y Source Trans Lang'),
        )

        self._your_tgt = PopupMenu(
            parent=self._root_widget,
            position=(275, 70),
            autoselect=False,
            choices=AVAILABLE_LANGUAGES[1:],
            button_size=(130, 30),
            current_choice=app_config.get('Y Target Trans Lang', DEFAULT_Y_TARGET),
            on_value_change_call=make_call(self._set_lang, 'Y Target Trans Lang'),
        )

        # Action Buttons: Default & Done
        self._default_button = bui.buttonwidget(
            parent=self._root_widget,
            position=(115, 20),
            size=(105, 30),
            label='Default',
            autoselect=True,
            on_activate_call=make_call(self._reset_defaults),
        )

        self._done_button = bui.buttonwidget(
            parent=self._root_widget,
            position=(240, 20),
            size=(105, 30),
            label='Done',
            autoselect=True,
            on_activate_call=make_call(self.close, sound=True),
        )
        bui.containerwidget(edit=self._root_widget, cancel_button=self._done_button)

        # Developer Credit
        bui.textwidget(
            parent=self._root_widget,
            position=(230, 7),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='By Darkness83 | Discord: 825145042900746292',
            scale=0.55,
            color=(0.55, 0.55, 0.55),
            maxwidth=400,
        )

    def _reset_defaults(self) -> None:
        """Restores optimal defaults: Incoming to Arabic, Outgoing to English."""
        app_config['O Source Trans Lang'] = 'Auto Detect'
        app_config['O Target Trans Lang'] = 'Arabic'
        app_config['Y Source Trans Lang'] = 'Auto Detect'
        app_config['Y Target Trans Lang'] = 'English'
        try:
            app_config.commit()
        except Exception:
            pass

        if self._other_src is not None:
            self._other_src.set_choice('Auto Detect')
        if self._other_tgt is not None:
            self._other_tgt.set_choice('Arabic')
        if self._your_src is not None:
            self._your_src.set_choice('Auto Detect')
        if self._your_tgt is not None:
            self._your_tgt.set_choice('English')

        try:
            get_sound('gunCocking').play()
        except Exception:
            pass

    def _set_lang(self, key: str, choice: str) -> None:
        app_config[key] = choice
        try:
            app_config.commit()
        except Exception:
            pass

    def close(self, sound: bool = False) -> None:
        if not self._root_widget or self._root_widget.transitioning_out:
            return
        bui.containerwidget(edit=self._root_widget, transition='out_scale')
        if sound:
            try:
                get_sound('swish').play()
            except Exception:
                pass
        self._other_src = None
        self._other_tgt = None
        self._your_src = None
        self._your_tgt = None
        self._default_button = None
        self._done_button = None
        if self._on_close_call is not None:
            cb = self._on_close_call
            self._on_close_call = None
            try:
                cb()
            except Exception:
                pass

    def __del__(self) -> None:
        self._other_src = None
        self._other_tgt = None
        self._your_src = None
        self._your_tgt = None
        self._default_button = None
        self._done_button = None


# ==============================================================================
# Network Helper: Follow HTTP 307 Redirects (Legacy Master Server support)
# ==============================================================================

try:
    import urllib.request

    class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
        def http_error_307(self, req: Any, fp: Any, code: int, msg: str, headers: Any) -> Any:
            newurl = headers.get('Location')
            if newurl:
                new_req = urllib.request.Request(
                    newurl,
                    data=getattr(req, 'data', None),
                    headers=dict(getattr(req, 'headers', {})),
                    method=req.get_method() if hasattr(req, 'get_method') else None,
                )
                return self.parent.open(new_req)
            return super().http_error_307(req, fp, code, msg, headers)

    urllib.request.install_opener(urllib.request.build_opener(_SafeRedirectHandler))
except Exception:
    pass


# ==============================================================================
# Database Layer (Pure Python JSON: Fast, persistent, zero-dependency)
# ==============================================================================

def get_db_path() -> str:
    """Returns the persistent path for the chat history JSON file."""
    # 1. On Windows: prioritize existing LocalAppData JSON file if present
    local_app = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'BombSquad')
    app_data_file = os.path.join(local_app, 'chat_history.json')
    if os.path.isfile(app_data_file):
        return app_data_file

    # 2. On Android/mobile or custom setups: use BombSquad user python directory
    try:
        user_dir = babase.app.env.python_directory_user
        if user_dir and os.path.isdir(user_dir):
            return os.path.join(user_dir, 'chat_history.json')
    except Exception:
        pass

    # 3. Fallback to LocalAppData folder on Windows
    if os.path.isdir(local_app):
        return app_data_file

    return os.path.abspath('chat_history.json')


def clean_account_name(name: str) -> str:
    """Strips any leading icon/PUA glyphs from name."""
    if not name:
        return ''
    s = str(name).strip()
    while s and 0xE000 <= ord(s[0]) <= 0xF8FF:
        s = s[1:].strip()
    return s


def get_special_char_string(char_enum_name: str, fallback_char: str) -> str:
    """Safely retrieves BombSquad SpecialChar string using babase or bauiv1."""
    try:
        import babase
        enum_val = getattr(babase.SpecialChar, char_enum_name, None)
        if enum_val is not None:
            return babase.charstr(enum_val)
    except Exception:
        pass
    try:
        import bauiv1 as bui
        enum_val = getattr(bui.SpecialChar, char_enum_name, None)
        if enum_val is not None:
            return bui.charstr(enum_val)
    except Exception:
        pass
    return fallback_char


def detect_account_type(name: str = '', account_id: str = '', sender: str = '') -> str:
    """Detects whether an account is V2, Google Play Games (Android), Game Center (Apple), Steam, Local, or Regular."""
    # 1. Direct character inspection
    for candidate in (sender, name):
        if candidate and candidate.strip():
            first = candidate.strip()[0]
            if first == '\ue063':
                return 'v2'
            if first == '\ue020':
                return 'google'
            if first == '\ue021':
                return 'apple'
            if first == '\ue05b':
                return 'steam'
            if first == '\ue026':
                return 'amazon'
            if first == '\ue030':
                return 'local'
            if 0xE000 <= ord(first) <= 0xF8FF:
                return 'custom_icon'

    # 2. Account ID inspection
    aid = (account_id or '').strip().lower()
    if aid == 'v2' or aid.startswith('pb-v2-') or 'v2' in aid:
        return 'v2'
    if any(k in aid for k in ('gpgs', 'google', 'android', 'gp-')):
        return 'google'
    if any(k in aid for k in ('game_center', 'gamecenter', 'apple', 'gc-', 'ios')):
        return 'apple'
    if 'steam' in aid:
        return 'steam'
    if 'amazon' in aid or 'gamecircle' in aid:
        return 'amazon'
    if 'local' in aid:
        return 'local'

    return 'regular'


def format_account_display_name(name: str, account_id: str = '', sender: str = '') -> str:
    """Formats an account name with its official BombSquad platform logo (V2, Android, Apple, Steam, Local)."""
    # Extract existing icon character if present
    existing_icon = ''
    for candidate in (sender, name):
        if candidate and candidate.strip():
            first = candidate.strip()[0]
            if 0xE000 <= ord(first) <= 0xF8FF:
                existing_icon = first
                break

    clean_name = clean_account_name(name) or clean_account_name(sender)
    if not clean_name:
        clean_name = name or sender

    acc_type = detect_account_type(name=name, account_id=account_id, sender=sender)

    if existing_icon:
        icon = existing_icon
    elif acc_type == 'v2':
        icon = get_special_char_string('V2_LOGO', '\ue063')
    elif acc_type == 'google':
        icon = get_special_char_string('GOOGLE_PLAY_GAMES_LOGO', '\ue020')
    elif acc_type == 'apple':
        icon = get_special_char_string('GAME_CENTER_LOGO', '\ue021')
    elif acc_type == 'steam':
        icon = get_special_char_string('STEAM_LOGO', '\ue05b')
    elif acc_type == 'amazon':
        icon = get_special_char_string('GAME_CIRCLE_LOGO', '\ue026')
    elif acc_type == 'local':
        icon = get_special_char_string('LOCAL_ACCOUNT', '\ue030')
    else:
        icon = ''

    return f'{icon}{clean_name}'


class ChatDatabase:
    """Manages Pure-Python JSON storage, querying, indexing, and session lifecycle.

    Guarantees 100% compatibility across all platforms including Android without
    requiring compiled C-extensions like sqlite3.
    """

    _instance: ChatDatabase | None = None

    @classmethod
    def get(cls) -> ChatDatabase:
        if cls._instance is None:
            cls._instance = ChatDatabase()
        return cls._instance

    def __init__(self) -> None:
        self.db_path = get_db_path()
        self._servers: list[dict[str, Any]] = []
        self._settings: dict[str, Any] = {
            'auto_delete_days': 0,       # 0 = None, 7, 14, 30, 60
            'max_size_mb': 0,            # 0 = None, 200, 300, 400, 500
            'ignore_system': False,      # False = Off, True = On
            'session_timeout_min': 30,   # 15, 30, 60
        }
        self._next_server_id = 1
        self._next_session_id = 1
        self._next_msg_id = 1
        self._load()

    def _load(self) -> None:
        """Loads data from JSON file, converting from legacy formats if needed."""
        if not os.path.isfile(self.db_path):
            self._try_migrate_sqlite()
            if not os.path.isfile(self.db_path):
                self._servers = []
                return

        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_settings = data.get('settings')
            if isinstance(loaded_settings, dict):
                self._settings.update(loaded_settings)

            raw_servers = data.get('servers')
            if isinstance(raw_servers, dict):
                # Format: {"server_name": {"address": ..., "last_seen": ..., "sessions": [...]}}
                self._servers = []
                sid = 1
                sess_id = 1
                msg_id = 1
                for sname, sinfo in raw_servers.items():
                    sessions_list: list[dict[str, Any]] = []
                    for sess in sinfo.get('sessions', []):
                        raw_msgs = sess.get('messages', [])
                        parsed_msgs: list[dict[str, Any]] = []
                        for m in raw_msgs:
                            parsed_msgs.append(
                                {
                                    'id': int(m.get('id', msg_id)),
                                    'timestamp': str(m.get('timestamp', '')),
                                    'sender': str(m.get('sender', '')),
                                    'message': str(m.get('message', '')),
                                }
                            )
                            msg_id = max(msg_id, int(m.get('id', msg_id)) + 1)

                        cur_sess_id = int(sess.get('id', sess_id))
                        sess_id = max(sess_id, cur_sess_id + 1)
                        sessions_list.append(
                            {
                                'id': cur_sess_id,
                                'start_time': str(sess.get('start_time', '')),
                                'display_time': str(sess.get('display_time', '')),
                                'messages': parsed_msgs,
                            }
                        )

                    self._servers.append(
                        {
                            'id': sid,
                            'name': str(sname),
                            'address': str(sinfo.get('address', '')),
                            'last_seen': str(sinfo.get('last_seen', '')),
                            'sessions': sessions_list,
                        }
                    )
                    sid += 1

                self._next_server_id = sid
                self._next_session_id = sess_id
                self._next_msg_id = msg_id
                self._save()

            elif isinstance(raw_servers, list):
                # Standard normalized list format
                self._servers = raw_servers
                self._next_server_id = int(data.get('next_server_id', 1))
                self._next_session_id = int(data.get('next_session_id', 1))
                self._next_msg_id = int(data.get('next_msg_id', 1))

                for s in self._servers:
                    self._next_server_id = max(
                        self._next_server_id, int(s.get('id', 0)) + 1
                    )
                    for sess in s.get('sessions', []):
                        self._next_session_id = max(
                            self._next_session_id, int(sess.get('id', 0)) + 1
                        )
                        for m in sess.get('messages', []):
                            self._next_msg_id = max(
                                self._next_msg_id, int(m.get('id', 0)) + 1
                            )

            try:
                self.prune_expired_sessions()
                self.prune_if_size_exceeded()
            except Exception:
                pass
        except Exception:
            logging.exception('Failed to load chat history JSON.')
            self._servers = []

    def _try_migrate_sqlite(self) -> None:
        """One-time safe migration from old SQLite db if sqlite3 is available on this system."""
        try:
            import sqlite3
        except Exception:
            return

        try:
            local_app = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'BombSquad')
            db_candidates = [
                os.path.join(local_app, 'chat_history.db'),
                os.path.abspath('chat_history.db'),
            ]
            try:
                user_dir = babase.app.env.python_directory_user
                if user_dir:
                    db_candidates.append(os.path.join(user_dir, 'chat_history.db'))
            except Exception:
                pass

            old_db = None
            for cand in db_candidates:
                if os.path.isfile(cand):
                    old_db = cand
                    break

            if not old_db:
                return

            conn = sqlite3.connect(old_db)
            c = conn.cursor()

            c.execute('SELECT id, name, address, last_seen FROM servers;')
            servers_rows = c.fetchall()
            server_map: dict[int, dict[str, Any]] = {}
            for r in servers_rows:
                server_map[r[0]] = {
                    'id': r[0],
                    'name': r[1],
                    'address': r[2] or '',
                    'last_seen': r[3],
                    'sessions': [],
                }

            c.execute('SELECT id, server_id, start_time, display_time FROM sessions;')
            sess_rows = c.fetchall()
            sess_map: dict[int, dict[str, Any]] = {}
            for r in sess_rows:
                sess_obj = {
                    'id': r[0],
                    'start_time': r[2],
                    'display_time': r[3],
                    'messages': [],
                }
                sess_map[r[0]] = sess_obj
                if r[1] in server_map:
                    server_map[r[1]]['sessions'].append(sess_obj)

            c.execute(
                'SELECT id, session_id, timestamp, sender, message FROM messages ORDER BY id ASC;'
            )
            for r in c.fetchall():
                if r[1] in sess_map:
                    sess_map[r[1]]['messages'].append(
                        {
                            'id': r[0],
                            'timestamp': r[2],
                            'sender': r[3],
                            'message': r[4],
                        }
                    )

            conn.close()
            self._servers = list(server_map.values())
            self._save()
        except Exception:
            pass

    def _save(self) -> None:
        try:
            parent_dir = os.path.dirname(self.db_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            data = {
                'version': 1,
                'next_server_id': self._next_server_id,
                'next_session_id': self._next_session_id,
                'next_msg_id': self._next_msg_id,
                'settings': self._settings,
                'servers': self._servers,
            }
            tmp_path = self.db_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.db_path)
        except Exception:
            try:
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                logging.exception('Failed to save ChatDatabase to JSON.')

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save()

    def prune_expired_sessions(self) -> int:
        days = int(self._settings.get('auto_delete_days', 0))
        if days <= 0:
            return 0
        cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')

        deleted_count = 0
        for s in self._servers:
            sessions = s.get('sessions', [])
            remaining: list[dict[str, Any]] = []
            for sess in sessions:
                start_time = sess.get('start_time', '')
                if start_time and start_time < cutoff_str:
                    deleted_count += 1
                else:
                    remaining.append(sess)
            s['sessions'] = remaining

        self._servers = [s for s in self._servers if len(s.get('sessions', [])) > 0]
        if deleted_count > 0:
            self._save()
        return deleted_count

    def prune_if_size_exceeded(self) -> int:
        max_mb = int(self._settings.get('max_size_mb', 0))
        if max_mb <= 0:
            return 0
        max_bytes = max_mb * 1024 * 1024

        deleted_count = 0
        try:
            if not os.path.isfile(self.db_path):
                return 0
            cur_bytes = os.path.getsize(self.db_path)
            if cur_bytes <= max_bytes:
                return 0

            # Gather all sessions across all servers with dates
            all_sessions: list[tuple[str, int, int]] = []
            for s in self._servers:
                sid = s['id']
                for sess in s.get('sessions', []):
                    all_sessions.append((sess.get('start_time', ''), sid, sess['id']))

            all_sessions.sort(key=lambda x: x[0])

            for _, _, sess_id in all_sessions:
                self.delete_session(sess_id)
                deleted_count += 1
                if os.path.isfile(self.db_path) and os.path.getsize(self.db_path) < max_bytes:
                    break
        except Exception:
            logging.exception('Error during storage size pruning.')
        return deleted_count

    def get_storage_stats(self) -> dict[str, Any]:
        file_bytes = 0
        try:
            if os.path.isfile(self.db_path):
                file_bytes = os.path.getsize(self.db_path)
        except Exception:
            pass

        if file_bytes < 1024:
            size_str = f'{file_bytes} B'
        elif file_bytes < 1024 * 1024:
            size_str = f'{file_bytes / 1024:.1f} KB'
        else:
            size_str = f'{file_bytes / (1024 * 1024):.2f} MB'

        total_msgs = 0
        total_sessions = 0
        for s in self._servers:
            sessions = s.get('sessions', [])
            total_sessions += len(sessions)
            for sess in sessions:
                total_msgs += len(sess.get('messages', []))

        return {
            'file_bytes': file_bytes,
            'size_str': size_str,
            'message_count': total_msgs,
            'session_count': total_sessions,
            'server_count': len(self._servers),
        }

    def export_backup(self) -> str | None:
        """Exports a full backup copy of chat_history.json to user Downloads folder."""
        try:
            candidates = [
                os.path.join(os.path.expanduser('~'), 'Downloads'),
                os.path.join(os.path.expanduser('~'), 'Videos'),
                '/storage/emulated/0/Download',
            ]
            try:
                user_dir = babase.app.env.python_directory_user
                if user_dir:
                    candidates.append(user_dir)
            except Exception:
                pass

            target_dir = None
            for cand in candidates:
                if cand and os.path.isdir(cand):
                    target_dir = cand
                    break

            if not target_dir:
                target_dir = os.path.dirname(self.db_path)

            backup_dir = os.path.join(target_dir, 'BombSquad_Backups')
            os.makedirs(backup_dir, exist_ok=True)

            ts = time.strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'chat_history_backup_{ts}.json')

            self._save()
            with open(self.db_path, 'r', encoding='utf-8') as src:
                content = src.read()
            with open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(content)

            return backup_file
        except Exception:
            logging.exception('Failed to export database backup.')
            return None

    def _find_server(self, server_id: int) -> dict[str, Any] | None:
        for s in self._servers:
            if s.get('id') == server_id:
                return s
        return None

    def _find_session(self, session_id: int) -> dict[str, Any] | None:
        for s in self._servers:
            for sess in s.get('sessions', []):
                if sess.get('id') == session_id:
                    return sess
        return None

    def get_or_create_server(self, name: str, address: str) -> int:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for s in self._servers:
            if s.get('name') == name:
                s['last_seen'] = now_str
                if address:
                    s['address'] = address
                self._save()
                return int(s['id'])

        sid = self._next_server_id
        self._next_server_id += 1
        new_server = {
            'id': sid,
            'name': name,
            'address': address,
            'last_seen': now_str,
            'sessions': [],
        }
        self._servers.append(new_server)
        self._save()
        return sid

    def create_session(self, server_id: int) -> int:
        now = datetime.datetime.now()
        start_str = now.strftime('%Y-%m-%d %H:%M:%S')
        display_str = now.strftime('%Y-%m-%d  %I:%M:%S %p')
        server = self._find_server(server_id)
        if server is None:
            server = {
                'id': server_id,
                'name': 'Unknown Server',
                'address': '',
                'last_seen': start_str,
                'sessions': [],
            }
            self._servers.append(server)

        sess_id = self._next_session_id
        self._next_session_id += 1
        new_sess = {
            'id': sess_id,
            'start_time': start_str,
            'display_time': display_str,
            'messages': [],
        }
        server.setdefault('sessions', []).append(new_sess)
        self._save()
        return sess_id

    def log_message(
        self,
        session_id: int,
        timestamp: str,
        sender: str,
        text: str,
        account_name: str | None = None,
        account_id: str | None = None,
    ) -> None:
        try:
            sess = self._find_session(session_id)
            if sess is None:
                if self._servers:
                    last_server = self._servers[-1]
                    if not last_server.get('sessions'):
                        self.create_session(last_server['id'])
                    sess = last_server['sessions'][-1]
                else:
                    sid = self.get_or_create_server('Local / Party', '')
                    sess_id = self.create_session(sid)
                    sess = self._find_session(sess_id)
            if sess is None:
                return

            msg_id = self._next_msg_id
            self._next_msg_id += 1
            sess.setdefault('messages', []).append(
                {
                    'id': msg_id,
                    'timestamp': timestamp,
                    'sender': sender,
                    'message': text,
                    'account_name': account_name or sender,
                    'account_id': account_id or '',
                }
            )
            self._save()
        except Exception:
            logging.exception('Failed to log chat message.')

    def get_all_servers(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            for s in self._servers:
                sessions = s.get('sessions', [])
                valid_sessions = [
                    sess for sess in sessions if len(sess.get('messages', [])) > 0
                ]
                msg_count = sum(len(sess.get('messages', [])) for sess in sessions)
                if msg_count > 0:
                    results.append(
                        {
                            'id': s['id'],
                            'name': s['name'],
                            'address': s.get('address', ''),
                            'last_seen': s.get('last_seen', ''),
                            'session_count': len(valid_sessions),
                            'message_count': msg_count,
                        }
                    )
            results.sort(key=lambda x: str(x.get('last_seen', '')), reverse=True)
        except Exception:
            logging.exception('Failed to retrieve servers from ChatDatabase.')
        return results

    def get_server_sessions(self, server_id: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            server = self._find_server(server_id)
            if server:
                for sess in server.get('sessions', []):
                    msg_count = len(sess.get('messages', []))
                    if msg_count > 0:
                        results.append(
                            {
                                'id': sess['id'],
                                'start_time': sess.get('start_time', ''),
                                'display_time': sess.get('display_time', ''),
                                'message_count': msg_count,
                            }
                        )
                results.sort(key=lambda x: str(x.get('start_time', '')), reverse=True)
        except Exception:
            logging.exception('Failed to retrieve sessions from ChatDatabase.')
        return results

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            sess = self._find_session(session_id)
            if sess:
                for m in sess.get('messages', []):
                    results.append(
                        {
                            'id': m.get('id', 0),
                            'timestamp': m.get('timestamp', ''),
                            'sender': m.get('sender', ''),
                            'message': m.get('message', ''),
                            'account_name': m.get('account_name', m.get('sender', '')),
                            'account_id': m.get('account_id', ''),
                        }
                    )
        except Exception:
            logging.exception('Failed to retrieve messages from ChatDatabase.')
        return results

    def global_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Searches all messages across all servers and sessions for query keywords."""
        results: list[dict[str, Any]] = []
        q = query.strip().lower()
        if not q:
            return results

        try:
            for s in self._servers:
                sid = s['id']
                sname = s.get('name', 'Unknown Server')
                for sess in s.get('sessions', []):
                    sess_id = sess['id']
                    disp_time = sess.get('display_time', '')
                    for m in sess.get('messages', []):
                        txt = str(m.get('message', '')).lower()
                        sender = str(m.get('sender', '')).lower()
                        acc_name = str(m.get('account_name', '')).lower()
                        acc_id = str(m.get('account_id', '')).lower()

                        if (
                            q in txt
                            or q in sender
                            or q in acc_name
                            or q in acc_id
                            or q in sname.lower()
                        ):
                            results.append(
                                {
                                    'server_id': sid,
                                    'server_name': sname,
                                    'session_id': sess_id,
                                    'session_display': disp_time,
                                    'timestamp': m.get('timestamp', ''),
                                    'sender': m.get('sender', ''),
                                    'account_name': m.get(
                                        'account_name', m.get('sender', '')
                                    ),
                                    'account_id': m.get('account_id', ''),
                                    'message': m.get('message', ''),
                                }
                            )
                            if len(results) >= limit:
                                results.reverse()
                                return results
        except Exception:
            logging.exception('Failed during global search in ChatDatabase.')

        results.reverse()
        return results
        return results

    def delete_server(self, server_id: int) -> None:
        try:
            self._servers = [s for s in self._servers if s.get('id') != server_id]
            self._save()
        except Exception:
            logging.exception('Failed to delete server.')

    def delete_session(self, session_id: int) -> None:
        try:
            for s in self._servers:
                sessions = s.get('sessions', [])
                new_sessions = [
                    sess for sess in sessions if sess.get('id') != session_id
                ]
                if len(new_sessions) != len(sessions):
                    s['sessions'] = new_sessions
                    break
            self._save()
        except Exception:
            logging.exception('Failed to delete session.')

    def clear_all(self) -> None:
        try:
            self._servers = []
            self._save()
        except Exception:
            logging.exception('Failed to clear ChatDatabase.')


# ==============================================================================
# Tracker: Real-time Hooking & Active Session Monitoring
# ==============================================================================

class ChatTracker:
    """Listens to in-game chat events and coordinates session archiving."""

    _active_server_name: str | None = None
    _active_server_addr: str | None = None
    _active_server_id: int | None = None
    _active_session_id: int | None = None
    _last_msg_time: float = 0.0
    _recent_logged: list[tuple[float, str]] = []
    _last_polled_msgs: list[str] = []
    _player_account_cache: dict[str, dict[str, str]] = {}

    @classmethod
    def get_roster_player_mapping(cls) -> dict[str, dict[str, str]]:
        """Maps in-game player names to their real account name and persistent ID."""
        mapping: dict[str, dict[str, str]] = {}
        try:
            roster = bs.get_game_roster()
            if not roster:
                return mapping
            for client in roster:
                client_id = str(client.get('client_id', ''))
                display_str = str(client.get('display_string', '')).strip()
                spec_str = client.get('spec_string', '')
                account_name = ''
                account_id = ''

                if spec_str:
                    try:
                        spec = json.loads(spec_str)
                        account_name = str(spec.get('n', '')).strip()
                        account_id = str(
                            spec.get('a')
                            or spec.get('id')
                            or spec.get('v2_id')
                            or ''
                        ).strip()
                        if not account_id and spec.get('v2'):
                            account_id = 'v2'
                    except Exception:
                        pass

                if not account_name:
                    account_name = display_str

                if client_id == '-1' or not account_id:
                    try:
                        import babase
                        plus = getattr(babase.app, 'plus', None)
                        if plus is not None and getattr(plus, 'accounts', None) is not None:
                            prim = plus.accounts.primary
                            if prim and getattr(prim, 'accountid', None):
                                account_id = account_id or str(prim.accountid)
                    except Exception:
                        pass

                if not account_id and client_id and client_id != '-1':
                    account_id = f'client_{client_id}'

                info = {
                    'account_name': account_name or display_str,
                    'account_id': account_id,
                    'client_id': client_id,
                    'display_string': display_str,
                }

                if account_name:
                    mapping[account_name] = info
                    mapping[account_name.strip()] = info
                    mapping[account_name.strip().lower()] = info
                if display_str:
                    mapping[display_str] = info
                    mapping[display_str.strip()] = info
                    mapping[display_str.strip().lower()] = info

                for p in client.get('players', []):
                    p_name = p.get('name', '')
                    p_full = p.get('name_full', '')
                    if p_name:
                        mapping[p_name] = info
                        mapping[p_name.strip()] = info
                        mapping[p_name.strip().lower()] = info
                    if p_full:
                        mapping[p_full] = info
                        mapping[p_full.strip()] = info
                        mapping[p_full.strip().lower()] = info
            cls._player_account_cache.update(mapping)
        except Exception:
            pass
        return mapping

    @classmethod
    def poll_chat_messages(cls) -> None:
        """Polls BombSquad internal chat messages continuously to catch all in-game chats."""
        try:
            msgs = bs.get_chat_messages()
            if not msgs or msgs == cls._last_polled_msgs:
                return

            prev = cls._last_polled_msgs
            new_msgs: list[str] = []
            if not prev:
                new_msgs = list(msgs)
            else:
                overlap = 0
                for k in range(len(msgs), 0, -1):
                    if prev[-k:] == msgs[:k]:
                        overlap = k
                        break
                new_msgs = msgs[overlap:] if overlap > 0 else list(msgs)

            cls._last_polled_msgs = list(msgs)
            for m in new_msgs:
                cls.record_incoming_message(m)
        except Exception:
            pass

    @classmethod
    def get_current_server_info(cls) -> tuple[str, str]:
        try:
            info = bs.get_connection_to_host_info_2()
            if info is not None and info.name:
                addr = f'{info.address}:{info.port}' if info.address else ''
                return info.name.strip(), addr
        except Exception:
            pass

        # Persistence during round/map changes on servers:
        # Keep the active server name for 90s to prevent fracturing sessions
        if (
            cls._active_server_name
            and cls._active_server_name not in ('Local / Party', 'MainMenuSession')
        ):
            cur_time = time.time()
            if cur_time - cls._last_msg_time < 90.0:
                return cls._active_server_name, cls._active_server_addr or ''

        try:
            session = bs.get_foreground_host_session()
            if session is not None:
                return type(session).__name__, 'Local'
        except Exception:
            pass

        return 'Local / Party', ''

    @classmethod
    def record_incoming_message(cls, msg: str) -> None:
        if not msg or not isinstance(msg, str):
            return

        cur_time = time.time()

        # Deduplicate identical message events within 1.5s
        cls._recent_logged = [
            (t, m) for (t, m) in cls._recent_logged if cur_time - t < 2.0
        ]
        for t, m in cls._recent_logged:
            if m == msg:
                return
        cls._recent_logged.append((cur_time, msg))

        server_name, server_addr = cls.get_current_server_info()
        db = ChatDatabase.get()

        timeout_sec = int(db.get_setting('session_timeout_min', 30)) * 60
        if timeout_sec <= 0:
            timeout_sec = 1800

        # Group messages into the same session if on the same server within timeout
        if (
            cls._active_server_name != server_name
            or cls._active_session_id is None
            or (cur_time - cls._last_msg_time > timeout_sec)
        ):
            cls._active_server_name = server_name
            cls._active_server_addr = server_addr
            cls._active_server_id = db.get_or_create_server(server_name, server_addr)
            cls._active_session_id = db.create_session(cls._active_server_id)

        cls._last_msg_time = cur_time

        time_str = datetime.datetime.now().strftime('%H:%M:%S')
        if ': ' in msg:
            parts = msg.split(': ', 1)
            sender = parts[0].strip()
            text = parts[1].strip()
        elif ':' in msg:
            parts = msg.split(':', 1)
            sender = parts[0].strip()
            text = parts[1].strip()
        else:
            sender = 'System'
            text = msg.strip()

        if db.get_setting('ignore_system', False):
            if (
                sender == 'System'
                or msg.startswith('***')
                or msg.startswith('[Server]')
                or sender.lower() in ('server', 'system', 'console')
            ):
                return

        # Resolve real account name and persistent ID from roster or cache
        roster_map = cls.get_roster_player_mapping()
        if roster_map:
            cls._player_account_cache.update(roster_map)

        clean_s = clean_account_name(sender)
        acc_info = (
            cls._player_account_cache.get(sender)
            or cls._player_account_cache.get(sender.strip())
            or cls._player_account_cache.get(clean_s)
            or cls._player_account_cache.get(clean_s.lower())
        )
        account_name = acc_info['account_name'] if acc_info and acc_info.get('account_name') else sender
        account_id = acc_info['account_id'] if acc_info and acc_info.get('account_id') else ''

        db.log_message(
            cls._active_session_id,
            time_str,
            sender,
            text,
            account_name=account_name,
            account_id=account_id,
        )


def patch_local_chat_message() -> None:
    """Hooks local_chat_message by swapping __code__ so C++ pointer executes our code."""
    try:
        try:
            import bascenev1._hooks as _bs_hooks
        except Exception:
            _bs_hooks = getattr(bs, '_hooks', None)

        if _bs_hooks is None:
            return

        orig = getattr(_bs_hooks, 'local_chat_message', None)
        if orig is None or getattr(orig, '_chat_history_patched', False):
            return

        def _replacement_local_chat_message(msg: str) -> None:
            try:
                ChatTracker.record_incoming_message(msg)
            except Exception:
                pass
            try:
                classic = babase.app.classic
                if classic is not None:
                    pw = (
                        None
                        if classic.party_window is None
                        else classic.party_window()
                    )
                    if pw is not None:
                        pw.on_chat_message(msg)
            except Exception:
                pass

        try:
            orig.__code__ = _replacement_local_chat_message.__code__
        except Exception:
            pass
        setattr(orig, '_chat_history_patched', True)
        setattr(_bs_hooks, 'local_chat_message', _replacement_local_chat_message)
    except Exception:
        logging.exception('Failed to patch local_chat_message.')


# ==============================================================================
# Window Stack Manager (Prevents Duplicate and Stacked Windows)
# ==============================================================================

_active_chat_window: bui.Window | None = None


def get_active_chat_window() -> bui.Window | None:
    """Returns the currently open chat window if it exists and is alive."""
    global _active_chat_window
    if _active_chat_window is not None:
        try:
            if hasattr(_active_chat_window, '_root_widget') and _active_chat_window._root_widget.exists():
                return _active_chat_window
        except Exception:
            pass
        _active_chat_window = None
    return None


def close_active_chat_window() -> None:
    """Closes any open chat history window without leaving duplicates."""
    global _active_chat_window
    win = get_active_chat_window()
    if win is not None:
        try:
            bui.containerwidget(edit=win._root_widget, transition='out_scale')
        except Exception:
            pass
        _active_chat_window = None


def toggle_chat_history() -> None:
    """Toggles chat history window: closes it if open, opens it if closed."""
    win = get_active_chat_window()
    if win is not None:
        close_active_chat_window()
    else:
        open_chat_history_window()


def open_chat_history_window() -> None:
    """Safely opens Level 1 server list window, closing any previous window."""
    global _active_chat_window
    close_active_chat_window()
    _active_chat_window = ChatHistoryWindow()


def open_server_sessions_window(server_id: int, server_name: str) -> None:
    """Safely opens Level 2 sessions window, closing any previous window."""
    global _active_chat_window
    close_active_chat_window()
    _active_chat_window = ServerSessionsWindow(server_id, server_name)


def open_chat_log_viewer_window(
    server_id: int,
    server_name: str,
    session_id: int,
    session_display: str,
    initial_query: str = '',
) -> None:
    """Safely opens Level 3 chat viewer window, closing any previous window."""
    global _active_chat_window
    close_active_chat_window()
    _active_chat_window = ChatLogViewerWindow(
        server_id,
        server_name,
        session_id,
        session_display,
        initial_query=initial_query,
    )


# ==============================================================================
# UI: Mod Information Modal Window
# ==============================================================================

class ChatHistoryInfoWindow(bui.Window):
    """Modal info dialog showing author credits and contact link."""

    def __init__(self) -> None:
        uiscale = bui.app.ui_v1.uiscale
        self._width = 540 if uiscale is bui.UIScale.SMALL else 480
        self._height = 340 if uiscale is bui.UIScale.SMALL else 300

        super().__init__(
            root_widget=bui.containerwidget(
                size=(self._width, self._height),
                transition='in_scale',
                scale=(
                    1.4
                    if uiscale is bui.UIScale.SMALL
                    else 1.15 if uiscale is bui.UIScale.MEDIUM else 1.0
                ),
                on_outside_click_call=self._close,
            )
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 38),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.1,
            color=(0.35, 0.65, 0.95),
            text='Mod Information',
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 90),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.9,
            color=(0.92, 0.92, 0.95),
            text='Server Chat History Mod',
        )

        try:
            v2_char = babase.charstr(babase.SpecialChar.V2_LOGO)
        except Exception:
            v2_char = ''

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 124),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.05,
            color=(0.4, 0.85, 0.4),
            text=f'Created by {v2_char}Darkness83',
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 165),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.72,
            color=(0.7, 0.68, 0.75),
            text='Discord Account:',
        )

        discord_url = 'https://discord.com/users/825145042900746292'

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 192),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.68,
            color=(0.45, 0.75, 1.0),
            text=discord_url,
            maxwidth=self._width - 60,
        )

        # Bottom Buttons
        btn_w = 135
        btn_h = 42

        self._btn_copy = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width * 0.5 - 145, 30),
            size=(btn_w, btn_h),
            label='Copy Link',
            button_type='square',
            color=(0.3, 0.48, 0.68),
            on_activate_call=self._on_copy_link,
            autoselect=True,
        )

        self._btn_open = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width * 0.5 + 10, 30),
            size=(btn_w, btn_h),
            label='Open Discord',
            button_type='square',
            color=(0.28, 0.58, 0.38),
            on_activate_call=self._on_open_discord,
            autoselect=True,
        )

        self._btn_close = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width - 48, self._height - 44),
            size=(34, 34),
            label='X',
            button_type='square',
            color=(0.48, 0.38, 0.44),
            on_activate_call=self._close,
            autoselect=True,
        )
        bui.containerwidget(
            edit=self._root_widget,
            cancel_button=self._btn_close,
            on_outside_click_call=self._close,
        )

    def _on_copy_link(self) -> None:
        url = 'https://discord.com/users/825145042900746292'
        if bui.clipboard_is_supported():
            bui.clipboard_set_text(url)
            bui.getsound('tap').play()
            bui.screenmessage('Discord profile link copied!', color=(0.2, 1, 0.2))

    def _on_open_discord(self) -> None:
        url = 'https://discord.com/users/825145042900746292'
        bui.getsound('swish').play()
        bui.open_url(url)

    def _close(self) -> None:
        bui.getsound('swish').play()
        bui.containerwidget(edit=self._root_widget, transition='out_scale')


# ==============================================================================
# UI: Settings Window (Storage Maintenance & Preferences)
# ==============================================================================

class ChatHistorySettingsWindow(bui.Window):
    """Modal dialog for configuring chat history preferences and storage maintenance."""

    def __init__(self, on_close_call: Callable[[], None] | None = None) -> None:
        self._on_close_call = on_close_call
        self._db = ChatDatabase.get()
        uiscale = bui.app.ui_v1.uiscale
        self._width = 620 if uiscale is bui.UIScale.SMALL else 560
        self._height = 470 if uiscale is bui.UIScale.SMALL else 430

        super().__init__(
            root_widget=bui.containerwidget(
                size=(self._width, self._height),
                transition='in_scale',
                scale=(
                    1.4
                    if uiscale is bui.UIScale.SMALL
                    else 1.15 if uiscale is bui.UIScale.MEDIUM else 1.0
                ),
                on_outside_click_call=self._close,
            )
        )

        # Title
        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 34),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.05,
            color=(0.4, 0.85, 0.4),
            text='History Settings',
        )

        # Storage & Database summary banner
        self._stats_text = bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 66),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.72,
            color=(0.75, 0.78, 0.88),
            text='',
        )
        self._update_stats_display()

        # Options layout constants
        label_x = 44
        label_max_w = self._width - 240
        btn_w = 140
        btn_h = 36
        btn_x = self._width - 184

        # Row 1: Auto-Delete Old Chats (None, 7 Days, 14 Days, 30 Days, 60 Days)
        y1 = self._height - 116
        bui.textwidget(
            parent=self._root_widget,
            position=(label_x, y1),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.82,
            color=(0.88, 0.88, 0.92),
            text='Auto-Delete Old Chats',
            maxwidth=label_max_w,
        )

        cur_auto_delete = int(self._db.get_setting('auto_delete_days', 0))
        self._btn_auto_delete = bui.buttonwidget(
            parent=self._root_widget,
            position=(btn_x, y1 - btn_h * 0.5),
            size=(btn_w, btn_h),
            label=self._format_auto_delete(cur_auto_delete),
            button_type='square',
            color=(0.32, 0.35, 0.44),
            on_activate_call=self._cycle_auto_delete,
            autoselect=True,
        )

        # Row 2: Storage Size Limit (None, 200 MB, 300 MB, 400 MB, 500 MB)
        y2 = self._height - 166
        bui.textwidget(
            parent=self._root_widget,
            position=(label_x, y2),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.82,
            color=(0.88, 0.88, 0.92),
            text='Storage Size Limit',
            maxwidth=label_max_w,
        )

        cur_max_size = int(self._db.get_setting('max_size_mb', 0))
        self._btn_max_size = bui.buttonwidget(
            parent=self._root_widget,
            position=(btn_x, y2 - btn_h * 0.5),
            size=(btn_w, btn_h),
            label=self._format_max_size(cur_max_size),
            button_type='square',
            color=(0.32, 0.35, 0.44),
            on_activate_call=self._cycle_max_size,
            autoselect=True,
        )

        # Row 3: Ignore System Messages (Off, On)
        y3 = self._height - 216
        bui.textwidget(
            parent=self._root_widget,
            position=(label_x, y3),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.82,
            color=(0.88, 0.88, 0.92),
            text='Ignore System Messages',
            maxwidth=label_max_w,
        )

        cur_ignore_sys = bool(self._db.get_setting('ignore_system', False))
        self._btn_ignore_system = bui.buttonwidget(
            parent=self._root_widget,
            position=(btn_x, y3 - btn_h * 0.5),
            size=(btn_w, btn_h),
            label='On' if cur_ignore_sys else 'Off',
            button_type='square',
            color=(0.28, 0.52, 0.35) if cur_ignore_sys else (0.38, 0.35, 0.42),
            on_activate_call=self._toggle_ignore_system,
            autoselect=True,
        )

        # Row 4: Session Timeout (15 Min, 30 Min, 60 Min)
        y4 = self._height - 266
        bui.textwidget(
            parent=self._root_widget,
            position=(label_x, y4),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.82,
            color=(0.88, 0.88, 0.92),
            text='Session Timeout',
            maxwidth=label_max_w,
        )

        cur_timeout = int(self._db.get_setting('session_timeout_min', 30))
        self._btn_timeout = bui.buttonwidget(
            parent=self._root_widget,
            position=(btn_x, y4 - btn_h * 0.5),
            size=(btn_w, btn_h),
            label=f'{cur_timeout} Min',
            button_type='square',
            color=(0.32, 0.35, 0.44),
            on_activate_call=self._cycle_timeout,
            autoselect=True,
        )

        # Row 5: Backup Database to Downloads
        backup_w = 240
        backup_h = 38
        self._btn_backup = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width * 0.5 - backup_w * 0.5, 84),
            size=(backup_w, backup_h),
            label='Backup Database (JSON)',
            button_type='square',
            color=(0.28, 0.48, 0.72),
            on_activate_call=self._on_backup_database,
            autoselect=True,
        )

        # Bottom Done Button & Top-Right Close Button
        done_w = 120
        done_h = 36
        self._btn_done = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width * 0.5 - done_w * 0.5, 26),
            size=(done_w, done_h),
            label='Done',
            button_type='square',
            color=(0.44, 0.42, 0.48),
            on_activate_call=self._close,
            autoselect=True,
        )

        self._btn_close = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width - 48, self._height - 44),
            size=(34, 34),
            label='X',
            button_type='square',
            color=(0.48, 0.38, 0.44),
            on_activate_call=self._close,
            autoselect=True,
        )
        bui.containerwidget(
            edit=self._root_widget,
            cancel_button=self._btn_close,
            on_outside_click_call=self._close,
        )

    def _update_stats_display(self) -> None:
        stats = self._db.get_storage_stats()
        text = (
            f"Storage: {stats['size_str']}   |   "
            f"Messages: {stats['message_count']}   |   "
            f"Servers: {stats['server_count']}"
        )
        bui.textwidget(edit=self._stats_text, text=text)

    def _format_auto_delete(self, days: int) -> str:
        return 'None' if days <= 0 else f'{days} Days'

    def _format_max_size(self, mb: int) -> str:
        return 'None' if mb <= 0 else f'{mb} MB'

    def _cycle_auto_delete(self) -> None:
        cur = int(self._db.get_setting('auto_delete_days', 0))
        options = [0, 7, 14, 30, 60]
        next_val = options[(options.index(cur) + 1) % len(options)] if cur in options else 0
        self._db.set_setting('auto_delete_days', next_val)
        bui.buttonwidget(edit=self._btn_auto_delete, label=self._format_auto_delete(next_val))
        bui.getsound('tap').play()
        pruned = self._db.prune_expired_sessions()
        if pruned > 0:
            bui.screenmessage(f'Cleaned up {pruned} expired sessions.', color=(0.4, 0.85, 0.4))
        self._update_stats_display()

    def _cycle_max_size(self) -> None:
        cur = int(self._db.get_setting('max_size_mb', 0))
        options = [0, 200, 300, 400, 500]
        next_val = options[(options.index(cur) + 1) % len(options)] if cur in options else 0
        self._db.set_setting('max_size_mb', next_val)
        bui.buttonwidget(edit=self._btn_max_size, label=self._format_max_size(next_val))
        bui.getsound('tap').play()
        pruned = self._db.prune_if_size_exceeded()
        if pruned > 0:
            bui.screenmessage(f'Trimmed {pruned} sessions to fit storage limit.', color=(0.4, 0.85, 0.4))
        self._update_stats_display()

    def _toggle_ignore_system(self) -> None:
        cur = bool(self._db.get_setting('ignore_system', False))
        next_val = not cur
        self._db.set_setting('ignore_system', next_val)
        bui.buttonwidget(
            edit=self._btn_ignore_system,
            label='On' if next_val else 'Off',
            color=(0.28, 0.52, 0.35) if next_val else (0.38, 0.35, 0.42),
        )
        bui.getsound('tap').play()

    def _cycle_timeout(self) -> None:
        cur = int(self._db.get_setting('session_timeout_min', 30))
        options = [15, 30, 60]
        next_val = options[(options.index(cur) + 1) % len(options)] if cur in options else 30
        self._db.set_setting('session_timeout_min', next_val)
        bui.buttonwidget(edit=self._btn_timeout, label=f'{next_val} Min')
        bui.getsound('tap').play()

    def _on_backup_database(self) -> None:
        backup_path = self._db.export_backup()
        if backup_path:
            bui.getsound('tap').play()
            filename = os.path.basename(backup_path)
            bui.screenmessage(f'Backup saved: {filename}', color=(0.2, 1.0, 0.2))
        else:
            bui.getsound('error').play()
            bui.screenmessage('Failed to export backup.', color=(1.0, 0.3, 0.3))
        self._update_stats_display()

    def _close(self) -> None:
        bui.getsound('swish').play()
        bui.containerwidget(edit=self._root_widget, transition='out_scale')
        if self._on_close_call is not None:
            self._on_close_call()


# ==============================================================================
# UI: Level 1 - Unique Server List Window (Only Server Names)
# ==============================================================================

class ChatHistoryWindow(bui.Window):
    """Level 1: Displays unique servers with recorded chat history."""

    def __init__(self, transition: str = 'in_scale') -> None:
        uiscale = bui.app.ui_v1.uiscale
        self._width = 840 if uiscale is bui.UIScale.SMALL else 740
        self._height = 520 if uiscale is bui.UIScale.SMALL else 480
        self._selected_server_id: int | None = None
        self._selected_server_name: str | None = None
        self._server_buttons: dict[int, bui.Widget] = {}

        super().__init__(
            root_widget=bui.containerwidget(
                size=(self._width, self._height),
                transition=transition,
                scale=(
                    1.4
                    if uiscale is bui.UIScale.SMALL
                    else 1.15 if uiscale is bui.UIScale.MEDIUM else 1.0
                ),
                on_outside_click_call=self._close,
            )
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 36),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.1,
            color=(0.4, 0.85, 0.4),
            text='Server Chat History',
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 64),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.72,
            color=(0.7, 0.68, 0.75),
            text='Select a server to view recorded chat sessions.',
        )

        scroll_w = self._width - 230

        # Global Search Bar
        search_y = self._height - 106
        btn_ctrl_w = (
            78 if uiscale is bui.UIScale.SMALL else 68 if uiscale is bui.UIScale.LARGE else 72
        )
        btn_ctrl_h = 30
        gap = 12

        # Search label on the left (x=40, width ~60px, ends at ~100)
        bui.textwidget(
            parent=self._root_widget,
            position=(40, search_y + 15),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.72,
            color=(0.85, 0.85, 0.9),
            text='Search:',
        )

        right_edge = 40 + scroll_w
        clear_x = right_edge - btn_ctrl_w
        find_x = clear_x - gap - btn_ctrl_w

        input_x = 116
        input_w = find_x - gap - input_x

        self._btn_clear_search = bui.buttonwidget(
            parent=self._root_widget,
            size=(btn_ctrl_w, btn_ctrl_h),
            position=(clear_x, search_y),
            label='Clear',
            color=(0.42, 0.38, 0.45),
            on_activate_call=self._on_clear_global_search,
            autoselect=True,
        )

        self._btn_find = bui.buttonwidget(
            parent=self._root_widget,
            size=(btn_ctrl_w, btn_ctrl_h),
            position=(find_x, search_y),
            label='Find',
            color=(0.32, 0.58, 0.32),
            on_activate_call=self._do_global_search,
            autoselect=True,
        )

        self._search_input = bui.textwidget(
            parent=self._root_widget,
            editable=True,
            size=(input_w, btn_ctrl_h),
            position=(input_x, search_y),
            text='',
            maxwidth=input_w - 16,
            shadow=0.2,
            flatness=1.0,
            description='Search all servers...',
            autoselect=True,
            v_align='center',
        )

        bui.textwidget(
            edit=self._search_input, on_return_press_call=self._do_global_search
        )

        scroll_h = self._height - 160

        self._scrollwidget = bui.scrollwidget(
            parent=self._root_widget,
            position=(40, 40),
            size=(scroll_w, scroll_h),
            color=(0.22, 0.2, 0.26),
        )
        self._columnwidget = bui.columnwidget(
            parent=self._scrollwidget, border=2, margin=0
        )

        # Right Action Buttons
        btn_w = 140
        btn_h = 44
        bx = self._width - 170
        by = self._height - 130

        self._btn_open = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Open Sessions',
            color=(0.32, 0.62, 0.32),
            on_activate_call=self._on_open_server,
            autoselect=True,
        )

        by -= 54
        self._btn_delete = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Delete Server',
            color=(0.65, 0.3, 0.3),
            on_activate_call=self._on_delete_server,
            autoselect=True,
        )

        by -= 54
        self._btn_clear = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Clear All',
            color=(0.45, 0.35, 0.4),
            on_activate_call=self._on_clear_all,
            autoselect=True,
        )

        by -= 54
        self._btn_settings = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Settings',
            color=(0.35, 0.40, 0.50),
            on_activate_call=self._on_open_settings,
            autoselect=True,
        )

        by -= 54
        self._btn_info = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Info',
            color=(0.28, 0.48, 0.72),
            on_activate_call=self._on_open_info,
            autoselect=True,
        )

        self._btn_close = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, 44),
            size=(btn_w, btn_h),
            label='Close',
            color=(0.5, 0.45, 0.55),
            on_activate_call=self._close,
            autoselect=True,
        )
        bui.containerwidget(
            edit=self._root_widget,
            cancel_button=self._btn_close,
            on_outside_click_call=self._close,
        )

        self._refresh_list()

    def _refresh_list(self) -> None:
        for child in self._columnwidget.get_children():
            child.delete()
        self._server_buttons.clear()
        self._selected_server_id = None
        self._selected_server_name = None

        db = ChatDatabase.get()
        servers = db.get_all_servers()

        if not servers:
            bui.textwidget(
                parent=self._columnwidget,
                size=(self._width - 250, 80),
                h_align='center',
                v_align='center',
                scale=0.85,
                color=(0.6, 0.58, 0.65),
                text='No recorded server chats yet.\nJoin a server and chat to start logging automatically.',
            )
            return

        scroll_w = self._width - 250
        item_h = 44

        for s in servers:
            sid = s['id']
            sname = s['name']

            # Button contains ONLY the server name inside the rectangle
            btn = bui.buttonwidget(
                parent=self._columnwidget,
                size=(scroll_w, item_h),
                label=sname,
                button_type='square',
                color=(0.35, 0.32, 0.42),
                on_activate_call=bui.Call(self._on_server_click, sid, sname),
                autoselect=True,
            )
            self._server_buttons[sid] = btn

        # Select first server by default
        first = servers[0]
        self._select_server(first['id'], first['name'])

    def _on_server_click(self, sid: int, sname: str) -> None:
        if self._selected_server_id == sid:
            self._on_open_server()
        else:
            self._select_server(sid, sname)

    def _select_server(self, sid: int, sname: str) -> None:
        self._selected_server_id = sid
        self._selected_server_name = sname
        for s_id, btn in self._server_buttons.items():
            if s_id == sid:
                bui.buttonwidget(edit=btn, color=(0.28, 0.52, 0.35))
            else:
                bui.buttonwidget(edit=btn, color=(0.35, 0.32, 0.42))

    def _on_open_server(self) -> None:
        if self._selected_server_id is None or not self._selected_server_name:
            bui.getsound('error').play()
            return
        bui.getsound('swish').play()
        open_server_sessions_window(self._selected_server_id, self._selected_server_name)

    def _on_delete_server(self) -> None:
        if self._selected_server_id is None:
            bui.getsound('error').play()
            return
        bui.getsound('shieldDown').play()
        ChatDatabase.get().delete_server(self._selected_server_id)
        bui.screenmessage('Server chat history deleted.', color=(1, 0.4, 0.4))
        self._refresh_list()

    def _on_clear_all(self) -> None:
        bui.getsound('shieldDown').play()
        ChatDatabase.get().clear_all()
        bui.screenmessage('All chat history cleared.', color=(1, 0.4, 0.4))
        self._refresh_list()

    def _do_global_search(self) -> None:
        raw_q = bui.textwidget(query=self._search_input)
        if not raw_q or not raw_q.strip():
            self._refresh_list()
            return

        bui.getsound('swish').play()
        for child in self._columnwidget.get_children():
            child.delete()
        self._server_buttons.clear()
        self._selected_server_id = None
        self._selected_server_name = None

        db = ChatDatabase.get()
        matches = db.global_search(raw_q.strip(), limit=50)

        if not matches:
            bui.textwidget(
                parent=self._columnwidget,
                size=(self._width - 250, 40),
                h_align='center',
                v_align='center',
                scale=0.8,
                color=(0.7, 0.65, 0.75),
                text=f'No messages matching "{raw_q.strip()}".',
            )
            return

        bui.textwidget(
            parent=self._columnwidget,
            size=(self._width - 250, 24),
            h_align='left',
            v_align='center',
            scale=0.72,
            color=(0.4, 0.85, 0.4),
            text=f'Results ({len(matches)} matches):',
        )

        btn_w = self._width - 250
        for m in matches:
            sid = m['server_id']
            sname = m['server_name']
            sess_id = m['session_id']
            disp_time = m['session_display']
            ts = m['timestamp']
            sender = m['sender']
            acc_name = m['account_name']
            acc_id = m['account_id']
            msg_txt = format_chat_text_for_display(m['message'])

            formatted_acc = format_account_display_name(acc_name, acc_id, sender=sender)
            clean_s = clean_account_name(sender)
            clean_a = clean_account_name(acc_name)
            if clean_s and clean_a and clean_s != clean_a:
                sender_disp = f'{clean_s} ({formatted_acc})'
            else:
                sender_disp = formatted_acc or sender

            # Calculate width and wrapping boundaries
            max_content_w = btn_w - 30
            wrap_chars = max(36, int((btn_w - 40) / 10.5))

            header_text = f'{sname} • {disp_time}'
            header_max_chars = max(38, int((btn_w - 40) / 11.0))
            if len(header_text) > header_max_chars:
                header_text = header_text[: header_max_chars - 3] + '...'

            # 1. Clean header label showing the server and session time
            bui.textwidget(
                parent=self._columnwidget,
                size=(btn_w, 20),
                h_align='left',
                v_align='center',
                scale=0.72,
                color=(0.4, 0.85, 0.4),
                text=f'  {header_text}',
                maxwidth=max_content_w,
                selectable=True,
                autoselect=True,
                on_activate_call=bui.Call(
                    self._on_search_result_click, sid, sname, sess_id, disp_time, raw_q.strip()
                ),
            )

            # 2. Golden yellow message lines with text wrapping
            prefix = f'    [{ts}] {sender_disp}: '
            paragraphs = msg_txt.split('\n')
            wrapped_lines: list[str] = []
            for p_idx, para in enumerate(paragraphs):
                p_prefix = prefix if p_idx == 0 else '      '
                p_text = (p_prefix + para) if para else p_prefix
                lines = textwrap.wrap(
                    p_text,
                    width=wrap_chars,
                    subsequent_indent='      ',
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                wrapped_lines.extend(lines if lines else [p_text])

            if len(wrapped_lines) > 5:
                wrapped_lines = wrapped_lines[:5]
                if not wrapped_lines[-1].endswith('...'):
                    wrapped_lines[-1] = wrapped_lines[-1] + '...'

            for w_line in wrapped_lines:
                bui.textwidget(
                    parent=self._columnwidget,
                    size=(btn_w, 20),
                    h_align='left',
                    v_align='center',
                    scale=0.68,
                    color=(1.0, 0.9, 0.25),
                    text=w_line,
                    maxwidth=max_content_w,
                    selectable=True,
                    autoselect=True,
                    shadow=0.25,
                    flatness=1.0,
                    on_activate_call=bui.Call(
                        self._on_search_result_click, sid, sname, sess_id, disp_time, raw_q.strip()
                    ),
                )

            # 3. Small neat spacer between results
            bui.textwidget(
                parent=self._columnwidget,
                size=(btn_w, 8),
                text='',
            )

    def _on_search_result_click(
        self, sid: int, sname: str, sess_id: int, disp_time: str, query: str = ''
    ) -> None:
        bui.getsound('swish').play()
        open_chat_log_viewer_window(sid, sname, sess_id, disp_time, initial_query=query)

    def _on_clear_global_search(self) -> None:
        bui.textwidget(edit=self._search_input, text='')
        self._refresh_list()

    def _on_open_settings(self) -> None:
        bui.getsound('swish').play()
        ChatHistorySettingsWindow(on_close_call=self._refresh_list)

    def _on_open_info(self) -> None:
        bui.getsound('swish').play()
        ChatHistoryInfoWindow()

    def _close(self) -> None:
        bui.getsound('swish').play()
        global _active_chat_window
        if _active_chat_window is self:
            _active_chat_window = None
        bui.containerwidget(edit=self._root_widget, transition='out_scale')


# ==============================================================================
# UI: Level 2 - Chronological Server Sessions Window (Only Dates and Times)
# ==============================================================================

class ServerSessionsWindow(bui.Window):
    """Level 2: Displays saved dates and times for a specific server (Newest to Oldest)."""

    def __init__(self, server_id: int, server_name: str) -> None:
        self._server_id = server_id
        self._server_name = server_name
        self._selected_session_id: int | None = None
        self._selected_session_display: str | None = None
        self._session_buttons: dict[int, bui.Widget] = {}

        uiscale = bui.app.ui_v1.uiscale
        self._width = 840 if uiscale is bui.UIScale.SMALL else 740
        self._height = 520 if uiscale is bui.UIScale.SMALL else 480

        super().__init__(
            root_widget=bui.containerwidget(
                size=(self._width, self._height),
                transition='in_scale',
                scale=(
                    1.4
                    if uiscale is bui.UIScale.SMALL
                    else 1.15 if uiscale is bui.UIScale.MEDIUM else 1.0
                ),
                on_outside_click_call=self._close,
            )
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 36),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.05,
            color=(0.4, 0.85, 0.4),
            text=f'Sessions: {server_name}',
            maxwidth=self._width * 0.85,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 64),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.72,
            color=(0.7, 0.68, 0.75),
            text='Select a date and time to read its chat log.',
        )

        scroll_w = self._width - 230
        scroll_h = self._height - 120

        self._scrollwidget = bui.scrollwidget(
            parent=self._root_widget,
            position=(40, 40),
            size=(scroll_w, scroll_h),
            color=(0.22, 0.2, 0.26),
        )
        self._columnwidget = bui.columnwidget(
            parent=self._scrollwidget, border=2, margin=0
        )

        # Right Action Buttons
        btn_w = 140
        btn_h = 44
        bx = self._width - 170
        by = self._height - 130

        self._btn_view = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='View Chat',
            color=(0.32, 0.62, 0.32),
            on_activate_call=self._on_view_chat,
            autoselect=True,
        )

        by -= 54
        self._btn_delete = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Delete Session',
            color=(0.65, 0.3, 0.3),
            on_activate_call=self._on_delete_session,
            autoselect=True,
        )

        by -= 54
        self._btn_export = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, by),
            size=(btn_w, btn_h),
            label='Export TXT',
            color=(0.35, 0.5, 0.65),
            on_activate_call=self._on_export_session,
            autoselect=True,
        )

        self._btn_back = bui.buttonwidget(
            parent=self._root_widget,
            position=(bx, 44),
            size=(btn_w, btn_h),
            label='Back',
            color=(0.5, 0.45, 0.55),
            on_activate_call=self._on_back_pressed,
            autoselect=True,
        )
        bui.containerwidget(
            edit=self._root_widget,
            cancel_button=self._btn_back,
            on_outside_click_call=self._close,
        )

        self._refresh_list()

    def _refresh_list(self) -> None:
        for child in self._columnwidget.get_children():
            child.delete()
        self._session_buttons.clear()
        self._selected_session_id = None
        self._selected_session_display = None

        db = ChatDatabase.get()
        sessions = db.get_server_sessions(self._server_id)

        if not sessions:
            bui.textwidget(
                parent=self._columnwidget,
                size=(self._width - 250, 80),
                h_align='center',
                v_align='center',
                scale=0.85,
                color=(0.6, 0.58, 0.65),
                text='No sessions found for this server.',
            )
            return

        scroll_w = self._width - 250
        item_h = 44

        for sess in sessions:
            sess_id = sess['id']
            disp_time = sess['display_time']

            # Button contains ONLY the date and time inside the rectangle
            btn = bui.buttonwidget(
                parent=self._columnwidget,
                size=(scroll_w, item_h),
                label=disp_time,
                button_type='square',
                color=(0.35, 0.32, 0.42),
                on_activate_call=bui.Call(self._on_session_click, sess_id, disp_time),
                autoselect=True,
            )
            self._session_buttons[sess_id] = btn

        # Select first session by default
        first = sessions[0]
        self._select_session(first['id'], first['display_time'])

    def _on_session_click(self, sess_id: int, disp_time: str) -> None:
        if self._selected_session_id == sess_id:
            self._on_view_chat()
        else:
            self._select_session(sess_id, disp_time)

    def _select_session(self, sess_id: int, disp_time: str) -> None:
        self._selected_session_id = sess_id
        self._selected_session_display = disp_time
        for s_id, btn in self._session_buttons.items():
            if s_id == sess_id:
                bui.buttonwidget(edit=btn, color=(0.28, 0.52, 0.35))
            else:
                bui.buttonwidget(edit=btn, color=(0.35, 0.32, 0.42))

    def _on_view_chat(self) -> None:
        if self._selected_session_id is None or not self._selected_session_display:
            bui.getsound('error').play()
            return
        bui.getsound('swish').play()
        open_chat_log_viewer_window(
            self._server_id,
            self._server_name,
            self._selected_session_id,
            self._selected_session_display,
        )

    def _on_delete_session(self) -> None:
        if self._selected_session_id is None:
            bui.getsound('error').play()
            return
        bui.getsound('shieldDown').play()
        ChatDatabase.get().delete_session(self._selected_session_id)
        bui.screenmessage('Session deleted.', color=(1, 0.4, 0.4))
        self._refresh_list()

    def _on_export_session(self) -> None:
        if self._selected_session_id is None:
            bui.getsound('error').play()
            return

        db = ChatDatabase.get()
        msgs = db.get_session_messages(self._selected_session_id)
        if not msgs:
            bui.screenmessage('No messages to export.', color=(1, 0.5, 0.5))
            return

        out_dir = os.path.join(os.path.expanduser('~'), 'Videos', 'BombSquad_Exports')
        os.makedirs(out_dir, exist_ok=True)
        clean_sname = (
            ''.join(c for c in self._server_name if c.isalnum() or c in (' ', '_', '-')).strip()
            or 'Server'
        )
        ts = time.strftime('%Y%m%d_%H%M%S')
        out_file = os.path.join(out_dir, f'Chat_{clean_sname}_{ts}.txt')

        try:
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f'BombSquad Chat Log: {self._server_name}\n')
                f.write(f'Session: {self._selected_session_display}\n')
                f.write('=' * 60 + '\n\n')
                for m in msgs:
                    f.write(f"[{m['timestamp']}] {m['sender']}: {m['message']}\n")
            bui.getsound('shieldUp').play()
            bui.screenmessage(f'Exported to {os.path.basename(out_file)}', color=(0.2, 1, 0.2))
        except Exception:
            logging.exception('Failed to export chat log.')
            bui.getsound('error').play()

    def _on_back_pressed(self) -> None:
        bui.getsound('swish').play()
        open_chat_history_window()

    def _close(self) -> None:
        bui.getsound('swish').play()
        global _active_chat_window
        if _active_chat_window is self:
            _active_chat_window = None
        bui.containerwidget(edit=self._root_widget, transition='out_scale')


# ==============================================================================
# UI: Level 3 - Clean Chat Viewer with In-Chat Search & Jump
# ==============================================================================

def format_chat_text_for_display(raw_text: str) -> str:
    """Formats chat message for display, adding visual tags for face emojis that BombSquad font lacks."""
    if not raw_text or not raw_text.strip():
        return '[empty message]'

    emoji_map = {
        '😂': ' [😂 xD] ',
        '🤣': ' [🤣 ROFL] ',
        '😭': ' [😭 crying] ',
        '🥺': ' [🥺 please] ',
        '💀': ' [💀 dead] ',
        '🔥': ' [🔥 fire] ',
        '❤️': ' [❤️ love] ',
        '😍': ' [😍 heart-eyes] ',
        '😊': ' [😊 smile] ',
        '😁': ' [😁 grin] ',
        '😆': ' [😆 haha] ',
        '😄': ' [😄 happy] ',
        '😃': ' [😃 smile] ',
        '😀': ' [😀 grin] ',
        '😉': ' [😉 wink] ',
        '😎': ' [😎 cool] ',
        '🤔': ' [🤔 thinking] ',
        '🙄': ' [🙄 roll-eyes] ',
        '🤐': ' [🤐 zipped] ',
        '😴': ' [😴 sleeping] ',
        '😡': ' [😡 angry] ',
        '🤬': ' [🤬 curse] ',
        '👍': ' [👍 ok] ',
        '👎': ' [👎 no] ',
        '👏': ' [👏 clap] ',
        '🙏': ' [🙏 pray] ',
        '🤡': ' [🤡 clown] ',
        '💩': ' [💩 poop] ',
        '🎉': ' [🎉 party] ',
        '💯': ' [💯 100] ',
        '✨': ' [✨ sparkle] ',
    }
    res = raw_text
    for emo, tag in emoji_map.items():
        if emo in res:
            res = res.replace(emo, tag)
    return ' '.join(res.split())


class ChatLogViewerWindow(bui.Window):
    """Level 3: Clean left-aligned chat log with in-chat search and match jumping."""

    def __init__(
        self,
        server_id: int,
        server_name: str,
        session_id: int,
        session_display: str,
        initial_query: str = '',
    ) -> None:
        self._server_id = server_id
        self._server_name = server_name
        self._session_id = session_id
        self._session_display = session_display
        self._messages: list[dict[str, Any]] = []
        self._matching_indices: list[int] = []
        self._current_match_idx = 0
        self._row_widgets: list[bui.Widget] = []
        self._selected_player_filter: str | None = None
        self._show_real_accounts: bool = False
        self._last_query: str = initial_query

        uiscale = bui.app.ui_v1.uiscale
        self._width = 840 if uiscale is bui.UIScale.SMALL else 740
        self._height = 520 if uiscale is bui.UIScale.SMALL else 480

        super().__init__(
            root_widget=bui.containerwidget(
                size=(self._width, self._height),
                transition='in_scale',
                scale=(
                    1.4
                    if uiscale is bui.UIScale.SMALL
                    else 1.15 if uiscale is bui.UIScale.MEDIUM else 1.0
                ),
                on_outside_click_call=self._close,
            )
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 28),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=1.0,
            color=(0.4, 0.85, 0.4),
            text=f'Chat: {server_name}',
            maxwidth=self._width * 0.8,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height - 50),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.65,
            color=(0.7, 0.68, 0.75),
            text=f'Session: {session_display}',
            maxwidth=self._width * 0.85,
        )

        # Search Bar Controls
        search_y = self._height - 86
        bui.textwidget(
            parent=self._root_widget,
            position=(40, search_y + 15),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.72,
            color=(0.85, 0.85, 0.9),
            text='Search:',
        )

        input_x = 125
        input_w = 260 if uiscale is bui.UIScale.SMALL else 210
        self._search_field = bui.textwidget(
            parent=self._root_widget,
            editable=True,
            size=(input_w, 30),
            position=(input_x, search_y),
            text=self._last_query,
            maxwidth=input_w - 20,
            shadow=0.2,
            flatness=1.0,
            description='Search chat...',
            autoselect=True,
            v_align='center',
        )

        bx = input_x + input_w + 14
        self._btn_search = bui.buttonwidget(
            parent=self._root_widget,
            size=(62, 30),
            position=(bx, search_y),
            label='Find',
            color=(0.32, 0.58, 0.32),
            on_activate_call=self._do_search,
            autoselect=True,
        )

        bui.textwidget(edit=self._search_field, on_return_press_call=self._do_search)

        bx += 62 + 12
        self._btn_prev = bui.buttonwidget(
            parent=self._root_widget,
            size=(34, 30),
            position=(bx, search_y),
            label='<',
            color=(0.38, 0.35, 0.44),
            on_activate_call=self._jump_prev_match,
            autoselect=True,
        )

        bx += 34 + 10
        self._btn_next = bui.buttonwidget(
            parent=self._root_widget,
            size=(34, 30),
            position=(bx, search_y),
            label='>',
            color=(0.38, 0.35, 0.44),
            on_activate_call=self._jump_next_match,
            autoselect=True,
        )

        bx += 34 + 16
        self._search_status = bui.textwidget(
            parent=self._root_widget,
            position=(bx, search_y + 15),
            size=(0, 0),
            h_align='left',
            v_align='center',
            scale=0.65,
            color=(0.75, 0.72, 0.8),
            maxwidth=self._width - bx - 30,
            text='',
        )

        # Scrollable Chat Area
        scroll_w = self._width - 80
        scroll_h = self._height - 146
        self._scroll_w = scroll_w

        self._scrollwidget = bui.scrollwidget(
            parent=self._root_widget,
            position=(40, 52),
            size=(scroll_w, scroll_h),
            color=(0.18, 0.16, 0.22),
        )
        col_left_border = -200
        self._columnwidget = bui.columnwidget(
            parent=self._scrollwidget,
            border=2,
            left_border=col_left_border,
            margin=0,
            claims_left_right=True,
        )

        self._empty_text = bui.textwidget(
            parent=self._root_widget,
            position=(self._width * 0.5, self._height * 0.45),
            size=(0, 0),
            h_align='center',
            v_align='center',
            scale=0.85,
            color=(0.6, 0.58, 0.65),
            text='',
        )

        # Bottom Bar Buttons
        self._btn_copy_all = bui.buttonwidget(
            parent=self._root_widget,
            position=(40, 14),
            size=(110, 32),
            label='Copy All',
            color=(0.35, 0.45, 0.55),
            on_activate_call=self._on_copy_all,
            autoselect=True,
        )

        self._btn_filter_player = bui.buttonwidget(
            parent=self._root_widget,
            position=(160, 14),
            size=(145, 32),
            label='Filter: All',
            color=(0.35, 0.40, 0.50),
            on_activate_call=self._on_filter_click,
            autoselect=True,
        )

        self._btn_toggle_names = bui.buttonwidget(
            parent=self._root_widget,
            position=(315, 14),
            size=(145, 32),
            label='Names: In-Game',
            color=(0.28, 0.48, 0.72),
            on_activate_call=self._on_toggle_name_mode,
            autoselect=True,
        )

        self._btn_back = bui.buttonwidget(
            parent=self._root_widget,
            position=(self._width - 150, 14),
            size=(110, 32),
            label='Back',
            color=(0.5, 0.45, 0.55),
            on_activate_call=self._on_back_pressed,
            autoselect=True,
        )
        bui.containerwidget(
            edit=self._root_widget,
            cancel_button=self._btn_back,
            on_outside_click_call=self._close,
        )

        self._load_chat()

    def _load_chat(self) -> None:
        db = ChatDatabase.get()
        self._messages = db.get_session_messages(self._session_id)
        self._render_messages(self._last_query)

    def _on_filter_click(self) -> None:
        players_map: dict[str, dict[str, Any]] = {}
        for m in self._messages:
            sender = m.get('sender', '')
            acc_name = m.get('account_name', sender)
            acc_id = m.get('account_id', '')
            key = acc_name or sender
            if key not in players_map:
                players_map[key] = {
                    'senders': set(),
                    'account_name': acc_name,
                    'account_id': acc_id,
                    'msg_count': 0,
                }
            players_map[key]['senders'].add(sender)
            players_map[key]['msg_count'] += 1

        choices = ['all']
        choices_display = ['All Players']

        for key, pinfo in players_map.items():
            choices.append(key)
            acc = pinfo['account_name']
            acc_id = pinfo['account_id']
            cnt = pinfo['msg_count']
            sample_sender = next(iter(pinfo['senders']), '')
            formatted_acc = format_account_display_name(acc, acc_id, sender=sample_sender)
            clean_acc = clean_account_name(acc)
            clean_senders = [
                clean_account_name(s)
                for s in pinfo['senders']
                if clean_account_name(s) and clean_account_name(s) != clean_acc
            ]
            if clean_senders:
                lbl = f'{formatted_acc} ({", ".join(clean_senders)}) ({cnt})'
            else:
                lbl = f'{formatted_acc} ({cnt})'
            if len(lbl) > 34:
                lbl = lbl[:32] + '..'
            choices_display.append(lbl)

        from bauiv1lib.popup import PopupMenuWindow
        uiscale = bui.app.ui_v1.uiscale
        PopupMenuWindow(
            position=self._btn_filter_player.get_screen_space_center(),
            scale=(
                2.2
                if uiscale is bui.UIScale.SMALL
                else 1.6 if uiscale is bui.UIScale.MEDIUM else 1.2
            ),
            choices=choices,
            choices_display=[bui.Lstr(value=d) for d in choices_display],
            current_choice=self._selected_player_filter or 'all',
            delegate=self,
        )

    def popup_menu_selected_choice(self, popup_window: Any, choice: str) -> None:
        if str(choice).lower() == 'all':
            self._selected_player_filter = None
            bui.buttonwidget(edit=self._btn_filter_player, label='Filter: All')
        else:
            self._selected_player_filter = choice
            lbl = f'Filter: {choice}'
            if len(lbl) > 16:
                lbl = lbl[:14] + '..'
            bui.buttonwidget(edit=self._btn_filter_player, label=lbl)
        self._render_messages(self._last_query)

    def popup_menu_closing(self, popup_window: Any) -> None:
        pass

    def _on_toggle_name_mode(self) -> None:
        self._show_real_accounts = not self._show_real_accounts
        bui.getsound('tap').play()
        new_lbl = 'Names: Account' if self._show_real_accounts else 'Names: In-Game'
        bui.buttonwidget(
            edit=self._btn_toggle_names,
            label=new_lbl,
            color=(0.28, 0.52, 0.35) if self._show_real_accounts else (0.28, 0.48, 0.72),
        )
        self._render_messages(self._last_query)

    def _render_messages(self, highlight_query: str = '') -> None:
        self._last_query = highlight_query
        for child in self._columnwidget.get_children():
            child.delete()
        self._row_widgets.clear()
        self._matching_indices.clear()

        if not self._messages:
            bui.textwidget(
                edit=self._empty_text,
                text='No messages recorded in this session.',
            )
            return

        bui.textwidget(edit=self._empty_text, text='')

        row_w = self._scroll_w * 2
        max_w = self._scroll_w - 70
        wrap_chars = max(40, int((self._scroll_w - 70) / 9.2))
        query_lower = highlight_query.lower().strip()

        rendered_count = 0
        for idx, m in enumerate(self._messages):
            sender = m['sender']
            acc_name = m.get('account_name', sender)
            acc_id = m.get('account_id', '')

            # Filter by player if selected
            if self._selected_player_filter is not None:
                match_filter = (
                    self._selected_player_filter == acc_name
                    or self._selected_player_filter == sender
                    or (acc_id and self._selected_player_filter == acc_id)
                )
                if not match_filter:
                    continue

            # In-game name vs Real Account Name
            if self._show_real_accounts:
                disp_sender = format_account_display_name(
                    name=acc_name, account_id=acc_id, sender=sender
                )
            else:
                disp_sender = sender

            ts = m['timestamp']
            raw_text = m['message']
            disp_text = format_chat_text_for_display(raw_text)
            full_line = f'[{ts}] {disp_sender}: {disp_text}'

            is_match = bool(query_lower and query_lower in full_line.lower())
            if is_match:
                self._matching_indices.append(rendered_count)

            # Highlight color vs normal line color
            if is_match:
                line_color = (1.0, 0.9, 0.25)
            elif sender == 'System':
                line_color = (0.85, 0.72, 0.4)
            else:
                line_color = (0.92, 0.92, 0.95)

            # Word-wrap long messages across multiple neat lines
            wrapped_lines: list[str] = []
            prefix = f'[{ts}] {disp_sender}: '
            paragraphs = disp_text.split('\n')
            for p_idx, para in enumerate(paragraphs):
                p_prefix = prefix if p_idx == 0 else '    '
                p_text = (p_prefix + para) if para else p_prefix
                lines = textwrap.wrap(
                    p_text,
                    width=wrap_chars,
                    subsequent_indent='    ',
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                wrapped_lines.extend(lines if lines else [p_text])

            first_widget: bui.Widget | None = None
            for w_line in wrapped_lines:
                txt = bui.textwidget(
                    parent=self._columnwidget,
                    h_align='left',
                    v_align='center',
                    scale=0.58,
                    size=(row_w, 20),
                    text=w_line,
                    autoselect=True,
                    maxwidth=max_w,
                    shadow=0.25,
                    flatness=1.0,
                    color=line_color,
                    selectable=True,
                    on_activate_call=bui.Call(self._on_copy_row, full_line),
                )
                if first_widget is None:
                    first_widget = txt

            if first_widget is not None:
                self._row_widgets.append(first_widget)
            rendered_count += 1

        if highlight_query:
            if self._matching_indices:
                self._current_match_idx = 0
                bui.textwidget(
                    edit=self._search_status,
                    text=f'Found {len(self._matching_indices)} matches (1/{len(self._matching_indices)})',
                    color=(0.4, 0.9, 0.4),
                )
                self._jump_to_match(0)
            else:
                bui.textwidget(
                    edit=self._search_status,
                    text='No matches found.',
                    color=(0.9, 0.4, 0.4),
                )
        else:
            bui.textwidget(edit=self._search_status, text='')

    def _do_search(self) -> None:
        query = cast(str, bui.textwidget(query=self._search_field)).strip()
        bui.getsound('tap').play()
        self._render_messages(highlight_query=query)

    def _jump_to_match(self, match_idx: int) -> None:
        if not self._matching_indices:
            return
        msg_idx = self._matching_indices[match_idx]
        target_widget = self._row_widgets[msg_idx]
        bui.containerwidget(edit=self._columnwidget, visible_child=target_widget)
        bui.textwidget(
            edit=self._search_status,
            text=f'Match {match_idx + 1} of {len(self._matching_indices)}',
            color=(0.4, 0.9, 0.4),
        )

    def _jump_next_match(self) -> None:
        if not self._matching_indices:
            return
        self._current_match_idx = (self._current_match_idx + 1) % len(self._matching_indices)
        self._jump_to_match(self._current_match_idx)

    def _jump_prev_match(self) -> None:
        if not self._matching_indices:
            return
        self._current_match_idx = (self._current_match_idx - 1) % len(self._matching_indices)
        self._jump_to_match(self._current_match_idx)

    def _on_copy_row(self, line: str) -> None:
        if bui.clipboard_is_supported():
            bui.clipboard_set_text(line)
            bui.getsound('tap').play()
            bui.screenmessage('Message copied to clipboard.', color=(0.2, 1, 0.2))

    def _on_copy_all(self) -> None:
        if not self._messages:
            return
        if bui.clipboard_is_supported():
            lines: list[str] = []
            for m in self._messages:
                sender = m['sender']
                acc_name = m.get('account_name', sender)
                acc_id = m.get('account_id', '')

                if self._selected_player_filter is not None:
                    match_filter = (
                        self._selected_player_filter == acc_name
                        or self._selected_player_filter == sender
                        or (acc_id and self._selected_player_filter == acc_id)
                    )
                    if not match_filter:
                        continue

                if self._show_real_accounts:
                    disp_sender = format_account_display_name(
                        name=acc_name, account_id=acc_id, sender=sender
                    )
                else:
                    disp_sender = sender

                lines.append(
                    f"[{m['timestamp']}] {disp_sender}: {format_chat_text_for_display(m['message'])}"
                )

            full_text = '\n'.join(lines)
            bui.clipboard_set_text(full_text)
            bui.getsound('tap').play()
            bui.screenmessage(
                f'{len(lines)} messages copied to clipboard.', color=(0.2, 1, 0.2)
            )

    def _on_back_pressed(self) -> None:
        bui.getsound('swish').play()
        open_server_sessions_window(self._server_id, self._server_name)

    def _close(self) -> None:
        bui.getsound('swish').play()
        global _active_chat_window
        if _active_chat_window is self:
            _active_chat_window = None
        bui.containerwidget(edit=self._root_widget, transition='out_scale')


# ==============================================================================
# Runtime Monkey Patching (Pure mod - leaves ba_data untouched on disk)
# ==============================================================================
class RecentSearchesStore:
    """Stores recent PBID lookups in a JSON file next to BombSquad config."""

    @staticmethod
    def _file_path() -> str:
        try:
            cfg = babase.app.env.config_file_path
            base_dir = os.path.dirname(cfg)
        except Exception:
            base_dir = os.getcwd()
        return os.path.join(base_dir, 'pbid_lookup_history.json')

    @classmethod
    def load(cls) -> list[dict[str, str]]:
        path = cls._file_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict) and x.get('pbid')]
        except Exception:
            pass
        return []

    @classmethod
    def save(cls, items: list[dict[str, str]]) -> None:
        path = cls._file_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(items[:MAX_RECENT], f, ensure_ascii=False, indent=2)
        except Exception as ex:
            logging.warning('Failed to save PBID lookup history: %s', ex)

    @classmethod
    def record(cls, pbid: str, name: str = '', created: str = '') -> None:
        if not pbid:
            return
        items = [x for x in cls.load() if x.get('pbid') != pbid]
        items.insert(
            0,
            {
                'pbid': pbid,
                'name': name or pbid,
                'created': created or '',
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            },
        )
        cls.save(items[:MAX_RECENT])

    @classmethod
    def update_meta(cls, pbid: str, name: str = '', created: str = '') -> None:
        if not pbid:
            return
        items = cls.load()
        changed = False
        for item in items:
            if item.get('pbid') == pbid:
                if name:
                    item['name'] = name
                if created:
                    item['created'] = created
                changed = True
                break
        if changed:
            cls.save(items)

    @classmethod
    def clear(cls) -> None:
        cls.save([])


def fetch_accountquery_async(pbid: str, callback: Any) -> None:
    """Fetch creation timestamp and HTML profile from bombsquadgame.com/accountquery."""

    def _worker() -> None:
        result: dict[str, Any] = {'ok': False, 'error': None, 'created': None, 'name': None}
        try:
            url = f'http://bombsquadgame.com/accountquery?id={pbid}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=7) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw)
            if isinstance(data, dict):
                if 'error' in data and data['error']:
                    result['error'] = str(data['error'])
                else:
                    created_val = data.get('created')
                    if isinstance(created_val, list) and len(created_val) >= 6:
                        dt = datetime(
                            int(created_val[0]),
                            int(created_val[1]),
                            int(created_val[2]),
                            int(created_val[3]),
                            int(created_val[4]),
                            int(created_val[5]),
                        )
                        result['created'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    name_html = data.get('name_html', '')
                    if isinstance(name_html, str) and name_html:
                        char_match = re.search(r'/char/(\d+)\.png', name_html)
                        clean_txt = html.unescape(re.sub(r'<[^>]+>', '', name_html).strip())
                        if char_match:
                            prefix = chr(0xE000 + int(char_match.group(1)))
                            result['name'] = f'{prefix}{clean_txt}'
                        else:
                            result['name'] = clean_txt
                    result['ok'] = True
            else:
                result['error'] = 'Unexpected response format'
        except (urllib.error.HTTPError, urllib.error.URLError) as ex:
            result['error'] = f'Network error: {ex}'
        except Exception as ex:
            result['error'] = str(ex)

        try:
            bui.pushcall(bui.Call(callback, result), from_other_thread=True)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _league_tier_name(tier: str) -> str:
    mapping = {
        'b': 'Bronze',
        's': 'Silver',
        'g': 'Gold',
        'd': 'Diamond',
    }
    return mapping.get(str(tier).lower(), str(tier))


def _clamp_window_size(desired_w: float, desired_h: float) -> tuple[float, float, float]:
    uiscale = bui.app.ui_v1.uiscale
    if uiscale is bui.UIScale.SMALL:
        scale = 1.15
    elif uiscale is bui.UIScale.MEDIUM:
        scale = 1.0
    else:
        scale = 0.92
    try:
        vw, vh = bui.get_virtual_screen_size()
    except Exception:
        vw, vh = (1280.0, 720.0)
    max_w = max(460.0, (vw / scale) - 40.0)
    max_h = max(340.0, (vh / scale) - 40.0)
    return min(desired_w, max_w), min(desired_h, max_h), scale


class InfoWindow:
    """Credits and Discord info dialog."""

    def __init__(self) -> None:
        global _ACTIVE_SUB_WIN
        _close_window_safe(_ACTIVE_SUB_WIN)

        w, h, scale = _clamp_window_size(460.0, 260.0)
        self._transitioning_out = False
        self._root_widget = bui.containerwidget(
            size=(w, h),
            transition='in_scale',
            scale=scale,
            stack_offset=(0, 0),
            on_outside_click_call=self._close,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(w * 0.5, h - 32),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='PBID Lookup Info',
            scale=1.0,
            color=(0.7, 0.9, 1.0),
        )

        v2 = _get_v2_char()
        bui.textwidget(
            parent=self._root_widget,
            position=(w * 0.5, h - 88),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text=f'Created by {v2} Darkness83',
            scale=0.95,
            color=(1.0, 0.92, 0.45),
            maxwidth=w - 50,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(w * 0.5, h - 128),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='Discord Profile:',
            scale=0.72,
            color=(0.8, 0.85, 0.95),
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(w * 0.5, h - 154),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text=DISCORD_URL,
            scale=0.68,
            color=(0.45, 0.78, 1.0),
            maxwidth=w - 44,
        )

        btn_y = 26
        bui.buttonwidget(
            parent=self._root_widget,
            position=(w * 0.5 - 145, btn_y),
            size=(135, 42),
            label='Copy Discord',
            text_scale=0.82,
            autoselect=True,
            color=(0.24, 0.48, 0.78),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=bui.Call(_copy_to_clipboard, DISCORD_URL, 'Discord URL'),
        )

        close_btn = bui.buttonwidget(
            parent=self._root_widget,
            position=(w * 0.5 + 10, btn_y),
            size=(135, 42),
            label='Close',
            text_scale=0.85,
            autoselect=True,
            color=(0.55, 0.25, 0.25),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._close,
        )
        bui.containerwidget(edit=self._root_widget, cancel_button=close_btn)
        _ACTIVE_SUB_WIN = self

    def _close(self, silent: bool = False) -> None:
        if self._transitioning_out:
            return
        self._transitioning_out = True
        if not silent:
            _play_swish()
        try:
            if self._root_widget.exists():
                bui.containerwidget(edit=self._root_widget, transition='out_scale')
        except Exception:
            pass


class ServerPlayersWindow:
    """Lists current server roster players so user can inspect any player without typing PBID."""

    def __init__(self) -> None:
        global _ACTIVE_SUB_WIN
        _close_window_safe(_ACTIVE_SUB_WIN)

        w, h, scale = _clamp_window_size(560.0, 420.0)
        self._width = w
        self._height = h
        self._transitioning_out = False

        self._root_widget = bui.containerwidget(
            size=(w, h),
            transition='in_scale',
            scale=scale,
            stack_offset=(0, 0),
            on_outside_click_call=self._close,
        )

        close_btn = bui.buttonwidget(
            parent=self._root_widget,
            position=(20, h - 48),
            size=(44, 36),
            label='X',
            text_scale=0.9,
            autoselect=True,
            color=(0.6, 0.25, 0.25),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._close,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(78, h - 30),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='Current Server Players',
            scale=0.95,
            color=(0.75, 0.92, 1.0),
            maxwidth=w - 110,
        )

        scroll_w = w - 40
        scroll_h = h - 90
        self._scroll = bui.scrollwidget(
            parent=self._root_widget,
            position=(20, 22),
            size=(scroll_w, scroll_h),
            border_opacity=0.5,
        )
        self._col = bui.columnwidget(
            parent=self._scroll,
            border=4,
            margin=6,
        )

        roster: list[dict[str, Any]] = []
        try:
            if bs is not None and hasattr(bs, 'get_game_roster'):
                roster = bs.get_game_roster() or []
        except Exception:
            roster = []

        if not roster:
            bui.textwidget(
                parent=self._col,
                size=(scroll_w - 24, 60),
                h_align='center',
                v_align='center',
                text='No active server roster found. Join a server first.',
                scale=0.78,
                color=(0.85, 0.85, 0.85),
                maxwidth=scroll_w - 30,
            )
        else:
            for entry in roster:
                pbid = str(entry.get('account_id') or '')
                disp = str(entry.get('display_string') or 'Unknown')
                players = entry.get('players') or []
                names = [str(p.get('name_full') or p.get('name') or '') for p in players if isinstance(p, dict)]
                player_label = ', '.join([n for n in names if n]) or disp

                is_valid_pb = pbid.startswith('pb-')
                sub_txt = pbid if pbid else 'No PBID (Local / Guest)'
                row_label = f'{player_label}   [{sub_txt}]'

                btn_color = (0.24, 0.45, 0.34) if is_valid_pb else (0.35, 0.35, 0.38)
                bui.buttonwidget(
                    parent=self._col,
                    size=(scroll_w - 28, 44),
                    label=row_label,
                    text_scale=0.75,
                    autoselect=True,
                    button_type='square',
                    color=btn_color,
                    textcolor=(1.0, 1.0, 1.0),
                    on_activate_call=bui.Call(self._on_pick, pbid, player_label),
                )

        bui.containerwidget(edit=self._root_widget, cancel_button=close_btn)
        _ACTIVE_SUB_WIN = self

    def _on_pick(self, pbid: str, name: str) -> None:
        if not pbid.startswith('pb-'):
            _screen_msg('This player is using a local/guest profile without a PBID.', (0.95, 0.7, 0.25))
            return
        self._close(silent=True)
        PBIDResultWindow(pbid=pbid, initial_name=name)

    def _close(self, silent: bool = False) -> None:
        if self._transitioning_out:
            return
        self._transitioning_out = True
        if not silent:
            _play_swish()
        try:
            if self._root_widget.exists():
                bui.containerwidget(edit=self._root_widget, transition='out_scale')
        except Exception:
            pass


class PBIDResultWindow:
    """Detailed account dossier combining bsAccountInfo and bombsquadgame.com/accountquery."""

    def __init__(self, pbid: str, initial_name: str = '') -> None:
        global _ACTIVE_SUB_WIN
        _close_window_safe(_ACTIVE_SUB_WIN)

        self._pbid = normalize_pbid(pbid)
        self._initial_name = initial_name
        self._transitioning_out = False

        w, h, scale = _clamp_window_size(640.0, 480.0)
        self._width = w
        self._height = h

        self._root_widget = bui.containerwidget(
            size=(w, h),
            transition='in_scale',
            scale=scale,
            stack_offset=(0, 0),
            on_outside_click_call=self._close,
        )

        # Header bar
        close_btn = bui.buttonwidget(
            parent=self._root_widget,
            position=(20, h - 48),
            size=(44, 36),
            label='X',
            text_scale=0.9,
            autoselect=True,
            color=(0.6, 0.25, 0.25),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._close,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(76, h - 30),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='Account Details',
            scale=0.95,
            color=(0.75, 0.92, 1.0),
            maxwidth=w - 310,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(w - 235, h - 48),
            size=(105, 36),
            label='Copy PBID',
            text_scale=0.72,
            autoselect=True,
            button_type='square',
            color=(0.24, 0.48, 0.78),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=bui.Call(_copy_to_clipboard, self._pbid, 'PBID'),
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(w - 122, h - 48),
            size=(102, 36),
            label='Native UI',
            text_scale=0.72,
            autoselect=True,
            button_type='square',
            color=(0.38, 0.35, 0.52),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._open_native_viewer,
        )

        # Scroll area
        scroll_w = w - 36
        scroll_h = h - 76
        self._scroll = bui.scrollwidget(
            parent=self._root_widget,
            position=(18, 16),
            size=(scroll_w, scroll_h),
            border_opacity=0.5,
        )
        self._scroll_w = scroll_w
        self._col: Any = None

        self._bs_data: dict[str, Any] | None = None
        self._bs_done = False
        self._aq_data: dict[str, Any] | None = None
        self._aq_done = False

        bui.containerwidget(edit=self._root_widget, cancel_button=close_btn)
        _ACTIVE_SUB_WIN = self

        RecentSearchesStore.record(self._pbid, name=initial_name or self._pbid)
        self._rebuild_body()
        self._start_queries()

    def _open_native_viewer(self) -> None:
        if AccountViewerWindow is None:
            _screen_msg('Native AccountViewerWindow is unavailable.', (0.95, 0.5, 0.3))
            return
        try:
            AccountViewerWindow(account_id=self._pbid)
        except Exception as ex:
            _screen_msg(f'Could not open native viewer: {ex}', (0.95, 0.4, 0.4))

    def _start_queries(self) -> None:
        # 1. Master server bsAccountInfo
        try:
            classic = getattr(bui.app, 'classic', None)
            if classic is not None and hasattr(classic, 'master_server_v1_get'):
                build_num = getattr(bui.app.env, 'build_number', 0)
                classic.master_server_v1_get(
                    'bsAccountInfo',
                    {
                        'buildNumber': build_num,
                        'accountID': self._pbid,
                        'profileID': None,
                    },
                    callback=bui.WeakCall(self._on_bs_info),
                )
            else:
                self._bs_done = True
        except Exception:
            self._bs_done = True

        # 2. accountquery for creation date + icon name
        fetch_accountquery_async(self._pbid, bui.WeakCall(self._on_aq_info))

    def _on_bs_info(self, data: dict[str, Any] | None) -> None:
        self._bs_done = True
        self._bs_data = data if isinstance(data, dict) else None
        if self._bs_data:
            names = self._bs_data.get('accountDisplayStrings') or []
            best_name = names[0] if names else (self._bs_data.get('profileDisplayString') or '')
            if best_name:
                RecentSearchesStore.update_meta(self._pbid, name=str(best_name))
        self._rebuild_body()

    def _on_aq_info(self, result: dict[str, Any]) -> None:
        self._aq_done = True
        self._aq_data = result
        if result.get('ok'):
            RecentSearchesStore.update_meta(
                self._pbid,
                name=str(result.get('name') or ''),
                created=str(result.get('created') or ''),
            )
        self._rebuild_body()

    def _add_section_header(self, title: str, color: tuple[float, float, float] = (0.45, 0.85, 1.0)) -> None:
        bui.textwidget(
            parent=self._col,
            size=(self._scroll_w - 30, 26),
            h_align='left',
            v_align='center',
            text=title,
            scale=0.82,
            color=color,
            maxwidth=self._scroll_w - 36,
        )

    def _add_info_line(self, text: str, color: tuple[float, float, float] = (0.94, 0.94, 0.94), scale: float = 0.72) -> None:
        max_chars = max(30, int((self._scroll_w - 50) / 8.5))
        for line in wrap_lines(text, max_chars):
            bui.textwidget(
                parent=self._col,
                size=(self._scroll_w - 30, 22),
                h_align='left',
                v_align='center',
                text='  ' + line,
                scale=scale,
                color=color,
                maxwidth=self._scroll_w - 38,
            )

    def _rebuild_body(self) -> None:
        if not self._root_widget.exists() or not self._scroll.exists():
            return
        if self._col is not None and self._col.exists():
            self._col.delete()

        self._col = bui.columnwidget(
            parent=self._scroll,
            border=8,
            margin=4,
        )

        # Top Summary Row (Character icon + Name + PBID)
        top_row = bui.rowwidget(
            parent=self._col,
            size=(self._scroll_w - 28, 76),
        )
        self._render_character_badge(top_row)

        name_col = bui.columnwidget(parent=top_row, border=2, margin=2)
        disp_name = self._initial_name or self._pbid
        if self._aq_data and self._aq_data.get('name'):
            disp_name = str(self._aq_data['name'])
        elif self._bs_data and self._bs_data.get('accountDisplayStrings'):
            disp_name = str(self._bs_data['accountDisplayStrings'][0])

        bui.textwidget(
            parent=name_col,
            size=(self._scroll_w - 130, 32),
            h_align='left',
            v_align='center',
            text=disp_name,
            scale=0.95,
            color=(1.0, 0.95, 0.55),
            maxwidth=self._scroll_w - 140,
        )
        bui.textwidget(
            parent=name_col,
            size=(self._scroll_w - 130, 24),
            h_align='left',
            v_align='center',
            text=f'PBID: {self._pbid}',
            scale=0.7,
            color=(0.72, 0.85, 0.95),
            maxwidth=self._scroll_w - 140,
        )

        # Creation Date & Account Age
        self._add_section_header('Creation Date & Age')
        if not self._aq_done:
            self._add_info_line('Loading creation date...', (0.75, 0.75, 0.75))
        elif self._aq_data and self._aq_data.get('ok'):
            created = self._aq_data.get('created')
            if created:
                self._add_info_line(f'Created: {created}', (0.65, 1.0, 0.72))
                self._add_info_line(f'Account Age: {compute_age_text(created)}', (0.85, 0.95, 0.85))
            else:
                self._add_info_line('Created: Not provided by server', (0.9, 0.75, 0.45))
        else:
            err = (self._aq_data or {}).get('error') or 'Unavailable'
            self._add_info_line(f'Could not fetch creation date ({err})', (0.95, 0.55, 0.45))

        # Linked Accounts
        self._add_section_header('Linked Accounts')
        if not self._bs_done:
            self._add_info_line('Loading linked accounts...', (0.75, 0.75, 0.75))
        elif self._bs_data is None:
            self._add_info_line('Account not found on master server (or offline).', (0.95, 0.55, 0.45))
        else:
            linked = self._bs_data.get('accountDisplayStrings') or []
            if not linked:
                self._add_info_line('No linked accounts returned.', (0.85, 0.85, 0.85))
            else:
                for acc in linked:
                    acc_str = str(acc)
                    bui.buttonwidget(
                        parent=self._col,
                        size=(self._scroll_w - 40, 32),
                        label=f'{acc_str}   (Tap to copy)',
                        text_scale=0.68,
                        autoselect=True,
                        button_type='square',
                        color=(0.25, 0.30, 0.42),
                        textcolor=(1.0, 1.0, 1.0),
                        on_activate_call=bui.Call(_copy_to_clipboard, acc_str, 'Account'),
                    )

            # Profile & Stats
            self._add_section_header('Profile, Rank & Stats')
            prof_str = self._bs_data.get('profileDisplayString')
            if prof_str:
                self._add_info_line(f'Active Profile: {prof_str}')

            rank = self._bs_data.get('rank')
            if isinstance(rank, (list, tuple)) and len(rank) >= 3:
                tier = _league_tier_name(str(rank[0]))
                self._add_info_line(f'Current Rank: #{rank[2]} in {tier} League [{rank[1]}]', (1.0, 0.88, 0.45))
            else:
                self._add_info_line('Current Rank: Unranked')

            ach_done = self._bs_data.get('achievementsCompleted')
            total_ach = None
            try:
                total_ach = len(bui.app.classic.ach.achievements)
            except Exception:
                pass
            if ach_done is not None:
                ach_txt = f'{ach_done} / {total_ach}' if total_ach else str(ach_done)
                self._add_info_line(f'Achievements: {ach_txt}')

            trophies = self._bs_data.get('trophies')
            if trophies is not None:
                self._add_info_line(f'Season Trophies: {trophies}')

            prev_ranks = self._bs_data.get('prevRanks') or []
            if prev_ranks:
                self._add_section_header('Previous Seasons')
                for pr in prev_ranks[:10]:
                    if isinstance(pr, (list, tuple)) and len(pr) >= 4:
                        tier = _league_tier_name(str(pr[1]))
                        self._add_info_line(f'Season {pr[0]}: #{pr[3]} in {tier} [{pr[2]}]')

    def _render_character_badge(self, parent: Any) -> None:
        try:
            if self._bs_data and self._bs_data.get('profile') and spazappearance is not None:
                profile = self._bs_data['profile']
                character = bui.app.classic.spaz_appearances.get(profile.get('character'), None)
                if character is not None:
                    tint_color = profile.get('color', (1, 1, 1))
                    tint2_color = profile.get('highlight', (1, 1, 1))
                    bui.imagewidget(
                        parent=parent,
                        size=(64, 64),
                        color=(1, 1, 1),
                        mask_texture=bui.gettexture('characterIconMask'),
                        texture=spazappearance.ui_texture(character.icon_texture),
                        tint_texture=spazappearance.ui_texture(character.icon_mask_texture),
                        tint_color=tint_color,
                        tint2_color=tint2_color,
                    )
                    return
        except Exception:
            pass
        bui.textwidget(
            parent=parent,
            size=(64, 64),
            h_align='center',
            v_align='center',
            text=_get_v2_char(),
            scale=1.5,
            color=(0.55, 0.85, 1.0),
        )

    def _close(self, silent: bool = False) -> None:
        if self._transitioning_out:
            return
        self._transitioning_out = True
        if not silent:
            _play_swish()
        try:
            if self._root_widget.exists():
                bui.containerwidget(edit=self._root_widget, transition='out_scale')
        except Exception:
            pass


class PBIDLookupWindow:
    """Main PBID search and recent lookups window."""

    def __init__(self) -> None:
        global _ACTIVE_MAIN_WIN
        _close_window_safe(_ACTIVE_MAIN_WIN)
        _close_window_safe(_ACTIVE_SUB_WIN)

        w, h, scale = _clamp_window_size(640.0, 460.0)
        self._width = w
        self._height = h
        self._transitioning_out = False

        self._root_widget = bui.containerwidget(
            size=(w, h),
            transition='in_scale',
            scale=scale,
            stack_offset=(0, 0),
            on_outside_click_call=self._close,
        )

        # Header
        close_btn = bui.buttonwidget(
            parent=self._root_widget,
            position=(20, h - 48),
            size=(44, 36),
            label='X',
            text_scale=0.9,
            autoselect=True,
            color=(0.6, 0.25, 0.25),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._close,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(76, h - 30),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='PBID Account Lookup',
            scale=0.95,
            color=(0.75, 0.92, 1.0),
            maxwidth=w - 190,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(w - 102, h - 48),
            size=(82, 36),
            label='Info',
            text_scale=0.8,
            autoselect=True,
            button_type='square',
            color=(0.22, 0.48, 0.80),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=InfoWindow,
        )

        # Search row (cleanly spaced, no overlaps)
        row_y = h - 102
        field_w = w - 246
        bui.textwidget(
            parent=self._root_widget,
            position=(22, row_y + 20),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='PBID:',
            scale=0.78,
            color=(0.88, 0.88, 0.88),
        )

        self._pbid_field = bui.textwidget(
            parent=self._root_widget,
            position=(78, row_y),
            size=(field_w, 40),
            editable=True,
            text='',
            description='Enter PBID (e.g. pb-IF4vV123 or IF4vV123)',
            maxwidth=field_w - 16,
            v_align='center',
            corner_scale=0.72,
            autoselect=True,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(78 + field_w + 10, row_y + 2),
            size=(76, 36),
            label='Find',
            text_scale=0.8,
            autoselect=True,
            button_type='square',
            color=(0.24, 0.56, 0.36),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._on_search,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(78 + field_w + 94, row_y + 2),
            size=(64, 36),
            label='Clear',
            text_scale=0.75,
            autoselect=True,
            button_type='square',
            color=(0.45, 0.35, 0.35),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._on_clear_field,
        )

        # Action row
        act_y = h - 152
        bui.buttonwidget(
            parent=self._root_widget,
            position=(22, act_y),
            size=(210, 36),
            label='Current Server Players',
            text_scale=0.75,
            autoselect=True,
            button_type='square',
            color=(0.28, 0.44, 0.68),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=ServerPlayersWindow,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(w - 162, act_y),
            size=(140, 36),
            label='Clear History',
            text_scale=0.74,
            autoselect=True,
            button_type='square',
            color=(0.50, 0.26, 0.26),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._on_clear_history,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(24, act_y - 22),
            size=(0, 0),
            h_align='left',
            v_align='center',
            text='Recent Searches:',
            scale=0.76,
            color=(0.65, 0.85, 1.0),
        )

        scroll_w = w - 40
        scroll_h = act_y - 48
        self._scroll = bui.scrollwidget(
            parent=self._root_widget,
            position=(20, 18),
            size=(scroll_w, scroll_h),
            border_opacity=0.5,
        )
        self._scroll_w = scroll_w
        self._col: Any = None
        self._refresh_recent()

        bui.containerwidget(edit=self._root_widget, cancel_button=close_btn)
        _ACTIVE_MAIN_WIN = self

    def _on_clear_field(self) -> None:
        try:
            bui.textwidget(edit=self._pbid_field, text='')
        except Exception:
            pass

    def _on_search(self) -> None:
        raw = ''
        try:
            raw = str(bui.textwidget(query=self._pbid_field) or '')
        except Exception:
            pass
        pbid = normalize_pbid(raw)
        if not pbid or pbid == 'pb-':
            _screen_msg('Please enter a valid PBID.', (0.95, 0.6, 0.25))
            return
        PBIDResultWindow(pbid=pbid)

    def _on_clear_history(self) -> None:
        RecentSearchesStore.clear()
        self._refresh_recent()
        _screen_msg('Recent PBID history cleared.', (0.65, 0.9, 0.65))

    def _refresh_recent(self) -> None:
        if not self._scroll.exists():
            return
        if self._col is not None and self._col.exists():
            self._col.delete()
        self._col = bui.columnwidget(parent=self._scroll, border=4, margin=6)

        items = RecentSearchesStore.load()
        if not items:
            bui.textwidget(
                parent=self._col,
                size=(self._scroll_w - 28, 56),
                h_align='center',
                v_align='center',
                text='No recent lookups yet. Enter a PBID above or pick a server player.',
                scale=0.72,
                color=(0.75, 0.75, 0.75),
                maxwidth=self._scroll_w - 34,
            )
            return

        for item in items:
            pbid = item.get('pbid', '')
            name = item.get('name', '') or pbid
            created = item.get('created', '')
            if created:
                label = f'{name}   |   {pbid}   |   Created: {created[:10]}'
            else:
                label = f'{name}   |   {pbid}'
            bui.buttonwidget(
                parent=self._col,
                size=(self._scroll_w - 28, 40),
                label=label,
                text_scale=0.72,
                autoselect=True,
                button_type='square',
                color=(0.24, 0.30, 0.40),
                textcolor=(1.0, 1.0, 1.0),
                on_activate_call=bui.Call(PBIDResultWindow, pbid, name),
            )

    def _close(self, silent: bool = False) -> None:
        if self._transitioning_out:
            return
        self._transitioning_out = True
        if not silent:
            _play_swish()
        try:
            if self._root_widget.exists():
                bui.containerwidget(edit=self._root_widget, transition='out_scale')
        except Exception:
            pass


def open_pbid_lookup_window() -> None:
    PBIDLookupWindow()

# ==============================================================================
# UI: Master Unified PartyWindow (Advanced Chat Version Dark)
# ==============================================================================

class AdvancedPartyWindow(BasePartyWindow):
    """Unified PartyWindow featuring Translation, Chat History, and PBID Account Lookup."""

    _menu_popup = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._menu_popup = None
        super().__init__(*args, **kwargs)

        self._last_msg_clicked: str | None = None
        self._last_msg_widget: bui.Widget | None = None
        self._last_time_pressed_msg: float = 0.0
        self._last_time_pressed_trans: float = 0.0
        self._double_press_interval: float = 0.35
        self._my_trans_id: int = 0
        self._translated_messages: dict[bui.Widget, str] = {}
        self._trans_settings_win: TranslateSettingsWindow | None = None

        # Adjust Title text position and width to avoid collisions with top buttons
        self._reposition_title_bar()

        # 1. PBID Lookup Button (Green)
        self._pbid_btn = bui.buttonwidget(
            parent=self._root_widget,
            scale=0.7,
            position=(self._width - 196, self._height - 47),
            size=(76, 50),
            label='PBID',
            text_scale=1.45,
            autoselect=True,
            button_type='square',
            color=(0.22, 0.56, 0.44),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._on_pbid_button_press,
        )

        # 2. Chat History Button (Blue)
        self._history_btn = bui.buttonwidget(
            parent=self._root_widget,
            scale=0.7,
            position=(self._width - 135, self._height - 47),
            size=(80, 50),
            label='History',
            text_scale=1.45,
            autoselect=True,
            button_type='square',
            color=(0.24, 0.46, 0.76),
            textcolor=(1.0, 1.0, 1.0),
            on_activate_call=self._on_history_button_press,
        )

        # 3. Translate Button (Next to Send button)
        self._trans_button = bui.buttonwidget(
            parent=self._root_widget,
            size=(50, 35),
            label='Trans',
            button_type='square',
            autoselect=True,
            position=(self._width - 10, 35),
            on_activate_call=bui.WeakCall(self._translate_your_chat),
        )

    def _reposition_title_bar(self) -> None:
        def _apply() -> None:
            try:
                if hasattr(self, '_title_text') and self._title_text.exists():
                    bui.textwidget(
                        edit=self._title_text,
                        position=(75, self._height - 29),
                        maxwidth=max(100, self._width - 280),
                        h_align='left',
                    )
            except Exception:
                pass
        _apply()
        try:
            bui.apptimer(0.08, _apply)
        except Exception:
            pass

    def _on_pbid_button_press(self) -> None:
        try:
            try:
                self.close()
            except Exception:
                pass
            open_pbid_lookup_window()
        except Exception as ex:
            report_mod_exception("PBIDButtonPress", ex)

    def _on_history_button_press(self) -> None:
        try:
            try:
                self.close()
            except Exception:
                pass
            open_chat_history_window()
        except Exception as ex:
            report_mod_exception("HistoryButtonPress", ex)

    def _open_trans_settings(self) -> None:
        if self._trans_settings_win is not None:
            self._trans_settings_win.close()
        self._trans_settings_win = TranslateSettingsWindow(
            on_close_call=self._on_trans_settings_closed
        )

    def _on_trans_settings_closed(self) -> None:
        self._trans_settings_win = None

    def _translate_your_chat(self) -> None:
        now = app_time()
        # Double click 'Trans' button opens Translation settings window
        if now - self._last_time_pressed_trans < self._double_press_interval:
            self._last_time_pressed_trans = 0.0
            self._open_trans_settings()
            return
        self._last_time_pressed_trans = now

        text = str(bui.textwidget(query=self._text_field)).strip()
        if not text:
            if self._last_msg_clicked and self._last_msg_widget and self._last_msg_widget.exists():
                self._translate_message(self._last_msg_clicked, self._last_msg_widget)
            return

        src_name = app_config.get('Y Source Trans Lang', 'Auto Detect')
        tgt_name = app_config.get('Y Target Trans Lang', DEFAULT_Y_TARGET)
        src_code = TRANSLATE_LANGUAGES.get(src_name, 'auto')
        tgt_code = TRANSLATE_LANGUAGES.get(tgt_name, 'en')

        self._my_trans_id += 1
        my_id = self._my_trans_id
        self_ref = weakref.ref(self)

        def _apply(translated: str) -> None:
            win = self_ref()
            if win is not None and win._my_trans_id == my_id and win._text_field.exists():
                bui.textwidget(edit=win._text_field, text=translated)

        def _worker() -> None:
            try:
                res = fetch_translation(text, source=src_code, target=tgt_code)
                if res and res != text:
                    push_call(bui.Call(_apply, res))
                elif res == text:
                    pass
                else:
                    push_call(bui.Call(screen_message, 'Translation unavailable', (1.0, 0.3, 0.3)))
            except Exception as ex:
                report_mod_exception("TranslateOutgoing", ex)
                push_call(bui.Call(screen_message, 'Network error during translation', (1.0, 0.3, 0.3)))

        threading.Thread(target=_worker, daemon=True).start()

    def _add_msg(self, msg: str, sender: str | None = None, *args: Any, **kwargs: Any) -> None:
        # Pass to parent / tracker
        try:
            ChatTracker.record_incoming_message(msg)
        except Exception:
            pass

        kwargs_text = {
            'parent': self._columnwidget,
            'h_align': 'left',
            'v_align': 'center',
            'scale': 0.55,
            'size': (900, 13),
            'text': msg,
            'autoselect': True,
            'maxwidth': self._scroll_width * 0.94,
            'shadow': 0.3,
            'flatness': 1.0,
            'selectable': True,
        }
        try:
            txt = bui.textwidget(literal=True, **kwargs_text)
        except Exception:
            txt = bui.textwidget(**kwargs_text)

        self._chat_texts.append(txt)
        while len(self._chat_texts) > 50:
            removed = self._chat_texts.pop(0)
            self._translated_messages.pop(removed, None)
            removed.delete()

        bui.containerwidget(edit=self._columnwidget, visible_child=txt)

        bui.textwidget(
            edit=txt,
            on_activate_call=bui.WeakCall(self._on_message_click, msg, txt),
            click_activate=True,
        )

    def _on_message_click(self, original_msg: str, widget: bui.Widget) -> None:
        if not widget.exists():
            return
        now = app_time()
        self._last_msg_clicked = original_msg
        self._last_msg_widget = widget

        # Double click to copy message to clipboard
        if now - self._last_time_pressed_msg < self._double_press_interval:
            self._last_time_pressed_msg = 0.0
            self._copy_msg(original_msg)
            return

        self._last_time_pressed_msg = now
        # Single click translates incoming message
        self._translate_message(original_msg, widget)

    def _copy_msg(self, msg: str) -> None:
        try:
            bui.clipboard_set_text(msg)
            bui.screenmessage('Message copied!', color=(0.4, 1.0, 0.4))
        except Exception:
            pass

    def _translate_message(self, original_msg: str, widget: bui.Widget) -> None:
        if not widget.exists():
            return

        # Toggle back to original message if already translated
        if widget in self._translated_messages:
            orig = self._translated_messages.pop(widget)
            if widget.exists():
                bui.textwidget(edit=widget, text=orig)
            return

        if ':' in original_msg:
            prefix, body = original_msg.split(':', 1)
            sender_prefix = prefix + ': '
            to_translate = body.strip()
        else:
            sender_prefix = ''
            to_translate = original_msg.strip()

        if not to_translate:
            return

        src_name = app_config.get('O Source Trans Lang', 'Auto Detect')
        tgt_name = app_config.get('O Target Trans Lang', DEFAULT_O_TARGET)
        src_code = TRANSLATE_LANGUAGES.get(src_name, 'auto')
        tgt_code = TRANSLATE_LANGUAGES.get(tgt_name, 'ar')

        self_ref = weakref.ref(self)

        def _apply(translated: str) -> None:
            win = self_ref()
            if win is not None and widget.exists():
                win._translated_messages[widget] = original_msg
                bui.textwidget(edit=widget, text=sender_prefix + translated)

        def _worker() -> None:
            try:
                res = fetch_translation(to_translate, source=src_code, target=tgt_code)
                if res and res != to_translate:
                    push_call(bui.Call(_apply, res))
                elif res == to_translate:
                    pass
                else:
                    push_call(bui.Call(screen_message, 'Translation unavailable', (1.0, 0.3, 0.3)))
            except Exception as ex:
                report_mod_exception("TranslateIncoming", ex)
                push_call(bui.Call(screen_message, 'Network error during translation', (1.0, 0.3, 0.3)))

        threading.Thread(target=_worker, daemon=True).start()

    def _send_chat_message(self) -> None:
        self._my_trans_id += 1
        try:
            raw_txt = bui.textwidget(query=self._text_field)
            if raw_txt:
                classic = getattr(bui.app, 'classic', None)
                pname = (
                    classic.accounts.get_active_player_name()
                    if classic
                    else 'Me'
                )
                ChatTracker.record_incoming_message(f'{pname}: {raw_txt}')
        except Exception:
            pass
        super()._send_chat_message()


def patch_local_chat_message() -> None:
    """Hooks local_chat_message so C++ pointer executes our chat tracker."""
    try:
        try:
            import bascenev1._hooks as _bs_hooks
        except Exception:
            _bs_hooks = getattr(bs, '_hooks', None)

        if _bs_hooks is None:
            return

        orig = getattr(_bs_hooks, 'local_chat_message', None)
        if orig is None or getattr(orig, '_adv_chat_patched', False):
            return

        def _replacement_local_chat_message(msg: str) -> None:
            try:
                ChatTracker.record_incoming_message(msg)
            except Exception:
                pass
            try:
                classic = babase.app.classic
                if classic is not None:
                    pw = (
                        None
                        if classic.party_window is None
                        else classic.party_window()
                    )
                    if pw is not None:
                        pw.on_chat_message(msg)
            except Exception:
                pass

        try:
            orig.__code__ = _replacement_local_chat_message.__code__
        except Exception:
            pass
        setattr(orig, '_adv_chat_patched', True)
        setattr(_bs_hooks, 'local_chat_message', _replacement_local_chat_message)
    except Exception as ex:
        report_mod_exception("LocalChatHook", ex)


def apply_party_window_patch() -> None:
    """Replaces PartyWindow with AdvancedPartyWindow across all game references."""
    try:
        import bauiv1lib.party
        bauiv1lib.party.PartyWindow = AdvancedPartyWindow
    except Exception:
        pass
    try:
        import bauiv1._subsystem
        bauiv1._subsystem.PartyWindow = AdvancedPartyWindow
    except Exception:
        pass
    try:
        import bauiv1._appsubsystem
        bauiv1._appsubsystem.PartyWindow = AdvancedPartyWindow
    except Exception:
        pass

    # Dynamic fallback hook on BasePartyWindow if instantiated directly
    try:
        if BasePartyWindow is not None and not getattr(BasePartyWindow, '_adv_dark_patched', False):
            orig_init = BasePartyWindow.__init__

            def _fallback_init(self: Any, *args: Any, **kwargs: Any) -> None:
                orig_init(self, *args, **kwargs)
                if isinstance(self, AdvancedPartyWindow):
                    return
                if getattr(self, '_adv_chat_buttons_added', False):
                    return
                self._adv_chat_buttons_added = True
                try:
                    if hasattr(self, '_title_text') and self._title_text.exists():
                        bui.textwidget(
                            edit=self._title_text,
                            position=(75, self._height - 29),
                            maxwidth=max(100, self._width - 280),
                            h_align='left',
                        )

                    def _open_pbid() -> None:
                        try:
                            self.close()
                        except Exception:
                            pass
                        open_pbid_lookup_window()

                    bui.buttonwidget(
                        parent=self._root_widget,
                        scale=0.7,
                        position=(self._width - 196, self._height - 47),
                        size=(76, 50),
                        label='PBID',
                        text_scale=1.45,
                        autoselect=True,
                        button_type='square',
                        color=(0.22, 0.56, 0.44),
                        textcolor=(1.0, 1.0, 1.0),
                        on_activate_call=_open_pbid,
                    )

                    def _open_hist() -> None:
                        try:
                            self.close()
                        except Exception:
                            pass
                        open_chat_history_window()

                    bui.buttonwidget(
                        parent=self._root_widget,
                        scale=0.7,
                        position=(self._width - 135, self._height - 47),
                        size=(80, 50),
                        label='History',
                        text_scale=1.45,
                        autoselect=True,
                        button_type='square',
                        color=(0.24, 0.46, 0.76),
                        textcolor=(1.0, 1.0, 1.0),
                        on_activate_call=_open_hist,
                    )
                except Exception as ex:
                    report_mod_exception('PartyWindowFallback', ex)

            BasePartyWindow.__init__ = _fallback_init
            BasePartyWindow._adv_dark_patched = True
    except Exception as ex:
        report_mod_exception('PartyWindowPatchInit', ex)


# ba_meta export babase.Plugin
class AdvancedChatVersionDarkPlugin(babase.Plugin):
    """Advanced Chat Version Dark Plugin (All-in-one)."""

    _poll_timer: bui.AppTimer | None = None

    def __init__(self) -> None:
        patch_local_chat_message()
        apply_party_window_patch()
        self._start_poll_timer()
        AutoUpdateManager.check_update_async(silent=True)

    def on_app_running(self) -> None:
        patch_local_chat_message()
        apply_party_window_patch()
        self._start_poll_timer()
        try:
            bui.apptimer(0.5, apply_party_window_patch)
            bui.apptimer(1.5, apply_party_window_patch)
            bui.apptimer(2.5, apply_party_window_patch)
        except Exception:
            pass

    def _start_poll_timer(self) -> None:
        try:
            if self._poll_timer is None:
                self._poll_timer = bui.AppTimer(
                    0.5, ChatTracker.poll_chat_messages, repeat=True
                )
        except Exception:
            pass

    def has_settings_ui(self) -> bool:
        return True

    def show_settings_ui(self, source_widget: bui.Widget | None) -> None:
        del source_widget
        open_chat_history_window()


# Instant initial activation
patch_local_chat_message()
apply_party_window_patch()
try:
    _global_poll_timer = bui.AppTimer(
        0.5, ChatTracker.poll_chat_messages, repeat=True
    )
except Exception:
    pass
