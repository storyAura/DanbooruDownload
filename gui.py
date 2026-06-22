import sys
import threading
import queue
import time
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import customtkinter as ctk
from tkinter import filedialog, messagebox, font as tkfont

from config import Config, QueueTaskConfig
from danbooru_client import DanbooruClient
from formatter import DEFAULT_TAG_TEXT_CATEGORIES, TAG_TEXT_CATEGORY_ORDER, FilenameFormatter
from downloader import Downloader
from locales import I18N, RATING_MAP_ZH, RATING_MAP_EN

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DOWNLOAD_DIR = APP_DIR / "Download"
DEFAULT_FILENAME_FORMAT = "{artist}_{id}.{ext}"
VIDEO_EXTENSIONS = {"mp4", "webm", "zip"}
LOG_DIVIDER = "=" * 50
DEFAULT_SITE_URL = "https://danbooru.donmai.us"
SITE_PRESETS = {
    "Danbooru": DEFAULT_SITE_URL,
    "AIBooru": "https://aibooru.online",
    "Gelbooru": "https://gelbooru.com",
    "Safebooru": "https://safebooru.donmai.us",
}
CUSTOM_SITE_LABEL = "Custom"

ICONS = {
    "title": "",
    "appearance": "",
    "misc": "",
    "site": "",
    "search": "",
    "download": "",
    "queue": "",
    "progress": "",
    "log": "",
    "txt": "",
    "remove": "X",
    "video": "",
}

STATUS_ICONS = {
    "success": "OK",
    "error": "ERR",
    "skip": "SKIP",
    "cancel": "STOP",
    "speed": "SPD",
    "info": "INFO",
    "searching": "SEARCH",
}

LANGUAGE_LABELS = {
    "zh": "\u4e2d\u6587",
    "en": "English",
}
LANGUAGE_LABEL_TO_CODE = {label: code for code, label in LANGUAGE_LABELS.items()}

QUEUE_EMPTY_MESSAGES = {
    "zh": "\u961f\u5217\u4e3a\u7a7a\uff0c\u70b9\u51fb\u4e0a\u65b9\u6309\u94ae\u6dfb\u52a0\u4efb\u52a1",
    "en": "Queue is empty. Click the button above to add a task.",
}

MASK_CHAR = "\u2022"
FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial")
UI_FONT_FAMILY = FONT_CANDIDATES[0]
LOG_FONT_FAMILY = "Consolas"

FONT_SIZES = {
    "title": 20,
    "section": 14,
    "body": 13,
    "caption": 11,
    "button": 13,
}

COLORS = {
    "app_bg": "#F4F7F8",
    "panel": "#FFFFFF",
    "panel_alt": "#F8FBFB",
    "panel_hover": "#F1F7F7",
    "border": "#D8E4E5",
    "border_strong": "#B9CFD0",
    "accent": "#139A9A",
    "accent_hover": "#0F7F80",
    "accent_soft": "#E4F5F4",
    "success": "#2E9D62",
    "success_dark": "#247F4F",
    "success_soft": "#E7F6ED",
    "warning": "#C18413",
    "warning_soft": "#FFF4D8",
    "danger": "#D24B4B",
    "danger_hover": "#B43D3D",
    "danger_soft": "#FCE9E9",
    "text_primary": "#1D2B2E",
    "text_secondary": "#65777B",
    "text_muted": "#8EA0A4",
    "queue_item_bg": "#FFFFFF",
    "queue_item_hover": "#F1F7F7",
    "queue_item_border": "#D8E4E5",
    "running_glow": "#139A9A",
    "done_bg": "#F0FAF4",
    "failed_bg": "#FFF1F1",
}


def resolve_ui_font() -> str:
    try:
        available = set(tkfont.families())
    except Exception:
        return UI_FONT_FAMILY
    for family in FONT_CANDIDATES:
        if family in available:
            return family
    return FONT_CANDIDATES[-1]


def ui_font(size: int | str = "body", weight: str | None = None, family: str | None = None) -> ctk.CTkFont:
    if isinstance(size, str):
        size = FONT_SIZES[size]
    kwargs = {"family": family or UI_FONT_FAMILY, "size": size}
    if weight:
        kwargs["weight"] = weight
    return ctk.CTkFont(**kwargs)


def button_style(kind: str = "secondary") -> dict:
    base = {
        "height": 34,
        "corner_radius": 8,
        "font": ui_font("button", "bold"),
    }
    if kind == "primary":
        return {
            **base,
            "fg_color": COLORS["accent"],
            "hover_color": COLORS["accent_hover"],
            "text_color": "#FFFFFF",
        }
    if kind == "success":
        return {
            **base,
            "fg_color": COLORS["success"],
            "hover_color": COLORS["success_dark"],
            "text_color": "#FFFFFF",
        }
    if kind == "danger":
        return {
            **base,
            "fg_color": COLORS["danger"],
            "hover_color": COLORS["danger_hover"],
            "text_color": "#FFFFFF",
        }
    return {
        **base,
        "fg_color": COLORS["panel_alt"],
        "hover_color": COLORS["panel_hover"],
        "border_width": 1,
        "border_color": COLORS["border"],
        "text_color": COLORS["text_primary"],
    }


class CardFrame(ctk.CTkFrame):
    def __init__(self, parent, title: str, icon: str = "", **kwargs):
        kwargs.setdefault("fg_color", COLORS["panel"])
        super().__init__(
            parent,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 2))
        label_text = f"{icon}  {title}" if icon else title
        self._title_label = ctk.CTkLabel(
            header, text=label_text,
            font=ui_font("section", "bold"),
            text_color=COLORS["text_primary"],
        )
        self._title_label.pack(side="left")
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16, pady=(6, 16))

    def set_title(self, title: str, icon: str = ""):
        self._title_label.configure(text=f"{icon}  {title}" if icon else title)


@dataclass
class QueueItem:
    tags: str = ""
    folder_name: str = ""
    max_posts: int = 100
    status: str = "waiting"  # waiting, running, done, failed, cancelled
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0


