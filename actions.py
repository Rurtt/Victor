"""Small, explicit PC capability boundary. Model output is always untrusted."""
from __future__ import annotations

import ctypes
import ipaddress
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.parse import quote_plus, urlsplit
import webbrowser


class PolicyError(ValueError):
    pass


RULES = {
    "open_app": {"app": ("notepad", "calculator", "explorer", "spotify")},
    "open_folder": {"folder": ("documents", "downloads", "desktop", "notes")},
    "open_website": {"url": None},
    "search_web": {"query": None},
    "media": {"command": ("play_pause", "next_track", "previous_track", "volume_up", "volume_down", "mute")},
    "save_note": {"text": None},
    "control_screen": {"goal": None},
    "discord_send": {"target": None, "text": None},
}
# Bounded and easily undone, so these run without a confirmation click. Anything that
# reaches other people, opens an arbitrary target, or takes over the mouse and keyboard
# stays behind the approval dialog. This list is policy: the model never edits it.
AUTO_RUN = frozenset({"media", "open_app", "open_folder", "search_web"})
DISCORD_LINK = re.compile(r"https://discord\.com/channels/(@me|\d{1,20})/\d{1,20}")
DISCORD_PER_HOUR = 10
DISCORD_MAX = 1000


def validate(action: dict) -> dict:
    if not isinstance(action, dict) or set(action) != {"name", "arguments"}:
        raise PolicyError("Action must contain only name and arguments.")
    name, args = action["name"], action["arguments"]
    if not isinstance(name, str) or name not in RULES:
        raise PolicyError("This action is not permitted.")
    if not isinstance(args, dict) or set(args) != set(RULES[name]):
        raise PolicyError("Unexpected action arguments.")
    clean = {}
    for key, choices in RULES[name].items():
        value = args[key]
        if not isinstance(value, str) or not value.strip():
            raise PolicyError("Action arguments must be nonempty text.")
        if len(value) > (20000 if name == "save_note" else 2000):
            raise PolicyError("Action argument is too long.")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise PolicyError("Control characters are not allowed.")
        if choices is not None and value not in choices:
            raise PolicyError("That target is not on the permitted list.")
        clean[key] = value
    if name == "open_website":
        url = clean["url"]
        try:
            parts = urlsplit(url)
            host = parts.hostname or ""
            port = parts.port
        except ValueError as exc:
            raise PolicyError("Invalid website address.") from exc
        if (parts.scheme != "https" or parts.username is not None or
                parts.password is not None or port not in (None, 443) or
                not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host or
                any(c.isspace() for c in url) or "\\" in url or
                host.endswith((".local", ".localhost", ".internal", ".lan", ".home", "."))):
            raise PolicyError("Only public HTTPS website addresses are permitted.")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise PolicyError("IP-address URLs are not permitted.")
        if all(part.isdigit() for part in host.split(".")):
            raise PolicyError("Numeric hosts are not permitted.")
    if name == "discord_send":
        text = clean["text"]
        # A newline would press Enter mid-message in Discord.
        if len(text) > DISCORD_MAX or any(c in text for c in "\n\r\t"):
            raise PolicyError(f"ข้อความ Discord ต้องเป็นบรรทัดเดียว ไม่เกิน {DISCORD_MAX} ตัวอักษร")
        if "@everyone" in text or "@here" in text:
            raise PolicyError("ไม่อนุญาตให้ Victor ส่ง @everyone หรือ @here")
    return {"name": name, "arguments": clean}


def describe(action: dict) -> str:
    a = validate(action)
    name, args = a["name"], a["arguments"]
    if name == "open_app":
        return f"Open {args['app']}"
    if name == "open_folder":
        return f"Open the {args['folder']} folder"
    if name == "open_website":
        return "Open in your browser:\n" + args["url"]
    if name == "search_web":
        return "Search Google in your browser for:\n" + args["query"]
    if name == "media":
        return "Send media command: " + args["command"].replace("_", " ")
    if name == "control_screen":
        return ("ให้ Victor ดูหน้าจอหลักและทำงานนี้:\n" + args["goal"] +
                "\n\nภาพหน้าจอจะถูกส่งให้ Gemini ทุกขั้น และคุณต้องอนุญาตทุกคลิก")
    if name == "discord_send":
        return f"ส่งข้อความ Discord ในชื่อบัญชีของคุณ ถึง {args['target']}:\n\n{args['text']}"
    return "Create a new text file in Victor/notes:\n\n" + args["text"]


