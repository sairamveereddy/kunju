from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import winreg
from ctypes import CFUNCTYPE, POINTER, Structure, byref, c_int, c_ulong, c_void_p, create_unicode_buffer, get_last_error, windll
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import BOTH, DISABLED, NORMAL, Button, Entry, Frame, Label, PhotoImage, StringVar, Tk, messagebox

from pynput import keyboard, mouse


APP_NAME = "Kunju Alarm"
APP_ID = "SairamPrivacyAlarm"
LICENSE_SERVER_URL = ""


def bundled_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "privacy_alarm" / Path(*parts)
    return Path(__file__).resolve().parent / Path(*parts)


DEFAULT_SOUND = bundled_path("assets", "alarm.mp3")
MASCOT_IMAGE = bundled_path("assets", "kunju-hero.png")
ARMING_DELAY_SECONDS = 5
MOUSE_MOVE_COOLDOWN_SECONDS = 0.15
STOP_SEQUENCE_SECONDS = 5.0
TRIAL_DAYS = 7
MUTEX_ALREADY_EXISTS = 183
VK_S = 0x53
VK_ESCAPE = 0x1B
KEY_PRESSED_MASK = 0x8000
KEY_WAS_PRESSED_MASK = 0x0001
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30
EMERGENCY_EXIT_DELAY_MS = 150


class KBDLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("vkCode", c_ulong),
        ("scanCode", c_ulong),
        ("flags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", c_void_p),
    ]


class MSG(Structure):
    _fields_ = [
        ("hwnd", c_void_p),
        ("message", c_ulong),
        ("wParam", c_void_p),
        ("lParam", c_void_p),
        ("time", c_ulong),
        ("pt_x", c_int),
        ("pt_y", c_int),
    ]