class QueueItemWidget(ctk.CTkFrame):
    """A single queue item row with animations."""

    def __init__(self, parent, index: int, item: QueueItem, t: dict,
                 on_remove=None, on_retry=None, can_edit=None, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color=COLORS["queue_item_border"],
                         fg_color=COLORS["queue_item_bg"], **kwargs)
        self._item = item
        self._index = index
        self._on_remove = on_remove
        self._on_retry = on_retry
        self._can_edit = can_edit
        self.t = t
        self._target_alpha = 1.0

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(10, 8))

        self._badge = ctk.CTkLabel(
            row, text=f"#{index + 1}", width=38, height=24,
            corner_radius=6, fg_color=COLORS["accent_soft"],
            text_color=COLORS["accent"],
            font=ui_font("caption", "bold"),
        )
        self._badge.pack(side="left", padx=(0, 8))

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        tags_display = item.tags if len(item.tags) < 50 else item.tags[:47] + "..."
        self._lbl_tags = ctk.CTkLabel(
            info, text=f"{t['queue_item_tags']}: {tags_display}",
            font=ui_font("body", "bold"), anchor="w",
            text_color=COLORS["text_primary"],
        )
        self._lbl_tags.pack(anchor="w")

        folder_display = item.folder_name or "Download/"
        sub_text = (
            f"{t['queue_item_folder']}: {folder_display}  |  "
            f"{t['queue_item_max']}: {item.max_posts}"
        )
        self._lbl_sub = ctk.CTkLabel(
            info, text=sub_text,
            font=ui_font("caption"), text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._lbl_sub.pack(anchor="w")

        self._lbl_status = ctk.CTkLabel(
            row, text=self._status_text(),
            font=ui_font("caption", "bold"), width=96, height=24,
            corner_radius=12, fg_color=COLORS["panel_alt"],
            text_color=COLORS["text_secondary"],
        )
        self._lbl_status.pack(side="left", padx=4)

        self._btn_retry = ctk.CTkButton(
            row, text=t["queue_retry"], width=58, height=28, corner_radius=8,
            fg_color=COLORS["accent_soft"], border_width=0,
            hover_color=COLORS["panel_hover"], text_color=COLORS["accent"],
            font=ui_font("caption", "bold"),
            command=self._do_retry,
        )
        self._btn_retry.pack(side="right", padx=(0, 6))

        self._btn_remove = ctk.CTkButton(
            row, text=ICONS["remove"], width=30, height=28, corner_radius=8,
            fg_color=COLORS["panel_alt"], hover_color=COLORS["danger_soft"],
            text_color=COLORS["text_secondary"],
            font=ui_font(14, "bold"),
            command=self._do_remove,
        )
        self._btn_remove.pack(side="right")

        self._mini_progress = ctk.CTkProgressBar(
            self, height=5, corner_radius=3,
            progress_color=COLORS["accent"],
        )
        self._mini_progress.set(0)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._sync_action_buttons()

    def _status_text(self) -> str:
        t = self.t
        status_map = {
            "waiting": t["queue_status_waiting"],
            "running": t["queue_status_running"],
            "done": t["queue_status_done"],
            "failed": t["queue_status_failed"],
            "cancelled": t["queue_status_cancelled"],
        }
        return status_map.get(self._item.status, self._item.status)

    def update_status(self, status: str, t: dict = None):
        if t:
            self.t = t
            self._btn_retry.configure(text=self.t["queue_retry"])
        self._item.status = status
        self._lbl_status.configure(text=self._status_text())

        if status == "waiting":
            self.configure(border_color=COLORS["queue_item_border"],
                           fg_color=COLORS["queue_item_bg"])
            self._badge.configure(fg_color=COLORS["accent_soft"], text_color=COLORS["accent"])
            self._lbl_status.configure(fg_color=COLORS["panel_alt"], text_color=COLORS["text_secondary"])
            self._mini_progress.pack_forget()
            self._mini_progress.set(0)
        elif status == "running":
            self._mini_progress.pack(fill="x", padx=12, pady=(0, 6))
            self.configure(border_color=COLORS["running_glow"])
            self._badge.configure(fg_color=COLORS["warning_soft"], text_color=COLORS["warning"])
            self._lbl_status.configure(fg_color=COLORS["accent_soft"], text_color=COLORS["accent"])
        elif status == "done":
            self._mini_progress.set(1.0)
            self.configure(border_color=COLORS["success"],
                           fg_color=COLORS["done_bg"])
            self._badge.configure(fg_color=COLORS["success_soft"], text_color=COLORS["success"])
            self._lbl_status.configure(fg_color=COLORS["success_soft"], text_color=COLORS["success"])
        elif status == "failed":
            self.configure(border_color=COLORS["danger"],
                           fg_color=COLORS["failed_bg"])
            self._badge.configure(fg_color=COLORS["danger_soft"], text_color=COLORS["danger"])
            self._lbl_status.configure(fg_color=COLORS["danger_soft"], text_color=COLORS["danger"])
        elif status == "cancelled":
            self.configure(border_color=COLORS["danger"])
            self._badge.configure(fg_color=COLORS["panel_alt"], text_color=COLORS["text_muted"])
            self._lbl_status.configure(fg_color=COLORS["panel_alt"], text_color=COLORS["text_muted"])

        self._sync_action_buttons()

    def update_progress(self, downloaded, skipped, failed, total):
        self._item.downloaded = downloaded
        self._item.skipped = skipped
        self._item.failed = failed
        self._item.total = total
        done = downloaded + skipped + failed
        ratio = done / total if total else 0
        self._mini_progress.set(ratio)

    def _do_remove(self):
        if self._on_remove:
            self._on_remove(self._index)

    def _do_retry(self):
        if self._on_retry:
            self._on_retry(self._index)

    def _can_edit_items(self) -> bool:
        if callable(self._can_edit):
            return bool(self._can_edit())
        return True

    def _sync_action_buttons(self):
        can_edit = self._can_edit_items()
        retry_enabled = can_edit and self._item.status in {"done", "failed", "cancelled"}
        remove_enabled = can_edit and self._item.status != "running"

        self._btn_retry.configure(
            state="normal" if retry_enabled else "disabled",
            fg_color=COLORS["accent_soft"] if retry_enabled else COLORS["panel_alt"],
            border_width=0,
            text_color=COLORS["accent"] if retry_enabled else COLORS["text_secondary"],
            hover=retry_enabled,
            hover_color=COLORS["panel_hover"],
        )
        self._btn_remove.configure(
            state="normal" if remove_enabled else "disabled",
            text_color=COLORS["text_secondary"] if remove_enabled else COLORS["queue_item_border"],
            fg_color=COLORS["panel_alt"],
            hover=remove_enabled,
            hover_color=COLORS["danger_soft"],
        )

    def _on_enter(self, _e):
        if self._item.status == "waiting":
            self.configure(fg_color=COLORS["queue_item_hover"])

    def _on_leave(self, _e):
        if self._item.status == "waiting":
            self.configure(fg_color=COLORS["queue_item_bg"])

    def animate_in(self, delay_ms: int = 0):
        self.configure(fg_color=COLORS["queue_item_bg"])
        if delay_ms > 0:
            self.after(delay_ms, self._do_animate_in)
        else:
            self._do_animate_in()

    def _do_animate_in(self):
        self._anim_step = 0
        self._run_anim_in()

    def _run_anim_in(self):
        if not self.winfo_exists():
            return
        self._anim_step += 1
        if self._anim_step <= 6:
            self.after(25, self._run_anim_in)


class SettingsDialog(ctk.CTkToplevel):

    def __init__(self, parent, lang: str, on_theme_change, on_lang_change):
        super().__init__(parent)
        self._lang = lang
        self._on_lang_change = on_lang_change
        self._on_theme_change = on_theme_change
        self.t = I18N[lang]
        self.title(self.t["settings_title"])
        self.geometry("400x340")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["app_bg"])
        self.transient(parent)
        self.attributes("-alpha", 0.0)
        self._build_content()
        self.after(30, self._fade_in, 0.0)

    def _build_content(self):
        card_appear = CardFrame(self, self.t["appearance"])
        card_appear.pack(fill="x", padx=16, pady=(16, 8))
        c = card_appear.content

        row_theme = ctk.CTkFrame(c, fg_color="transparent")
        row_theme.pack(fill="x", pady=4)
        ctk.CTkLabel(
            row_theme, text=self.t["theme"], width=70, anchor="w",
            font=ui_font("body"), text_color=COLORS["text_secondary"],
        ).pack(side="left")
        self.theme_var = ctk.StringVar(
            value=self.t["theme_dark"] if ctk.get_appearance_mode() == "Dark" else self.t["theme_light"]
        )
        ctk.CTkSegmentedButton(
            row_theme,
            values=[self.t["theme_dark"], self.t["theme_light"]],
            variable=self.theme_var,
            font=ui_font("body"),
            command=self._do_theme_switch,
        ).pack(side="left", padx=(8, 0))

        row_lang = ctk.CTkFrame(c, fg_color="transparent")
        row_lang.pack(fill="x", pady=4)
        ctk.CTkLabel(
            row_lang, text=self.t["language"], width=70, anchor="w",
            font=ui_font("body"), text_color=COLORS["text_secondary"],
        ).pack(side="left")
        self.lang_var = ctk.StringVar(value=LANGUAGE_LABELS[self._lang])
        ctk.CTkSegmentedButton(
            row_lang,
            values=list(LANGUAGE_LABELS.values()),
            variable=self.lang_var,
            font=ui_font("body"),
            command=self._do_lang_switch,
        ).pack(side="left", padx=(8, 0))

        card_misc = CardFrame(self, self.t["misc"])
        card_misc.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(
            card_misc.content, text=self.t["misc_desc"],
            font=ui_font("body"), text_color=COLORS["text_secondary"],
        ).pack(anchor="w")

        ctk.CTkButton(
            self, text=self.t["close"], width=100,
            command=self._fade_out_and_close, **button_style("primary"),
        ).pack(pady=(8, 16))

    def _fade_in(self, alpha: float):
        if not self.winfo_exists():
            return
        alpha = min(alpha + 0.12, 1.0)
        self.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.after(16, self._fade_in, alpha)
        else:
            try:
                self.grab_set()
                self.focus_force()
            except Exception:
                pass

    def _fade_out_and_close(self):
        self._fade_out(1.0, callback=self.destroy)

    def _fade_out(self, alpha: float, callback=None):
        if not self.winfo_exists():
            return
        alpha = max(alpha - 0.15, 0.0)
        self.attributes("-alpha", alpha)
        if alpha > 0.0:
            self.after(16, self._fade_out, alpha, callback)
        else:
            if callback:
                callback()

    def _do_theme_switch(self, val):
        mode = "dark" if val == self.t["theme_dark"] else "light"
        try:
            self.grab_release()
        except Exception:
            pass
        parent = self.master
        on_change = self._on_theme_change

        def _after_close():
            try:
                self.destroy()
            except Exception:
                pass
            parent.after(50, lambda: on_change(mode))

        self._fade_out(1.0, callback=_after_close)

    def _do_lang_switch(self, val):
        lang = LANGUAGE_LABEL_TO_CODE.get(val, "en")
        try:
            self.grab_release()
        except Exception:
            pass
        parent = self.master
        on_change = self._on_lang_change

        def _after_close():
            try:
                self.destroy()
            except Exception:
                pass
            parent.after(50, lambda: on_change(lang))

        self._fade_out(1.0, callback=_after_close)

class DanbooruGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        global UI_FONT_FAMILY
        UI_FONT_FAMILY = resolve_ui_font()
        self._lang = "zh"
        self.t = I18N[self._lang]
        self.title(self.t["title"])
        self.geometry("1500x820")
        self.minsize(1280, 720)
        self.configure(fg_color=COLORS["app_bg"])
        self._msg_queue: queue.Queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._download_thread: threading.Thread | None = None
        self._queue_items: list[QueueItem] = []
        self._queue_widgets: list[QueueItemWidget] = []
        self._queue_running = False
        self._current_queue_index = -1
        self._current_speed_str = ""
        self.site_preset_popup = None
        self.site_preset_popup_frame = None
        self.rating_popup = None
        self.rating_popup_frame = None
        self._build_ui()
        self._poll_queue()

    @property
    def _rating_map(self):
        return RATING_MAP_ZH if self._lang == "zh" else RATING_MAP_EN

    @property
    def _rating_rev(self):
        return {v: k for k, v in self._rating_map.items()}

    def _queue_empty_text(self) -> str:
        return QUEUE_EMPTY_MESSAGES.get(self._lang, QUEUE_EMPTY_MESSAGES["en"])

    def _site_label_for_url(self, url: str) -> str:
        normalized = (url or "").rstrip("/")
        for label, preset_url in SITE_PRESETS.items():
            if normalized == preset_url.rstrip("/"):
                return label
        return CUSTOM_SITE_LABEL

    def _set_site_url(self, url: str):
        self.var_url.delete(0, "end")
        self.var_url.insert(0, url)

    def _set_site_preset_label(self, label: str):
        self.var_site_preset.set(label)
        if hasattr(self, "btn_site_preset"):
            self.btn_site_preset.configure(text=label)

    def _on_site_preset_change(self, label: str):
        self._set_site_preset_label(label)
        url = SITE_PRESETS.get(label)
        if url:
            self._set_site_url(url)
        self._hide_site_preset_menu()

    def _on_site_url_edit(self, _event=None):
        current_label = self._site_label_for_url(self._get_entry_text(self.var_url))
        if self.var_site_preset.get() != current_label:
            self._set_site_preset_label(current_label)

    def _toggle_site_preset_menu(self):
        if self.site_preset_popup and self.site_preset_popup.winfo_viewable():
            self._hide_site_preset_menu()
        else:
            self._show_site_preset_menu()

    def _show_site_preset_menu(self):
        if not self.site_preset_popup:
            self.site_preset_popup = ctk.CTkToplevel(self)
            self.site_preset_popup.withdraw()
            self.site_preset_popup.overrideredirect(True)
            self.site_preset_popup.transient(self)
            self.site_preset_popup.configure(fg_color=COLORS["panel"])
            self.site_preset_popup.bind("<Escape>", lambda _event: self._hide_site_preset_menu())
            self.site_preset_popup.bind("<FocusOut>", lambda _event: self._hide_site_preset_menu())
            self.site_preset_popup_frame = ctk.CTkFrame(
                self.site_preset_popup,
                fg_color=COLORS["panel"],
                corner_radius=8,
                border_width=1,
                border_color=COLORS["border"],
            )
            self.site_preset_popup_frame.pack(fill="both", expand=True)
            options = list(SITE_PRESETS.keys()) + [CUSTOM_SITE_LABEL]
            for index, label in enumerate(options):
                option = ctk.CTkButton(
                    self.site_preset_popup_frame,
                    text=label,
                    anchor="w",
                    height=34,
                    corner_radius=6,
                    fg_color="transparent",
                    hover_color=COLORS["panel_hover"],
                    text_color=COLORS["text_primary"],
                    font=ui_font("body", "bold" if index == 0 else "normal"),
                    command=lambda value=label: self._on_site_preset_change(value),
                )
                option.pack(fill="x", padx=6, pady=(6 if index == 0 else 0, 6))

        self.update_idletasks()
        width = max(self.btn_site_preset.winfo_width(), 180)
        height = 34 * (len(SITE_PRESETS) + 1) + 42
        x = self.btn_site_preset.winfo_rootx()
        y = self.btn_site_preset.winfo_rooty() + self.btn_site_preset.winfo_height() + 4
        self.site_preset_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.site_preset_popup.deiconify()
        self.site_preset_popup.lift()
        self.site_preset_popup.focus_force()

    def _hide_site_preset_menu(self):
        if self.site_preset_popup:
            self.site_preset_popup.withdraw()

    def _set_rating_label(self, label: str):
        self.var_rating.set(label)
        if hasattr(self, "btn_rating"):
            self.btn_rating.configure(text=label)

    def _on_rating_change(self, label: str):
        self._set_rating_label(label)
        self._hide_rating_menu()

    def _toggle_rating_menu(self):
        if self.rating_popup and self.rating_popup.winfo_viewable():
            self._hide_rating_menu()
        else:
            self._show_rating_menu()

    def _show_rating_menu(self):
        if not self.rating_popup:
            self.rating_popup = ctk.CTkToplevel(self)
            self.rating_popup.withdraw()
            self.rating_popup.overrideredirect(True)
            self.rating_popup.transient(self)
            self.rating_popup.configure(fg_color=COLORS["panel"])
            self.rating_popup.bind("<Escape>", lambda _event: self._hide_rating_menu())
            self.rating_popup.bind("<FocusOut>", lambda _event: self._hide_rating_menu())
            self.rating_popup_frame = ctk.CTkFrame(
                self.rating_popup,
                fg_color=COLORS["panel"],
                corner_radius=8,
                border_width=1,
                border_color=COLORS["border"],
            )
            self.rating_popup_frame.pack(fill="both", expand=True)
            for index, label in enumerate(self.t["rating_options"]):
                option = ctk.CTkButton(
                    self.rating_popup_frame,
                    text=label,
                    anchor="w",
                    height=34,
                    corner_radius=6,
                    fg_color="transparent",
                    hover_color=COLORS["panel_hover"],
                    text_color=COLORS["text_primary"],
                    font=ui_font("body", "bold" if index == 0 else "normal"),
                    command=lambda value=label: self._on_rating_change(value),
                )
                option.pack(fill="x", padx=6, pady=(6 if index == 0 else 0, 6))

        self.update_idletasks()
        width = max(self.btn_rating.winfo_width(), 180)
        height = 34 * len(self.t["rating_options"]) + 42
        x = self.btn_rating.winfo_rootx()
        y = self.btn_rating.winfo_rooty() + self.btn_rating.winfo_height() + 4
        self.rating_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.rating_popup.deiconify()
        self.rating_popup.lift()
        self.rating_popup.focus_force()

    def _hide_rating_menu(self):
        if self.rating_popup:
            self.rating_popup.withdraw()

    def _reset_rating_menu(self):
        if self.rating_popup:
            self.rating_popup.destroy()
            self.rating_popup = None
            self.rating_popup_frame = None

    def _build_ui(self):
        t = self.t
        top = ctk.CTkFrame(self, fg_color=COLORS["app_bg"])
        top.pack(fill="x", padx=24, pady=(18, 10))
        self._lbl_title = ctk.CTkLabel(
            top, text=t["title"],
            font=ui_font("title", "bold"),
            text_color=COLORS["text_primary"],
        )
        self._lbl_title.pack(side="left")

        btn_group = ctk.CTkFrame(top, fg_color="transparent")
        btn_group.pack(side="right")
        self.btn_settings = ctk.CTkButton(
            btn_group, text=t["settings"], width=88,
            command=self._open_settings, **button_style("primary"),
        )
        self.btn_settings.pack(side="left", padx=(0, 8))
        self.btn_import = ctk.CTkButton(
            btn_group, text=t["import_config"], width=98,
            command=self._load_config, **button_style("secondary"),
        )
        self.btn_import.pack(side="left", padx=(0, 8))
        self.btn_export = ctk.CTkButton(
            btn_group, text=t["export_config"], width=98,
            command=self._save_config, **button_style("secondary"),
        )
        self.btn_export.pack(side="left")

        main = ctk.CTkFrame(self, fg_color=COLORS["app_bg"])
        main.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        main.grid_columnconfigure(0, minsize=500, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, minsize=340, weight=0)
        main.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(
            main,
            fg_color="transparent",
            width=500,
            scrollbar_button_color=COLORS["border_strong"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._scroll = left

        center = ctk.CTkFrame(main, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=0)
        center.grid_rowconfigure(0, weight=0)
        center.grid_rowconfigure(1, weight=0)
        center.grid_rowconfigure(2, weight=0)
        center.grid_rowconfigure(3, weight=1)
        center.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(main, fg_color="transparent", width=340)
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        def form_row(parent, label_text, entry):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, 12))
            label = ctk.CTkLabel(
                row, text=label_text,
                anchor="w", font=ui_font("body"), text_color=COLORS["text_secondary"],
            )
            label.pack(fill="x", anchor="w", pady=(0, 5))
            entry.pack(fill="x")
            return label

        self.card_site = CardFrame(left, t["site_settings"])
        self.card_site.pack(fill="x", pady=(0, 12))
        c = self.card_site.content
        site_row = ctk.CTkFrame(c, fg_color="transparent")
        site_row.pack(fill="x", pady=(0, 12))
        self._lbl_site_preset = ctk.CTkLabel(
            site_row, text=t["site_preset"],
            anchor="w", font=ui_font("body"), text_color=COLORS["text_secondary"],
        )
        self._lbl_site_preset.pack(fill="x", anchor="w", pady=(0, 5))
        self.var_site_preset = ctk.StringVar(value="Danbooru")
        self.btn_site_preset = ctk.CTkButton(
            site_row,
            text="Danbooru",
            anchor="w",
            command=self._toggle_site_preset_menu,
            **button_style("secondary"),
        )
        self.btn_site_preset.pack(fill="x")
        self.var_url = ctk.CTkEntry(
            c, placeholder_text=DEFAULT_SITE_URL,
            height=34, corner_radius=8, border_color=COLORS["border"],
            fg_color=COLORS["panel_alt"], font=ui_font("body"),
            text_color=COLORS["text_primary"],
        )
        self._lbl_url = form_row(c, t["site_url"], self.var_url)
        self.var_url.insert(0, DEFAULT_SITE_URL)
        self._set_site_preset_label("Danbooru")
        self.var_url.bind("<KeyRelease>", self._on_site_url_edit)
        self.var_username = ctk.CTkEntry(
            c, placeholder_text=t["optional"], height=34, corner_radius=8,
            border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self._lbl_user = form_row(c, t["username"], self.var_username)
        self.var_apikey = ctk.CTkEntry(
            c, placeholder_text=t["optional"], show=MASK_CHAR, height=34,
            corner_radius=8, border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self._lbl_apikey = form_row(c, t["api_key"], self.var_apikey)

        self.card_search = CardFrame(left, t["search_settings"])
        self.card_search.pack(fill="x", pady=(0, 12))
        c = self.card_search.content
        self.var_tags = ctk.CTkEntry(
            c, placeholder_text=t["search_tags_hint"], height=34, corner_radius=8,
            border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self._lbl_tags = form_row(c, t["search_tags"], self.var_tags)
        self.var_blocked = ctk.CTkEntry(
            c, placeholder_text=t["blocked_tags_hint"], height=34, corner_radius=8,
            border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self._lbl_blocked = form_row(c, t["blocked_tags"], self.var_blocked)

        filter_row = ctk.CTkFrame(c, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 12))
        self._lbl_rating = ctk.CTkLabel(
            filter_row, text=t["rating"],
            anchor="w", font=ui_font("body"), text_color=COLORS["text_secondary"],
        )
        self._lbl_rating.pack(fill="x", anchor="w", pady=(0, 5))
        self.var_rating = ctk.StringVar(value=t["rating_options"][0])
        self.btn_rating = ctk.CTkButton(
            filter_row,
            text=t["rating_options"][0],
            anchor="w",
            command=self._toggle_rating_menu,
            **button_style("secondary"),
        )
        self.btn_rating.pack(fill="x")
        score_row = ctk.CTkFrame(c, fg_color="transparent")
        score_row.pack(fill="x", pady=(0, 12))
        self._lbl_minscore = ctk.CTkLabel(
            score_row, text=t["min_score"],
            anchor="w", font=ui_font("body"), text_color=COLORS["text_secondary"],
        )
        self._lbl_minscore.pack(fill="x", anchor="w", pady=(0, 5))
        self.var_min_score = ctk.CTkEntry(
            score_row, placeholder_text=t["min_score_hint"], height=34,
            corner_radius=8, border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self.var_min_score.pack(fill="x")

        self.card_dl = CardFrame(left, t["download_settings"])
        self.card_dl.pack(fill="x", pady=(0, 12))
        c = self.card_dl.content
        self.var_folder_name = ctk.CTkEntry(
            c, placeholder_text=t["folder_name_hint"], height=34, corner_radius=8,
            border_color=COLORS["border"], fg_color=COLORS["panel_alt"],
            font=ui_font("body"), text_color=COLORS["text_primary"],
        )
        self._lbl_folder = form_row(c, t["folder_name"], self.var_folder_name)
        self.lbl_path_preview = ctk.CTkLabel(
            c, text=t["save_path_label"] + str(DEFAULT_DOWNLOAD_DIR) + "/",
            font=ui_font("caption"), text_color=COLORS["text_muted"],
            wraplength=430, justify="left",
        )
        self.lbl_path_preview.pack(anchor="w", pady=(0, 8))

        def _update_path_preview(*_args):
            sub = self.var_folder_name.get().strip()
            preview = str(DEFAULT_DOWNLOAD_DIR / sub) if sub else str(DEFAULT_DOWNLOAD_DIR)
            self.lbl_path_preview.configure(text=self.t["save_path_label"] + preview + "/")

        self.var_folder_name.bind("<KeyRelease>", _update_path_preview)

        row_fn = ctk.CTkFrame(c, fg_color="transparent")
        row_fn.pack(fill="x", pady=(8, 4))
        self.var_custom_name = ctk.CTkCheckBox(
            row_fn, text=t["custom_filename"], command=self._toggle_custom_name,
            font=ui_font("body"), text_color=COLORS["text_primary"],
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            border_color=COLORS["border_strong"],
        )
        self.var_custom_name.pack(side="left")

        row_fmt = ctk.CTkFrame(c, fg_color="transparent")
        row_fmt.pack(fill="x", pady=4)
        self._lbl_fmt = ctk.CTkLabel(
            row_fmt, text=t["filename_format"],
            anchor="w", font=ui_font("body"), text_color=COLORS["text_secondary"],
        )
        self._lbl_fmt.pack(fill="x", anchor="w", pady=(0, 5))
        self.entry_filename = ctk.CTkEntry(
            row_fmt, placeholder_text=DEFAULT_FILENAME_FORMAT, state="disabled",
            height=34, corner_radius=8, border_color=COLORS["border"],
            fg_color=COLORS["panel_alt"], font=ui_font("body"),
            text_color=COLORS["text_primary"],
        )
        self.entry_filename.pack(fill="x", pady=(0, 8))
        self.btn_placeholder = ctk.CTkButton(
            row_fmt, text=t["placeholder_info"], width=92,
            command=lambda: messagebox.showinfo(t["placeholder_info"], t["placeholder_help"]),
            **button_style("secondary"),
        )
        self.btn_placeholder.pack(anchor="w")
        self.lbl_fmt_hint = ctk.CTkLabel(
            c, text=t["default_format"] + DEFAULT_FILENAME_FORMAT,
            font=ui_font("caption"), text_color=COLORS["text_muted"],
            wraplength=430, justify="left",
        )
        self.lbl_fmt_hint.pack(anchor="w", pady=(0, 8))

        row_nums = ctk.CTkFrame(c, fg_color="transparent")
        row_nums.pack(fill="x", pady=4)
        self._lbl_max = ctk.CTkLabel(row_nums, text=t["max_downloads"], anchor="w", font=ui_font("caption"), text_color=COLORS["text_secondary"])
        self._lbl_max.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._lbl_conc = ctk.CTkLabel(row_nums, text=t["concurrent"], anchor="w", font=ui_font("caption"), text_color=COLORS["text_secondary"])
        self._lbl_conc.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self._lbl_timeout = ctk.CTkLabel(row_nums, text=t["timeout_sec"], anchor="w", font=ui_font("caption"), text_color=COLORS["text_secondary"])
        self._lbl_timeout.grid(row=0, column=2, sticky="w")
        row_nums.grid_columnconfigure((0, 1, 2), weight=1, uniform="nums")
        self.var_max_posts = ctk.CTkEntry(row_nums, placeholder_text="100", height=34, corner_radius=8, border_color=COLORS["border"], fg_color=COLORS["panel_alt"], font=ui_font("body"))
        self.var_max_posts.insert(0, "100")
        self.var_max_posts.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 0))
        self.var_concurrent = ctk.CTkEntry(row_nums, placeholder_text="8", height=34, corner_radius=8, border_color=COLORS["border"], fg_color=COLORS["panel_alt"], font=ui_font("body"))
        self.var_concurrent.insert(0, "8")
        self.var_concurrent.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(4, 0))
        self.var_timeout = ctk.CTkEntry(row_nums, placeholder_text="30", height=34, corner_radius=8, border_color=COLORS["border"], fg_color=COLORS["panel_alt"], font=ui_font("body"))
        self.var_timeout.insert(0, "30")
        self.var_timeout.grid(row=1, column=2, sticky="ew", pady=(4, 0))

        row_opts = ctk.CTkFrame(c, fg_color="transparent")
        row_opts.pack(fill="x", pady=(10, 0))
        self.var_skip_existing = ctk.CTkCheckBox(
            row_opts, text=t["skip_existing"], font=ui_font("body"),
            text_color=COLORS["text_primary"], fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], border_color=COLORS["border_strong"],
        )
        self.var_skip_existing.select()
        self.var_skip_existing.pack(side="left")

        row_video = ctk.CTkFrame(c, fg_color="transparent")
        row_video.pack(fill="x", pady=(4, 0))
        self.var_download_video = ctk.CTkCheckBox(
            row_video, text=t["download_video"], font=ui_font("body"),
            text_color=COLORS["text_primary"], fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], border_color=COLORS["border_strong"],
        )
        self.var_download_video.pack(side="left")

        row_txt = ctk.CTkFrame(c, fg_color="transparent")
        row_txt.pack(fill="x", pady=(10, 0))
        self.var_save_tag_txt = ctk.CTkCheckBox(
            row_txt, text=t["save_tag_txt"], font=ui_font("body"),
            text_color=COLORS["text_primary"], fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], border_color=COLORS["border_strong"],
            command=self._sync_tag_txt_controls,
        )
        self.var_save_tag_txt.pack(side="left")
        self.lbl_txt_hint = ctk.CTkLabel(
            c, text=t["tag_txt_hint"],
            font=ui_font("caption"), text_color=COLORS["text_muted"],
            wraplength=430, justify="left",
        )
        self.lbl_txt_hint.pack(anchor="w", pady=(0, 8))

        self._tag_txt_vars: dict[str, ctk.CTkCheckBox] = {}
        self.tag_txt_frame = ctk.CTkFrame(c, fg_color="transparent")
        self.tag_txt_frame.pack(fill="x", pady=(0, 2))
        for col in range(3):
            self.tag_txt_frame.grid_columnconfigure(col, weight=1, uniform="tag_txt")
        for index, category in enumerate(TAG_TEXT_CATEGORY_ORDER):
            checkbox = ctk.CTkCheckBox(
                self.tag_txt_frame,
                text=t[f"tag_category_{category}"],
                width=120,
                font=ui_font("caption"),
                text_color=COLORS["text_primary"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                border_color=COLORS["border_strong"],
            )
            if category in DEFAULT_TAG_TEXT_CATEGORIES:
                checkbox.select()
            checkbox.grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 10), pady=4)
            self._tag_txt_vars[category] = checkbox

        self.tag_txt_options_frame = ctk.CTkFrame(c, fg_color="transparent")
        self.tag_txt_options_frame.pack(fill="x", pady=(4, 2))
        self.tag_txt_options_frame.grid_columnconfigure(0, weight=1)
        self.tag_txt_options_frame.grid_columnconfigure(1, weight=1)
        self.var_tag_txt_underscore_to_space = ctk.CTkCheckBox(
            self.tag_txt_options_frame,
            text=t["tag_txt_underscore_to_space"],
            font=ui_font("caption"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border_strong"],
        )
        self.var_tag_txt_underscore_to_space.select()
        self.var_tag_txt_underscore_to_space.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self.var_tag_txt_escape_special_chars = ctk.CTkCheckBox(
            self.tag_txt_options_frame,
            text=t["tag_txt_escape_special_chars"],
            font=ui_font("caption"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["border_strong"],
        )
        self.var_tag_txt_escape_special_chars.select()
        self.var_tag_txt_escape_special_chars.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=4)
        self._sync_tag_txt_controls()

        self.card_queue = CardFrame(center, t["queue_title"])
        self.card_queue.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.card_queue.configure(height=320)
        self.card_queue.grid_propagate(False)
        cq = self.card_queue.content
        queue_btns = ctk.CTkFrame(cq, fg_color="transparent")
        queue_btns.pack(fill="x", pady=(0, 8))
        self.btn_queue_add = ctk.CTkButton(
            queue_btns, text=t["queue_add"], width=150,
            command=self._add_to_queue, **button_style("primary"),
        )
        self.btn_queue_add.pack(side="left", padx=(0, 8))
        self.btn_queue_clear = ctk.CTkButton(
            queue_btns, text=t["queue_clear"], width=104,
            command=self._clear_queue, **button_style("secondary"),
        )
        self.btn_queue_clear.pack(side="left")
        self._queue_list_frame = ctk.CTkScrollableFrame(
            cq, fg_color=COLORS["panel_alt"], corner_radius=8,
            border_width=1, border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border_strong"],
            scrollbar_button_hover_color=COLORS["accent"],
            height=210,
        )
        self._queue_list_frame.pack(fill="x", expand=False)
        self._lbl_queue_empty = ctk.CTkLabel(
            self._queue_list_frame, text=self._queue_empty_text(),
            text_color=COLORS["text_secondary"], font=ui_font("body"),
        )
        self._lbl_queue_empty.pack(pady=24)

        self.card_actions = CardFrame(center, t["download_settings"])
        self.card_actions.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        action_frame = ctk.CTkFrame(self.card_actions.content, fg_color="transparent")
        action_frame.pack(fill="x")
        self.btn_start = ctk.CTkButton(
            action_frame, text=t["start_download"], width=120,
            command=self._start_download, **button_style("primary"),
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_queue_start = ctk.CTkButton(
            action_frame, text=t["queue_start_all"], width=120,
            command=self._start_queue, **button_style("success"),
        )
        self.btn_queue_start.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_stop = ctk.CTkButton(
            action_frame, text=t["stop_download"], width=100,
            state="disabled", command=self._stop_download, **button_style("danger"),
        )
        self.btn_stop.pack(side="left", fill="x", expand=True)

        self.card_prog = CardFrame(center, t["progress"])
        self.card_prog.grid(row=2, column=0, sticky="ew")
        c = self.card_prog.content
        self.progress = ctk.CTkProgressBar(c, height=12, corner_radius=6, progress_color=COLORS["accent"])
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(0, 8))
        stats_row = ctk.CTkFrame(c, fg_color="transparent")
        stats_row.pack(fill="x")
        self.lbl_stats = ctk.CTkLabel(
            stats_row, text=t["ready"], font=ui_font("body"), text_color=COLORS["text_secondary"]
        )
        self.lbl_stats.pack(side="left")
        self.lbl_speed = ctk.CTkLabel(stats_row, text="", font=ui_font("body", "bold"), text_color=COLORS["accent"])
        self.lbl_speed.pack(side="right")

        log_toolbar = ctk.CTkFrame(right, fg_color="transparent")
        log_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._lbl_log_title = ctk.CTkLabel(
            log_toolbar, text=t["log"],
            font=ui_font("section", "bold"), text_color=COLORS["text_primary"],
        )
        self._lbl_log_title.pack(side="left")
        self.btn_clear = ctk.CTkButton(
            log_toolbar, text=t["clear_log"], width=100,
            command=self._clear_log, **button_style("secondary"),
        )
        self.btn_clear.pack(side="right")

        self.card_log = CardFrame(right, t["log"], icon="")
        self.card_log.grid(row=1, column=0, sticky="nsew")
        self.txt_log = ctk.CTkTextbox(
            self.card_log.content,
            font=ui_font("caption", family=LOG_FONT_FAMILY),
            corner_radius=8,
            fg_color=COLORS["panel_alt"],
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            state="disabled",
        )
        self.txt_log.pack(fill="both", expand=True)

    def _add_to_queue(self):
        tags = self._get_entry_text(self.var_tags)
        if not tags:
            messagebox.showwarning(self.t["hint"], self.t["queue_no_tags_warn"])
            return
        folder = self._get_entry_text(self.var_folder_name)
        try:
            max_posts = int(self._get_entry_text(self.var_max_posts) or "100")
        except ValueError:
            max_posts = 100

        item = QueueItem(tags=tags, folder_name=folder, max_posts=max_posts)
        self._queue_items.append(item)
        self._rebuild_queue_list()

        folder_display = folder or "Download/"
        self._log_message(self.t["queue_added_fmt"].format(tags=tags, folder=folder_display))

    def _remove_from_queue(self, index: int):
        if self._queue_running:
            return
        if 0 <= index < len(self._queue_items):
            item = self._queue_items[index]
            if item.status == "running":
                return
            self._queue_items.pop(index)
            self._rebuild_queue_list()

    def _clear_queue(self):
        if self._queue_running:
            return
        self._queue_items.clear()
        self._rebuild_queue_list()

    @staticmethod
    def _reset_queue_item(item: QueueItem):
        item.status = "waiting"
        item.downloaded = 0
        item.skipped = 0
        item.failed = 0
        item.total = 0

    def _retry_queue_item(self, index: int):
        if self._queue_running:
            return
        if not (0 <= index < len(self._queue_items)):
            return

        item = self._queue_items[index]
        if item.status not in {"done", "failed", "cancelled"}:
            return

        self._reset_queue_item(item)
        self._rebuild_queue_list()
        self._log_message(self.t["queue_retrying_fmt"].format(tags=item.tags))
        self._start_queue_items([index])

    def _rebuild_queue_list(self):
        for w in self._queue_widgets:
            w.destroy()
        self._queue_widgets.clear()

        if not self._queue_items:
            self._lbl_queue_empty.pack(pady=12)
            return

        self._lbl_queue_empty.pack_forget()
        for i, item in enumerate(self._queue_items):
            w = QueueItemWidget(
                self._queue_list_frame, i, item, self.t,
                on_remove=self._remove_from_queue,
                on_retry=self._retry_queue_item,
                can_edit=lambda: not self._queue_running,
            )
            w.pack(fill="x", pady=2)
            if item.status != "waiting":
                w.update_status(item.status)
            self._queue_widgets.append(w)
            if len(self._queue_items) <= 20:
                w.animate_in(delay_ms=i * 25)

    def _start_queue(self):
        waiting = [i for i, item in enumerate(self._queue_items) if item.status == "waiting"]
        if not waiting:
            messagebox.showwarning(self.t["hint"], self.t["queue_empty_warn"])
            return
        self._start_queue_items(waiting)

    def _start_queue_items(self, task_indices: list[int]):
        if self._queue_running or not task_indices:
            return

        self._queue_running = True
        self._cancel_event.clear()
        self.progress.set(0)
        self.lbl_stats.configure(text=self.t["searching"])
        self.lbl_speed.configure(text="")
        self._set_buttons_running(True)
        self._rebuild_queue_list()

        def _queue_worker():
            total_tasks = len(task_indices)
            for task_num, idx in enumerate(task_indices, 1):
                if self._cancel_event.is_set():
                    for remaining_idx in task_indices[task_num - 1:]:
                        if 0 <= remaining_idx < len(self._queue_items):
                            self._queue_items[remaining_idx].status = "cancelled"
                    self._msg_queue.put(("rebuild_queue", None))
                    break

                if not (0 <= idx < len(self._queue_items)):
                    continue

                item = self._queue_items[idx]
                item.status = "running"
                self._current_queue_index = idx
                self._msg_queue.put(("rebuild_queue", None))
                self._log_message("")
                self._log_message(self.t["queue_task_start_fmt"].format(n=task_num, total=total_tasks))
                self._log_message(f"Tags: {item.tags}")
                self._log_message(f"Folder: {item.folder_name or 'Download/'}")
                self._log_message(f"Max: {item.max_posts}")
                self._log_message("")

                try:
                    result = self._execute_single_task(item)
                    item.status = "cancelled" if result == "cancelled" else "done"
                except Exception as e:
                    self._log_message(f"Error: {e}")
                    item.status = "failed"

                self._msg_queue.put(("rebuild_queue", None))
                self._log_message(self.t["queue_task_done_fmt"].format(n=task_num, total=total_tasks))

                if not self._cancel_event.is_set() and task_num < total_tasks:
                    time.sleep(1)

            self._current_queue_index = -1
            self._queue_running = False
            self._msg_queue.put(("rebuild_queue", None))
            if not self._cancel_event.is_set():
                self._log_message("")
                self._log_message(self.t["queue_all_done"])
            self._msg_queue.put(("done", "queue_done"))

        self._download_thread = threading.Thread(target=_queue_worker, daemon=True)
        self._download_thread.start()

    def _execute_single_task(self, item: QueueItem) -> str:
        config = self._build_config()
        config.tags = item.tags
        config.save_dir = str(DEFAULT_DOWNLOAD_DIR / item.folder_name) if item.folder_name else str(DEFAULT_DOWNLOAD_DIR)
        config.max_posts = item.max_posts

        tags_query = config.build_tags_query()
        download_video = bool(self.var_download_video.get())

        self._log_message("Searching posts...")
        with DanbooruClient(
            base_url=config.base_url, username=config.username,
            api_key=config.api_key, timeout=config.timeout,
        ) as client:
            posts = list(client.search_all(tags=tags_query, max_posts=config.max_posts, on_log=self._log_message))

        if self._cancel_event.is_set():
            return "cancelled"

        if not download_video:
            before = len(posts)
            posts = [p for p in posts if (p.get("file_ext", "") or "").lower() not in VIDEO_EXTENSIONS]
            skipped_video = before - len(posts)
            if skipped_video:
                self._log_message(f"Filtered out {skipped_video} video/animation posts")

        self._log_message(f"Found {len(posts)} downloadable posts")
        if not posts:
            self._log_message("No matching posts.")
            return "no_results"

        formatter = FilenameFormatter(config.filename_format)

        def _item_progress(downloaded, skipped, failed, total):
            item.downloaded = downloaded
            item.skipped = skipped
            item.failed = failed
            item.total = total
            self._update_progress(downloaded, skipped, failed, total)
            self._msg_queue.put(("queue_item_progress", (self._current_queue_index, downloaded, skipped, failed, total)))

        dl = Downloader(
            save_dir=config.save_dir, formatter=formatter,
            max_concurrent=config.concurrent_downloads,
            skip_existing=config.skip_existing, timeout=config.timeout,
            on_progress=_item_progress, on_log=self._log_message,
            on_speed=self._update_speed, cancel_event=self._cancel_event,
            save_tag_txt=config.save_tag_txt,
            tag_txt_categories=config.tag_txt_categories,
            tag_txt_underscore_to_space=config.tag_txt_underscore_to_space,
            tag_txt_escape_special_chars=config.tag_txt_escape_special_chars,
        )
        dl.download_batch(posts)

        self._log_message(
            f"Downloaded: {dl.downloaded}  "
            f"Skipped: {dl.skipped}  "
            f"Failed: {dl.failed}"
        )
        if self._cancel_event.is_set():
            return "cancelled"
        return "success"

    def _open_settings(self):
        SettingsDialog(self, self._lang, self._on_theme_change, self._on_lang_change)

    def _on_theme_change(self, mode: str):
        ctk.set_appearance_mode(mode)

    def _on_lang_change(self, lang: str):
        if lang == self._lang:
            return
        old_rating_val = self._rating_map.get(self.var_rating.get(), "")
        self._lang = lang
        self.t = I18N[lang]
        self._update_texts(old_rating_val)
        self._rebuild_queue_list()

    def _update_texts(self, old_rating_val: str = ""):
        t = self.t
        self.title(t["title"])
        self._lbl_title.configure(text=t["title"])
        self.btn_settings.configure(text=t["settings"])
        self.btn_import.configure(text=t["import_config"])
        self.btn_export.configure(text=t["export_config"])
        self.card_site.set_title(t["site_settings"])
        self._lbl_site_preset.configure(text=t["site_preset"])
        self._lbl_url.configure(text=t["site_url"])
        self._lbl_user.configure(text=t["username"])
        self._lbl_apikey.configure(text=t["api_key"])
        self.card_search.set_title(t["search_settings"])
        self._lbl_tags.configure(text=t["search_tags"])
        self._lbl_blocked.configure(text=t["blocked_tags"])
        self._lbl_rating.configure(text=t["rating"])
        self._lbl_minscore.configure(text=t["min_score"])
        new_rev = self._rating_rev
        self._reset_rating_menu()
        self._set_rating_label(new_rev.get(old_rating_val, t["rating_options"][0]))
        self.card_dl.set_title(t["download_settings"])
        self.card_actions.set_title(t["download_settings"])
        self._lbl_folder.configure(text=t["folder_name"])
        self._lbl_fmt.configure(text=t["filename_format"])
        self.var_custom_name.configure(text=t["custom_filename"])
        self.btn_placeholder.configure(text=t["placeholder_info"])
        self._lbl_max.configure(text=t["max_downloads"])
        self._lbl_conc.configure(text=t["concurrent"])
        self._lbl_timeout.configure(text=t["timeout_sec"])
        self.var_skip_existing.configure(text=t["skip_existing"])
        self.var_download_video.configure(text=t["download_video"])
        self.var_save_tag_txt.configure(text=t["save_tag_txt"])
        self.lbl_txt_hint.configure(text=t["tag_txt_hint"])
        for category, checkbox in self._tag_txt_vars.items():
            checkbox.configure(text=t[f"tag_category_{category}"])
        self.var_tag_txt_underscore_to_space.configure(text=t["tag_txt_underscore_to_space"])
        self.var_tag_txt_escape_special_chars.configure(text=t["tag_txt_escape_special_chars"])
        sub = self.var_folder_name.get().strip()
        preview = str(DEFAULT_DOWNLOAD_DIR / sub) if sub else str(DEFAULT_DOWNLOAD_DIR)
        self.lbl_path_preview.configure(text=t["save_path_label"] + preview + "/")
        if self.var_custom_name.get():
            self.lbl_fmt_hint.configure(text=t["custom_format_hint"])
        else:
            self.lbl_fmt_hint.configure(text=t["default_format"] + DEFAULT_FILENAME_FORMAT)
        self.card_queue.set_title(t["queue_title"])
        self._lbl_queue_empty.configure(text=self._queue_empty_text())
        self.btn_queue_add.configure(text=t["queue_add"])
        self.btn_queue_clear.configure(text=t["queue_clear"])
        self.btn_start.configure(text=t["start_download"])
        self.btn_queue_start.configure(text=t["queue_start_all"])
        self.btn_stop.configure(text=t["stop_download"])
        self.btn_clear.configure(text=t["clear_log"])
        self.card_prog.set_title(t["progress"])
        self.card_log.set_title(t["log"])
        self._lbl_log_title.configure(text=t["log"])

    def _sync_tag_txt_controls(self):
        state = "normal" if self.var_save_tag_txt.get() else "disabled"
        for checkbox in self._tag_txt_vars.values():
            checkbox.configure(state=state)
        self.var_tag_txt_underscore_to_space.configure(state=state)
        self.var_tag_txt_escape_special_chars.configure(state=state)

    def _toggle_custom_name(self):
        if self.var_custom_name.get():
            self.entry_filename.configure(state="normal")
            self.entry_filename.delete(0, "end")
            self.entry_filename.insert(0, DEFAULT_FILENAME_FORMAT)
            self.lbl_fmt_hint.configure(text=self.t["custom_format_hint"])
        else:
            self.entry_filename.configure(state="normal")
            self.entry_filename.delete(0, "end")
            self.entry_filename.configure(state="disabled")
            self.lbl_fmt_hint.configure(text=self.t["default_format"] + DEFAULT_FILENAME_FORMAT)

    def _clear_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _get_entry_text(self, entry: ctk.CTkEntry) -> str:
        return entry.get().strip()

    def _get_save_dir(self) -> str:
        sub = self._get_entry_text(self.var_folder_name)
        return str(DEFAULT_DOWNLOAD_DIR / sub) if sub else str(DEFAULT_DOWNLOAD_DIR)

    def _build_config(self) -> Config:
        rating_val = self._rating_map.get(self.var_rating.get(), "")
        min_score = None
        s = self._get_entry_text(self.var_min_score)
        if s:
            try:
                min_score = int(s)
            except ValueError:
                pass
        try:
            max_posts = int(self._get_entry_text(self.var_max_posts) or "100")
        except ValueError:
            max_posts = 100
        try:
            concurrent = int(self._get_entry_text(self.var_concurrent) or "8")
        except ValueError:
            concurrent = 8
        try:
            timeout = float(self._get_entry_text(self.var_timeout) or "30")
        except ValueError:
            timeout = 30.0
        if self.var_custom_name.get():
            fmt = self._get_entry_text(self.entry_filename) or DEFAULT_FILENAME_FORMAT
        else:
            fmt = DEFAULT_FILENAME_FORMAT
        return Config(
            base_url=self._get_entry_text(self.var_url) or DEFAULT_SITE_URL,
            username=self._get_entry_text(self.var_username) or None,
            api_key=self._get_entry_text(self.var_apikey) or None,
            tags=self._get_entry_text(self.var_tags),
            blocked_tags=self._get_entry_text(self.var_blocked),
            rating=rating_val or None, min_score=min_score,
            save_dir=self._get_save_dir(), filename_format=fmt,
            max_posts=max_posts, concurrent_downloads=concurrent,
            skip_existing=bool(self.var_skip_existing.get()), timeout=timeout,
            save_tag_txt=bool(self.var_save_tag_txt.get()),
            tag_txt_categories=[
                category
                for category in TAG_TEXT_CATEGORY_ORDER
                if self._tag_txt_vars[category].get()
            ],
            tag_txt_underscore_to_space=bool(self.var_tag_txt_underscore_to_space.get()),
            tag_txt_escape_special_chars=bool(self.var_tag_txt_escape_special_chars.get()),
            queue_tasks=[
                QueueTaskConfig(
                    tags=item.tags,
                    folder_name=item.folder_name,
                    max_posts=item.max_posts,
                )
                for item in self._queue_items
            ],
        )

    def _apply_config(self, config: Config):
        def _set(entry, val):
            entry.configure(state="normal")
            entry.delete(0, "end")
            if val:
                entry.insert(0, val)
        _set(self.var_url, config.base_url)
        self._set_site_preset_label(self._site_label_for_url(config.base_url))
        _set(self.var_username, config.username or "")
        _set(self.var_apikey, config.api_key or "")
        _set(self.var_tags, config.tags)
        _set(self.var_blocked, config.blocked_tags)
        self._set_rating_label(self._rating_rev.get(config.rating or "", self.t["rating_options"][0]))
        _set(self.var_min_score, str(config.min_score) if config.min_score is not None else "")
        save_str = config.save_dir.replace("\\", "/")
        dl_prefix = str(DEFAULT_DOWNLOAD_DIR).replace("\\", "/") + "/"
        if save_str.startswith(dl_prefix):
            _set(self.var_folder_name, save_str[len(dl_prefix):])
        else:
            _set(self.var_folder_name, "")
        _set(self.var_max_posts, str(config.max_posts))
        _set(self.var_concurrent, str(config.concurrent_downloads))
        _set(self.var_timeout, str(config.timeout))
        if config.skip_existing:
            self.var_skip_existing.select()
        else:
            self.var_skip_existing.deselect()
        if config.save_tag_txt:
            self.var_save_tag_txt.select()
        else:
            self.var_save_tag_txt.deselect()
        if config.tag_txt_underscore_to_space:
            self.var_tag_txt_underscore_to_space.select()
        else:
            self.var_tag_txt_underscore_to_space.deselect()
        if config.tag_txt_escape_special_chars:
            self.var_tag_txt_escape_special_chars.select()
        else:
            self.var_tag_txt_escape_special_chars.deselect()
        selected_tag_categories = set(config.tag_txt_categories)
        for category, checkbox in self._tag_txt_vars.items():
            if category in selected_tag_categories:
                checkbox.select()
            else:
                checkbox.deselect()
        self._sync_tag_txt_controls()
        is_custom = config.filename_format != DEFAULT_FILENAME_FORMAT
        if is_custom:
            self.var_custom_name.select()
        else:
            self.var_custom_name.deselect()
        self._toggle_custom_name()
        if is_custom:
            _set(self.entry_filename, config.filename_format)
        self._queue_items = [
            QueueItem(
                tags=task.tags,
                folder_name=task.folder_name,
                max_posts=task.max_posts,
            )
            for task in config.queue_tasks
        ]
        self._current_queue_index = -1
        self._rebuild_queue_list()

    def _load_config(self):
        t = self.t
        path = filedialog.askopenfilename(
            title=t["select_config"],
            filetypes=[(t["yaml_files"], "*.yaml *.yml"), (t["all_files"], "*.*")],
        )
        if not path:
            return
        try:
            config = Config.from_yaml(path)
            self._apply_config(config)
            self._log_message(f"Imported config: {path}")
        except Exception as e:
            messagebox.showerror(t["import_fail"], t["import_fail_msg"].format(e))

    def _save_config(self):
        t = self.t
        path = filedialog.asksaveasfilename(
            title=t["save_config_title"], defaultextension=".yaml",
            filetypes=[(t["yaml_files"], "*.yaml *.yml")],
        )
        if not path:
            return
        try:
            config = self._build_config()
            config.to_yaml(path)
            self._log_message(f"Config saved: {path}")
        except Exception as e:
            messagebox.showerror(t["export_fail"], t["export_fail_msg"].format(e))

    def _log_message(self, msg: str):
        self._msg_queue.put(("log", msg))

    def _update_progress(self, downloaded: int, skipped: int, failed: int, total: int):
        self._msg_queue.put(("progress", (downloaded, skipped, failed, total)))

    def _update_speed(self, bytes_per_sec: float):
        if bytes_per_sec >= 1024 * 1024:
            speed_str = f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif bytes_per_sec >= 1024:
            speed_str = f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            speed_str = f"{bytes_per_sec:.0f} B/s"
        self._msg_queue.put(("speed", speed_str))

    def _set_buttons_running(self, running: bool):
        if running:
            self.btn_start.configure(state="disabled")
            self.btn_queue_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_queue_add.configure(state="disabled")
            self.btn_queue_clear.configure(state="disabled")
        else:
            self.btn_start.configure(state="normal")
            self.btn_queue_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.btn_queue_add.configure(state="normal")
            self.btn_queue_clear.configure(state="normal")

    def _poll_queue(self):
        log_messages: list[str] = []
        try:
            while True:
                kind, data = self._msg_queue.get_nowait()
                if kind == "log":
                    log_messages.append(data)
                elif kind == "progress":
                    downloaded, skipped, failed, total = data
                    done = downloaded + skipped + failed
                    ratio = done / total if total else 0
                    self.progress.set(ratio)
                    self.lbl_stats.configure(
                        text=self.t["stats_fmt"].format(dl=downloaded, sk=skipped, fa=failed, to=total)
                    )
                elif kind == "speed":
                    self.lbl_speed.configure(text=data)
                elif kind == "rebuild_queue":
                    self._rebuild_queue_list()
                elif kind == "queue_item_progress":
                    idx, downloaded, skipped, failed, total = data
                    if 0 <= idx < len(self._queue_widgets):
                        self._queue_widgets[idx].update_progress(downloaded, skipped, failed, total)
                elif kind == "done":
                    self._on_download_finished(data)
        except queue.Empty:
            pass
        if log_messages:
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", "\n".join(log_messages) + "\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        self.after(80, self._poll_queue)

    def _start_download(self):
        config = self._build_config()
        tags_query = config.build_tags_query()
        if not tags_query.strip():
            messagebox.showwarning(self.t["hint"], self.t["no_tags_warn"])
            return

        download_video = bool(self.var_download_video.get())
        video_status = "on" if download_video else "off"
        self._cancel_event.clear()
        self.progress.set(0)
        self.lbl_stats.configure(text=self.t["searching"])
        self.lbl_speed.configure(text="")
        self._set_buttons_running(True)

        self._log_message(LOG_DIVIDER)
        self._log_message(f"Tags: {tags_query}")
        self._log_message(f"Site: {config.base_url}")
        self._log_message(f"Save: {Path(config.save_dir).resolve()}")
        self._log_message(f"Format: {config.filename_format}")
        self._log_message(f"Max: {config.max_posts}  |  Concurrent: {config.concurrent_downloads}")
        self._log_message(f"Video: {video_status}")
        txt_status = ", ".join(config.tag_txt_categories) if config.save_tag_txt else "off"
        if config.save_tag_txt:
            txt_options = []
            if config.tag_txt_underscore_to_space:
                txt_options.append("underscore-to-space")
            if config.tag_txt_escape_special_chars:
                txt_options.append("escape-special-chars")
            if txt_options:
                txt_status = f"{txt_status} ({', '.join(txt_options)})"
        self._log_message(f"TXT: {txt_status}")
        self._log_message(LOG_DIVIDER)
        self._log_message("")

        def _worker():
            try:
                self._log_message("Searching posts...")
                with DanbooruClient(
                    base_url=config.base_url, username=config.username,
                    api_key=config.api_key, timeout=config.timeout,
                ) as client:
                    posts = list(client.search_all(tags=tags_query, max_posts=config.max_posts, on_log=self._log_message))

                if self._cancel_event.is_set():
                    self._msg_queue.put(("done", "cancelled"))
                    return

                if not download_video:
                    before = len(posts)
                    posts = [p for p in posts if (p.get("file_ext", "") or "").lower() not in VIDEO_EXTENSIONS]
                    skipped_video = before - len(posts)
                    if skipped_video:
                        self._log_message(f"Filtered out {skipped_video} video/animation posts")

                self._log_message(f"Found {len(posts)} downloadable posts")
                if not posts:
                    self._log_message("No matching posts.")
                    self._msg_queue.put(("done", "no_results"))
                    return

                self._log_message("")
                formatter = FilenameFormatter(config.filename_format)
                dl = Downloader(
                    save_dir=config.save_dir, formatter=formatter,
                    max_concurrent=config.concurrent_downloads,
                    skip_existing=config.skip_existing, timeout=config.timeout,
                    on_progress=self._update_progress, on_log=self._log_message,
                    on_speed=self._update_speed, cancel_event=self._cancel_event,
                    save_tag_txt=config.save_tag_txt,
                    tag_txt_categories=config.tag_txt_categories,
                    tag_txt_underscore_to_space=config.tag_txt_underscore_to_space,
                    tag_txt_escape_special_chars=config.tag_txt_escape_special_chars,
                )
                stats = dl.download_batch(posts)
                self._log_message("")
                self._log_message(LOG_DIVIDER)
                self._log_message(f"Downloaded: {stats['downloaded']}")
                self._log_message(f"Skipped: {stats['skipped']}")
                if stats["failed"]:
                    self._log_message(f"Failed: {stats['failed']}")
                self._log_message(f"Saved: {Path(config.save_dir).resolve()}")
                self._log_message(LOG_DIVIDER)
                self._msg_queue.put(("done", "success"))
            except Exception as e:
                self._log_message(f"\nError: {e}")
                self._msg_queue.put(("done", "error"))

        self._download_thread = threading.Thread(target=_worker, daemon=True)
        self._download_thread.start()

    def _stop_download(self):
        self._cancel_event.set()
        self._log_message("Stopping download...")
        self.btn_stop.configure(state="disabled")

    def _on_download_finished(self, result: str):
        self._set_buttons_running(False)
        self.lbl_speed.configure(text="")
        t = self.t
        if result == "cancelled":
            self._log_message("Download cancelled.")
            self.lbl_stats.configure(text=t["cancelled"])
        elif result == "no_results":
            self.lbl_stats.configure(text=t["no_results"])
        elif result == "error":
            self.lbl_stats.configure(text=t["error_status"])
        elif result == "queue_done":
            self.lbl_stats.configure(text=t.get("queue_all_done", t["done"]))
        else:
            self.lbl_stats.configure(text=t["done"])

def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = DanbooruGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