class ActionGate:
    """Pending actions can be run only via locally issued, single-use tickets.

    Tickets never enter the model context. The desktop UI calls approve only
    after its confirmation dialog returns Yes. This is an application boundary,
    not protection against another malicious process running as the same user.
    """
    def __init__(self, runner):
        self.runner = runner
        self.pending = {}

    def propose(self, action: dict) -> str:
        clean = validate(action)
        ticket = secrets.token_urlsafe(24)
        self.pending[ticket] = clean
        return ticket

    def approve(self, ticket: str):
        if ticket not in self.pending:
            raise PolicyError("Action expired or already handled.")
        action = self.pending.pop(ticket)
        return self.runner(validate(action))

    def reject(self, ticket: str):
        self.pending.pop(ticket, None)

    def clear(self):
        self.pending.clear()


class WindowsActions:
    def __init__(self, base: Path, screen_task=None):
        self.base = base.resolve()
        self.screen_task = screen_task
        self.discord_targets = {}
        self.discord_sent = []

    def send_discord(self, target: str, text: str) -> str:
        import screen
        link = self.discord_targets.get(target)
        if not link or not DISCORD_LINK.fullmatch(link):
            raise PolicyError(f"'{target}' ไม่อยู่ในรายชื่อ Discord ที่อนุญาต ยังไม่ได้ส่ง")
        now = time.monotonic()
        self.discord_sent = [t for t in self.discord_sent if now - t < 3600]
        if len(self.discord_sent) >= DISCORD_PER_HOUR:
            raise PolicyError(f"ถึงขีดจำกัด {DISCORD_PER_HOUR} ข้อความต่อชั่วโมงแล้ว ยังไม่ได้ส่ง")
        os.startfile(link.replace("https://discord.com/", "discord://-/", 1))
        # ponytail: fixed 3 s wait freezes the UI briefly; poll the window if Discord is slower.
        time.sleep(3)
        if not screen.foreground_exe().lower().endswith("discord.exe"):
            raise PolicyError("Discord ไม่ได้อยู่หน้าสุด ยังไม่ได้พิมพ์หรือส่งอะไร")
        screen.type_text(text)
        time.sleep(0.3)
        if not screen.foreground_exe().lower().endswith("discord.exe"):
            raise PolicyError("หน้าต่างเปลี่ยนระหว่างพิมพ์ ยังไม่ได้กด Enter ตรวจช่องข้อความ Discord")
        screen.press("enter")
        self.discord_sent.append(now)
        return f"ส่ง Discord ถึง {target} แล้ว: {text}"

    def __call__(self, action: dict) -> str:
        a = validate(action)
        name, args = a["name"], a["arguments"]
        system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        if name == "control_screen":
            if self.screen_task is None:
                raise PolicyError("Screen control is not available here.")
            self.screen_task(args["goal"])
            return "เริ่มควบคุมหน้าจอ: " + args["goal"]
        if name == "save_note":
            notes = self.base / "notes"
            notes.mkdir(exist_ok=True)
            if notes.is_symlink() or notes.is_junction() or notes.resolve().parent != self.base:
                raise PolicyError("Notes folder must stay inside Victor.")
            from datetime import datetime
            dest = notes / (datetime.now().strftime("%Y-%m-%d_%H%M%S_") + secrets.token_hex(3) + ".txt")
            with dest.open("x", encoding="utf-8") as f:
                f.write(args["text"])
            return f"Note saved: {dest}"
        if os.name != "nt":
            raise PolicyError("PC actions require Windows.")
        if name == "open_app":
            if args["app"] == "spotify":
                # The registered spotify: protocol starts the Store build and the desktop
                # installer alike, so no package id or install path is pinned here.
                os.startfile("spotify:")
                return "Sent to Windows: " + describe(a)
            apps = {"notepad": system / "System32/notepad.exe",
                    "calculator": system / "System32/calc.exe",
                    "explorer": system / "explorer.exe"}
            subprocess.Popen([str(apps[args["app"]])], shell=False)
        elif name == "open_folder":
            folders = {"documents": Path.home() / "Documents", "downloads": Path.home() / "Downloads",
                       "desktop": Path.home() / "Desktop", "notes": self.base / "notes"}
            folder = folders[args["folder"]]
            if not folder.is_dir():
                raise PolicyError("Folder does not exist yet (it may be redirected to OneDrive).")
            subprocess.Popen([str(system / "explorer.exe"), str(folder)], shell=False)
        elif name in ("open_website", "search_web"):
            url = args["url"] if name == "open_website" else "https://www.google.com/search?q=" + quote_plus(args["query"])
            if not webbrowser.open(url, new=2):
                raise PolicyError("Windows could not open the default browser.")
        elif name == "media":
            codes = {"play_pause": 0xB3, "next_track": 0xB0, "previous_track": 0xB1,
                     "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}
            key = codes[args["command"]]
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
        elif name == "discord_send":
            return self.send_discord(args["target"], args["text"])
        return "Sent to Windows: " + describe(a)