LowLevelKeyboardProc = CFUNCTYPE(c_void_p, c_int, c_void_p, c_void_p)


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def setup_logging() -> None:
    logging.basicConfig(
        filename=app_data_dir() / "privacy-alarm.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def show_message(title: str, message: str, icon: int = MB_ICONINFORMATION) -> None:
    windll.user32.MessageBoxW(None, message, title, icon)


def emit_user_message(message: str, warning: bool = False) -> None:
    if sys.stdout:
        print(message)
        return

    icon = MB_ICONWARNING if warning else MB_ICONINFORMATION
    show_message(APP_NAME, message, icon)


class SingleInstance:
    def __init__(self) -> None:
        self.handle = windll.kernel32.CreateMutexW(None, True, f"Global\\{APP_ID}")
        self.already_running = get_last_error() == MUTEX_ALREADY_EXISTS

    def close(self) -> None:
        if self.handle:
            windll.kernel32.CloseHandle(self.handle)


class LicenseManager:
    def __init__(self) -> None:
        self.path = app_data_dir() / "license.json"
        self.data = self._load()

    def _load(self) -> dict[str, str | bool]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logging.warning("License file was invalid JSON.")

        data = {
            "trial_started_at": utc_now().isoformat(),
            "activated": False,
            "license_key": "",
        }
        self._save(data)
        return data

    def _save(self, data: dict[str, str | bool]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def status(self) -> str:
        if self.data.get("activated"):
            return "activated"

        trial_ends = self.trial_ends_at()
        if trial_ends and utc_now() <= trial_ends:
            days_left = max(0, (trial_ends - utc_now()).days + 1)
            return f"trial active ({days_left} day(s) left)"

        return "trial expired"

    def trial_ends_at(self) -> datetime | None:
        raw = self.data.get("trial_started_at")
        if not isinstance(raw, str):
            return None

        try:
            return datetime.fromisoformat(raw) + timedelta(days=TRIAL_DAYS)
        except ValueError:
            return None

    def can_run(self) -> bool:
        if self.data.get("activated"):
            return True

        trial_ends = self.trial_ends_at()
        return trial_ends is not None and utc_now() <= trial_ends

    def activate(self, key: str) -> bool:
        key = key.strip()
        if not key:
            return False

        license_server = os.environ.get("PRIVACY_ALARM_LICENSE_SERVER", "").strip() or LICENSE_SERVER_URL
        if license_server:
            server_data = self._verify_with_server(license_server, key)
            if not server_data:
                return False
        elif not key.startswith("PAL-"):
            return False

        self.data["activated"] = True
        self.data["license_key"] = key
        self.data["machine_id"] = machine_id()
        self.data["activated_at"] = utc_now().isoformat()
        if license_server:
            self.data["license_server"] = license_server
        self._save(self.data)
        return True

    def _verify_with_server(self, license_server: str, key: str) -> dict[str, object] | None:
        payload = json.dumps(
            {
                "license_key": key,
                "machine_id": machine_id(),
                "app_id": APP_ID,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            license_server,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logging.warning("License verification failed: %s", exc)
            return None

        return body if bool(body.get("valid")) else None


def machine_id() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except OSError:
        return os.environ.get("COMPUTERNAME", "unknown-windows-device")


class LoopingAlarm:
    def __init__(self, sound_path: Path) -> None:
        if not sound_path.exists():
            raise FileNotFoundError(f"Alarm sound not found: {sound_path}")

        self.sound_path = sound_path
        self.alias = "privacy_alarm_sound"
        self.lock = threading.Lock()
        self.playing = False

    def start(self) -> None:
        with self.lock:
            if self.playing:
                return

            self.close_alarm_alias()
            quoted_path = str(self.sound_path).replace('"', '\\"')
            opened = self._send(f'open "{quoted_path}" type mpegvideo alias {self.alias}')
            if opened != 0:
                logging.error("Could not open alarm sound. MCI code: %s", opened)
                return

            self._send(f"setaudio {self.alias} volume to 1000")
            played = self._send(f"play {self.alias} repeat")
            if played != 0:
                logging.error("Could not play alarm sound. MCI code: %s", played)
                self.close_alarm_alias()
                return
            self.playing = True
            logging.info("Alarm started with bundled MP3.")

    def stop(self) -> None:
        with self.lock:
            self.force_stop_alias()
            if self.playing:
                logging.info("Alarm stopped.")
            self.playing = False

    @classmethod
    def force_stop_alias(cls) -> None:
        for _ in range(5):
            cls.close_alarm_alias()
            cls._send("stop all")
            cls._send("close all")
            time.sleep(0.02)
        logging.info("Forced alarm audio playback closed.")

    @classmethod
    def close_alarm_alias(cls) -> None:
        cls._send("stop privacy_alarm_sound")
        cls._send("close privacy_alarm_sound")

    @staticmethod
    def _send(command: str) -> int:
        buffer = create_unicode_buffer(255)
        return windll.winmm.mciSendStringW(command, buffer, len(buffer), None)


class HiddenPrivacyAlarm:
    def __init__(self, sound_path: Path) -> None:
        self.alarm = LoopingAlarm(sound_path)
        self.done = threading.Event()
        self.stopping = threading.Event()
        self.armed_at = time.monotonic() + ARMING_DELAY_SECONDS
        self.last_mouse_move_trigger = 0.0
        self.last_esc_press = 0.0
        self.last_s_press = 0.0
        self.last_stop_poll: dict[str, float] = {"esc": 0.0, "s": 0.0}
        self.pressed_stop_keys: set[str] = set()
        self.poll_was_down: dict[str, bool] = {"esc": False, "s": False}
        self.key_lock = threading.Lock()
        self.keyboard_listener: keyboard.Listener | None = None
        self.mouse_listener: mouse.Listener | None = None
        self.stop_key_thread: threading.Thread | None = None
        self.native_hotkey_thread: threading.Thread | None = None
        self.native_hook = None
        self.native_hook_callback = None
        self.native_hook_thread_id = 0

    def run(self) -> None:
        logging.info("Privacy alarm launched. Arming in %s seconds.", ARMING_DELAY_SECONDS)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = mouse.Listener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click,
            on_scroll=self.on_mouse_scroll,
        )
        self.keyboard_listener.start()
        self.mouse_listener.start()
        self.stop_key_thread = threading.Thread(target=self.watch_stop_key, daemon=True)
        self.stop_key_thread.start()
        self.native_hotkey_thread = threading.Thread(target=self.watch_native_stop_hotkey, daemon=True)
        self.native_hotkey_thread.start()

        self.done.wait()
        self.close()

    def watch_native_stop_hotkey(self) -> None:
        self.native_hook_thread_id = windll.kernel32.GetCurrentThreadId()

        def callback(n_code, w_param, l_param):
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                event = POINTER(KBDLLHOOKSTRUCT).from_address(l_param).contents
                if event.vkCode == VK_ESCAPE:
                    self.last_stop_poll["esc"] = time.monotonic()
                    self.stop_and_exit()
                elif event.vkCode == VK_S:
                    self.last_stop_poll["s"] = time.monotonic()
                    self.stop_and_exit()
            return windll.user32.CallNextHookEx(self.native_hook, n_code, w_param, l_param)

        self.native_hook_callback = LowLevelKeyboardProc(callback)
        self.native_hook = windll.user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.native_hook_callback, windll.kernel32.GetModuleHandleW(None), 0)
        if not self.native_hook:
            logging.warning("Native stop hotkey hook could not be installed.")
            return

        msg = MSG()
        while not self.done.is_set():
            result = windll.user32.GetMessageW(byref(msg), None, 0, 0)
            if result in (0, -1):
                break
            windll.user32.TranslateMessage(byref(msg))
            windll.user32.DispatchMessageW(byref(msg))

        if self.native_hook:
            windll.user32.UnhookWindowsHookEx(self.native_hook)
            self.native_hook = None

    def watch_stop_key(self) -> None:
        while not self.done.is_set():
            if self.poll_stop_keys():
                return
            time.sleep(0.03)

    def poll_stop_keys(self) -> bool:
        now = time.monotonic()
        current = {
            "esc": self.virtual_key_state(VK_ESCAPE),
            "s": self.virtual_key_state(VK_S),
        }

        for name, state in current.items():
            is_down = state["down"]
            was_down = self.poll_was_down.get(name, False)
            self.poll_was_down[name] = is_down
            if not is_down and was_down:
                with self.key_lock:
                    self.pressed_stop_keys.discard(name)
            if state["pressed"] or (is_down and not was_down):
                self.last_stop_poll[name] = now
                self.stop_and_exit()
                return True

        both_down = current["esc"]["down"] and current["s"]["down"]
        recent_combo = (
            self.last_stop_poll["esc"] > 0
            and self.last_stop_poll["s"] > 0
            and abs(self.last_stop_poll["esc"] - self.last_stop_poll["s"]) <= STOP_SEQUENCE_SECONDS
        )

        if both_down or recent_combo:
            self.stop_and_exit()
            return True

        return False

    @staticmethod
    def virtual_key_state(vk_code: int) -> dict[str, bool]:
        state = windll.user32.GetAsyncKeyState(vk_code)
        return {
            "down": bool(state & KEY_PRESSED_MASK),
            "pressed": bool(state & KEY_WAS_PRESSED_MASK),
        }

    def trigger(self) -> None:
        if self.stopping.is_set() or self.done.is_set():
            return

        if time.monotonic() < self.armed_at:
            return

        self.alarm.start()

    def stop_and_exit(self) -> None:
        if self.stopping.is_set():
            return

        self.stopping.set()
        if self.native_hook_thread_id:
            windll.user32.PostThreadMessageW(self.native_hook_thread_id, 0x0012, 0, 0)
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
        self.alarm.stop()
        LoopingAlarm.force_stop_alias()
        self.done.set()

    def on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> bool | None:
        if self.stopping.is_set():
            return False

        stop_key = self.stop_key_name(key)
        if stop_key is not None:
            self.stop_and_exit()
            return False
            return None

        self.trigger()
        return None

    def on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        stop_key = self.stop_key_name(key)
        if stop_key is None:
            return

        with self.key_lock:
            self.pressed_stop_keys.discard(stop_key)

    def stop_key_name(self, key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if key == keyboard.Key.esc:
            return "esc"

        char = getattr(key, "char", None)
        vk = getattr(key, "vk", None)
        if (isinstance(char, str) and char.lower() == "s") or vk == VK_S:
            return "s"

        return None

    def record_stop_key_press(self, stop_key: str) -> bool:
        now = time.monotonic()
        with self.key_lock:
            self.pressed_stop_keys.add(stop_key)
            if stop_key == "esc":
                self.last_esc_press = now
            elif stop_key == "s":
                self.last_s_press = now

            both_down = "esc" in self.pressed_stop_keys and "s" in self.pressed_stop_keys
            recent_sequence = (
                self.last_esc_press > 0
                and self.last_s_press > 0
                and abs(self.last_esc_press - self.last_s_press) <= STOP_SEQUENCE_SECONDS
            )

        if both_down or recent_sequence:
            self.stop_and_exit()
            return True

        return False

    def on_mouse_move(self, x: int, y: int) -> None:
        if self.stopping.is_set():
            return

        now = time.monotonic()
        if now - self.last_mouse_move_trigger < MOUSE_MOVE_COOLDOWN_SECONDS:
            return
        self.last_mouse_move_trigger = now
        self.trigger()

    def on_mouse_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if self.stopping.is_set():
            return

        if pressed:
            self.trigger()

    def on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if self.stopping.is_set():
            return

        self.trigger()

    def close(self) -> None:
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
        self.alarm.stop()
        logging.info("Privacy alarm exited.")


class PrivacyAlarmWindow:
    def __init__(self, root: Tk, license_manager: LicenseManager) -> None:
        self.root = root
        self.license_manager = license_manager
        self.alarm: HiddenPrivacyAlarm | None = None
        self.alarm_thread: threading.Thread | None = None
        self.test_player: LoopingAlarm | None = None
        self.status_text = StringVar()
        self.status_detail = StringVar()
        self.hero_image: PhotoImage | None = None

        bg = "#08080d"
        panel = "#17131f"
        panel_hot = "#26131a"
        ink = "#fff7e8"
        muted = "#b9b4c6"
        yellow = "#ffe05d"
        orange = "#ff7a18"
        red = "#ff2f45"
        blue = "#00c8ff"

        self.root.title(APP_NAME)
        self.root.geometry("860x560")
        self.root.minsize(760, 520)
        self.root.configure(bg=bg)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind_all("<KeyPress-Escape>", self.emergency_stop_from_window)
        self.root.bind_all("<KeyPress-s>", self.emergency_stop_from_window)
        self.root.bind_all("<KeyPress-S>", self.emergency_stop_from_window)

        container = Frame(root, padx=26, pady=24, bg=bg)
        container.pack(fill=BOTH, expand=True)

        header = Frame(container, bg=bg)
        header.pack(fill="x", pady=(0, 18))

        mark = Label(
            header,
            text="KA",
            width=4,
            height=2,
            font=("Segoe UI", 11, "bold"),
            bg=orange,
            fg="#210806",
        )
        mark.pack(side="left", padx=(0, 12))

        title_block = Frame(header, bg=bg)
        title_block.pack(side="left", fill="x", expand=True)
        Label(title_block, text=APP_NAME, font=("Segoe UI", 22, "bold"), bg=bg, fg=ink).pack(anchor="w")
        Label(
            title_block,
            text="Touch My Laptop? Sairam Sairam.",
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg=yellow,
        ).pack(anchor="w", pady=(2, 0))

        hero = Frame(container, bg=bg)
        hero.pack(fill=BOTH, expand=True)

        left = Frame(hero, bg=bg)
        left.pack(side="left", fill=BOTH, expand=True, padx=(0, 18))

        Label(
            left,
            text="Your laptop's loudest bodyguard.",
            font=("Segoe UI", 28, "bold"),
            wraplength=370,
            justify="left",
            bg=bg,
            fg=ink,
        ).pack(anchor="w")
        Label(
            left,
            text="Activate Kunju before you walk away. Keyboard, mouse, touchpad, clicks, scrolls, and movement trigger the dramatic warning sound.",
            font=("Segoe UI", 10),
            wraplength=390,
            justify="left",
            bg=bg,
            fg=muted,
        ).pack(anchor="w", pady=(10, 18))

        status_card = Frame(left, padx=16, pady=14, bg=panel, highlightthickness=1, highlightbackground="#3b3348")
        status_card.pack(fill="x", pady=(0, 14))

        Label(status_card, textvariable=self.status_text, font=("Segoe UI", 12, "bold"), bg=panel, fg=yellow).pack(anchor="w")
        Label(status_card, textvariable=self.status_detail, font=("Segoe UI", 9), bg=panel, fg=muted).pack(anchor="w", pady=(5, 0))

        action_row = Frame(left, bg=bg)
        action_row.pack(anchor="w", fill="x", pady=(0, 8))

        self.start_button = self.make_button(
            action_row,
            "Start Protection",
            self.start_protection,
            bg=orange,
            fg="#210806",
            activebackground=red,
        )
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_button = Button(
            action_row,
            text="Stop & Exit",
            font=("Segoe UI", 10, "bold"),
            bg=panel_hot,
            fg=ink,
            activebackground=red,
            activeforeground=ink,
            disabledforeground="#756d82",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            height=2,
            command=self.emergency_stop,
            state=DISABLED,
        )
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.test_button = self.make_button(action_row, "Test Sound", self.test_sound, bg="#102a34", fg=ink, activebackground=blue)
        self.test_button.pack(side="left", fill="x", expand=True)

        license_card = Frame(left, padx=16, pady=14, bg=panel, highlightthickness=1, highlightbackground="#3b3348")
        license_card.pack(fill="x", pady=(14, 0))

        Label(license_card, text="License key", font=("Segoe UI", 9, "bold"), bg=panel, fg=ink).pack(anchor="w")
        self.license_entry = Entry(
            license_card,
            width=46,
            bg="#0d0c13",
            fg=ink,
            insertbackground=yellow,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#3b3348",
            highlightcolor=orange,
        )
        self.license_entry.pack(anchor="w", fill="x", pady=(6, 0), ipady=7)

        self.activate_button = self.make_button(
            license_card,
            "Activate License",
            self.activate_license,
            bg="#1a1822",
            fg=ink,
            activebackground=orange,
        )
        self.activate_button.pack(anchor="w", pady=(10, 4))

        Label(
            left,
            text="Emergency stop: press Esc or S. The app exits to guarantee the voice stops.",
            font=("Segoe UI", 8),
            wraplength=390,
            justify="left",
            bg=bg,
            fg=muted,
        ).pack(anchor="w", pady=(14, 0))

        preview = Frame(hero, bg=panel_hot, highlightthickness=1, highlightbackground="#493542")
        preview.pack(side="right", fill=BOTH, expand=True)
        self.hero_image = self.load_preview_image()
        if self.hero_image is not None:
            Label(preview, image=self.hero_image, bg=panel_hot).pack(fill=BOTH, expand=True)
        else:
            Label(
                preview,
                text="Kunju Is Watching!",
                font=("Segoe UI", 24, "bold"),
                wraplength=300,
                bg=panel_hot,
                fg=yellow,
            ).pack(fill=BOTH, expand=True, padx=20, pady=40)

        self.refresh_status()

    def make_button(
        self,
        parent: Frame,
        text: str,
        command,
        bg: str,
        fg: str,
        activebackground: str,
    ) -> Button:
        return Button(
            parent,
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg=fg,
            activebackground=activebackground,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            height=2,
            command=command,
        )

    def load_preview_image(self) -> PhotoImage | None:
        if not MASCOT_IMAGE.exists():
            return None

        image = PhotoImage(file=str(MASCOT_IMAGE))
        width = max(1, image.width() // 360)
        height = max(1, image.height() // 250)
        factor = max(width, height)
        if factor > 1:
            image = image.subsample(factor, factor)
        return image

    def refresh_status(self) -> None:
        protection = "running" if self.alarm_thread and self.alarm_thread.is_alive() else "stopped"
        self.status_text.set(f"License: {self.license_manager.status()}    Protection: {protection}")
        if protection == "running":
            self.status_detail.set("Kunju is armed. Touch, movement, keyboard, or mouse activity will trigger the alarm.")
        else:
            self.status_detail.set("Ready to guard. Click Start Protection before stepping away.")

    def start_protection(self) -> None:
        if self.alarm_thread and self.alarm_thread.is_alive():
            return

        if not self.license_manager.can_run():
            messagebox.showwarning(APP_NAME, "Trial expired. Activate a license to start protection.")
            return

        self.alarm = HiddenPrivacyAlarm(DEFAULT_SOUND)
        self.alarm_thread = threading.Thread(target=self.alarm.run, daemon=True)
        self.alarm_thread.start()
        self.start_button.config(state=DISABLED)
        self.stop_button.config(state=NORMAL)
        self.refresh_status()

    def stop_protection(self) -> None:
        if self.alarm is not None:
            self.alarm.stop_and_exit()
        if self.alarm_thread is not None:
            self.alarm_thread.join(timeout=1)
        self.alarm = None
        self.alarm_thread = None
        self.start_button.config(state=NORMAL)
        self.stop_button.config(state=DISABLED)
        self.refresh_status()

    def emergency_stop_from_window(self, _event=None) -> str:
        self.emergency_stop()
        return "break"

    def emergency_stop(self) -> None:
        self.stop_protection()
        if self.test_player is not None:
            self.test_player.stop()
            self.test_player = None
        LoopingAlarm.force_stop_alias()
        logging.info("Emergency stop requested from app window.")
        self.root.after(EMERGENCY_EXIT_DELAY_MS, self.force_exit)

    def force_exit(self) -> None:
        LoopingAlarm.force_stop_alias()
        os._exit(0)

    def test_sound(self) -> None:
        self.stop_test_sound()
        LoopingAlarm.close_alarm_alias()
        self.test_player = LoopingAlarm(DEFAULT_SOUND)
        self.test_player.start()
        self.root.after(2500, self.stop_test_sound)

    def stop_test_sound(self) -> None:
        if self.test_player is not None:
            self.test_player.stop()
            self.test_player = None

    def activate_license(self) -> None:
        key = self.license_entry.get().strip()
        if self.license_manager.activate(key):
            messagebox.showinfo(APP_NAME, "Kunju Alarm is activated.")
            self.license_entry.delete(0, "end")
        else:
            messagebox.showwarning(APP_NAME, "Activation failed. Check your license key.")
        self.refresh_status()

    def close(self) -> None:
        self.emergency_stop()
        self.root.destroy()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--activate", metavar="LICENSE_KEY", help="Activate a paid license key.")
    parser.add_argument("--hidden", action="store_true", help="Run the hidden alarm listener immediately.")
    parser.add_argument("--status", action="store_true", help="Print license status.")
    parser.add_argument("--allow-trial-expired", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    license_manager = LicenseManager()

    if args.activate:
        if license_manager.activate(args.activate):
            emit_user_message("Privacy Alarm is activated.")
            return 0
        emit_user_message("Activation failed. Check your license key.", warning=True)
        return 2

    if args.status:
        emit_user_message(f"License status: {license_manager.status()}")
        return 0

    if not args.allow_trial_expired and not license_manager.can_run():
        logging.warning("App blocked because trial expired.")
        emit_user_message(
            "Your Privacy Alarm trial has expired. Activate a paid license to keep using it.",
            warning=True,
        )
        return 3

    if not args.hidden:
        root = Tk()
        PrivacyAlarmWindow(root, license_manager)
        root.mainloop()
        return 0

    instance = SingleInstance()
    if instance.already_running:
        logging.info("Another privacy alarm instance is already running.")
        return 0

    try:
        HiddenPrivacyAlarm(DEFAULT_SOUND).run()
        return 0
    except Exception as exc:
        logging.exception("Fatal app error: %s", exc)
        return 1
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
