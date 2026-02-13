import sys
import threading
import queue
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import customtkinter as ctk
from tkinter import filedialog, messagebox

from config import Config
from danbooru_client import DanbooruClient
from formatter import FilenameFormatter
from downloader import Downloader
from locales import I18N, RATING_MAP_ZH, RATING_MAP_EN

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DOWNLOAD_DIR = APP_DIR / "Download"
DEFAULT_FILENAME_FORMAT = "{artist}_{id}.{ext}"
VIDEO_EXTENSIONS = {"mp4", "webm", "zip"}

COLORS = {
    "accent": "#6C63FF",
    "accent_hover": "#5A52D5",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "danger": "#E74C3C",
    "text_secondary": "#A0A0A0",
}


class CardFrame(ctk.CTkFrame):

    def __init__(self, parent, title: str, icon: str = "", **kwargs):
        super().__init__(parent, corner_radius=12, border_width=1,
                         border_color=("gray75", "gray30"), **kwargs)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        label_text = f"{icon}  {title}" if icon else title
        self._title_label = ctk.CTkLabel(
            header, text=label_text,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._title_label.pack(side="left")
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="x", padx=16, pady=(4, 14))

    def set_title(self, title: str, icon: str = ""):
        self._title_label.configure(text=f"{icon}  {title}" if icon else title)


class SettingsDialog(ctk.CTkToplevel):

    def __init__(self, parent, lang: str, on_theme_change, on_lang_change):
        super().__init__(parent)
        self._on_lang_change = on_lang_change
        self._on_theme_change = on_theme_change
        self.t = I18N[lang]
        self.title(self.t["settings_title"])
        self.geometry("400x340")
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-alpha", 0.0)
        self._build_content()
        self.after(30, self._fade_in, 0.0)

    def _build_content(self):
        card_appear = CardFrame(self, self.t["appearance"], icon="🎨")
        card_appear.pack(fill="x", padx=16, pady=(16, 8))
        c = card_appear.content

        row_theme = ctk.CTkFrame(c, fg_color="transparent")
        row_theme.pack(fill="x", pady=4)
        ctk.CTkLabel(row_theme, text=self.t["theme"], width=70, anchor="w").pack(side="left")
        self.theme_var = ctk.StringVar(
            value=self.t["theme_dark"] if ctk.get_appearance_mode() == "Dark" else self.t["theme_light"]
        )
        ctk.CTkSegmentedButton(
            row_theme,
            values=[self.t["theme_dark"], self.t["theme_light"]],
            variable=self.theme_var,
            command=self._do_theme_switch,
        ).pack(side="left", padx=(8, 0))

        row_lang = ctk.CTkFrame(c, fg_color="transparent")
        row_lang.pack(fill="x", pady=4)
        ctk.CTkLabel(row_lang, text=self.t["language"], width=70, anchor="w").pack(side="left")
        self.lang_var = ctk.StringVar(value="中文" if self.t is I18N["zh"] else "English")
        ctk.CTkSegmentedButton(
            row_lang,
            values=["中文", "English"],
            variable=self.lang_var,
            command=self._do_lang_switch,
        ).pack(side="left", padx=(8, 0))

        card_misc = CardFrame(self, self.t["misc"], icon="🔧")
        card_misc.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(
            card_misc.content, text=self.t["misc_desc"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w")

        ctk.CTkButton(
            self, text=self.t["close"], width=100,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._fade_out_and_close,
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
        lang = "zh" if val == "中文" else "en"
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
        self._lang = "zh"
        self.t = I18N[self._lang]
        self.title(self.t["title"])
        self.geometry("820x920")
        self.minsize(720, 750)
        self._msg_queue: queue.Queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._download_thread: threading.Thread | None = None
        self._i18n_widgets: list = []
        self._build_ui()
        self._poll_queue()

    @property
    def _rating_map(self):
        return RATING_MAP_ZH if self._lang == "zh" else RATING_MAP_EN

    @property
    def _rating_rev(self):
        return {v: k for k, v in self._rating_map.items()}

    def _build_ui(self):
        t = self.t

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 4))

        self._lbl_title = ctk.CTkLabel(
            top, text="🎨 " + t["title"],
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self._lbl_title.pack(side="left")

        btn_group = ctk.CTkFrame(top, fg_color="transparent")
        btn_group.pack(side="right")

        self.btn_settings = ctk.CTkButton(
            btn_group, text=t["settings"], width=80, height=30,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=12),
            command=self._open_settings,
        )
        self.btn_settings.pack(side="left", padx=4)

        self.btn_import = ctk.CTkButton(
            btn_group, text=t["import_config"], width=90, height=30,
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray40"),
            hover_color=("gray85", "gray30"),
            text_color=("gray20", "gray80"),
            font=ctk.CTkFont(size=12),
            command=self._load_config,
        )
        self.btn_import.pack(side="left", padx=4)

        self.btn_export = ctk.CTkButton(
            btn_group, text=t["export_config"], width=90, height=30,
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray40"),
            hover_color=("gray85", "gray30"),
            text_color=("gray20", "gray80"),
            font=ctk.CTkFont(size=12),
            command=self._save_config,
        )
        self.btn_export.pack(side="left", padx=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        self._scroll = scroll

        self.card_site = CardFrame(scroll, t["site_settings"], icon="🌐")
        self.card_site.pack(fill="x", pady=4)
        c = self.card_site.content

        row1 = ctk.CTkFrame(c, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        self._lbl_url = ctk.CTkLabel(row1, text=t["site_url"], width=80, anchor="w")
        self._lbl_url.pack(side="left")
        self.var_url = ctk.CTkEntry(row1, placeholder_text="https://danbooru.donmai.us")
        self.var_url.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.var_url.insert(0, "https://danbooru.donmai.us")

        row2 = ctk.CTkFrame(c, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        self._lbl_user = ctk.CTkLabel(row2, text=t["username"], width=80, anchor="w")
        self._lbl_user.pack(side="left")
        self.var_username = ctk.CTkEntry(row2, placeholder_text=t["optional"])
        self.var_username.pack(side="left", fill="x", expand=True, padx=(4, 8))
        self._lbl_apikey = ctk.CTkLabel(row2, text=t["api_key"], width=60, anchor="w")
        self._lbl_apikey.pack(side="left")
        self.var_apikey = ctk.CTkEntry(row2, placeholder_text=t["optional"], show="•")
        self.var_apikey.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.card_search = CardFrame(scroll, t["search_settings"], icon="🔍")
        self.card_search.pack(fill="x", pady=4)
        c = self.card_search.content

        row1 = ctk.CTkFrame(c, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        self._lbl_tags = ctk.CTkLabel(row1, text=t["search_tags"], width=80, anchor="w")
        self._lbl_tags.pack(side="left")
        self.var_tags = ctk.CTkEntry(row1, placeholder_text=t["search_tags_hint"])
        self.var_tags.pack(side="left", fill="x", expand=True, padx=(4, 0))

        row2 = ctk.CTkFrame(c, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        self._lbl_blocked = ctk.CTkLabel(row2, text=t["blocked_tags"], width=80, anchor="w")
        self._lbl_blocked.pack(side="left")
        self.var_blocked = ctk.CTkEntry(row2, placeholder_text=t["blocked_tags_hint"])
        self.var_blocked.pack(side="left", fill="x", expand=True, padx=(4, 0))

        row3 = ctk.CTkFrame(c, fg_color="transparent")
        row3.pack(fill="x", pady=2)
        self._lbl_rating = ctk.CTkLabel(row3, text=t["rating"], width=80, anchor="w")
        self._lbl_rating.pack(side="left")
        self.var_rating = ctk.CTkComboBox(row3, values=t["rating_options"], width=180, state="readonly")
        self.var_rating.set(t["rating_options"][0])
        self.var_rating.pack(side="left", padx=(4, 16))
        self._lbl_minscore = ctk.CTkLabel(row3, text=t["min_score"], width=66, anchor="w")
        self._lbl_minscore.pack(side="left")
        self.var_min_score = ctk.CTkEntry(row3, placeholder_text=t["min_score_hint"], width=80)
        self.var_min_score.pack(side="left", padx=(4, 0))

        self.card_dl = CardFrame(scroll, t["download_settings"], icon="📁")
        self.card_dl.pack(fill="x", pady=4)
        c = self.card_dl.content

        row_folder = ctk.CTkFrame(c, fg_color="transparent")
        row_folder.pack(fill="x", pady=2)
        self._lbl_folder = ctk.CTkLabel(row_folder, text=t["folder_name"], width=80, anchor="w")
        self._lbl_folder.pack(side="left")
        self.var_folder_name = ctk.CTkEntry(row_folder, placeholder_text=t["folder_name_hint"])
        self.var_folder_name.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.lbl_path_preview = ctk.CTkLabel(
            c, text=t["save_path_label"] + str(DEFAULT_DOWNLOAD_DIR) + "/",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self.lbl_path_preview.pack(anchor="w", padx=(84, 0), pady=(0, 4))

        def _update_path_preview(*_args):
            sub = self.var_folder_name.get().strip()
            if sub:
                preview = str(DEFAULT_DOWNLOAD_DIR / sub)
            else:
                preview = str(DEFAULT_DOWNLOAD_DIR)
            self.lbl_path_preview.configure(text=self.t["save_path_label"] + preview + "/")

        self.var_folder_name.bind("<KeyRelease>", _update_path_preview)

        row_fn = ctk.CTkFrame(c, fg_color="transparent")
        row_fn.pack(fill="x", pady=(6, 2))
        self.var_custom_name = ctk.CTkCheckBox(
            row_fn, text=t["custom_filename"],
            command=self._toggle_custom_name,
            font=ctk.CTkFont(size=13),
        )
        self.var_custom_name.pack(side="left")

        row_fmt = ctk.CTkFrame(c, fg_color="transparent")
        row_fmt.pack(fill="x", pady=2)
        self._lbl_fmt = ctk.CTkLabel(row_fmt, text=t["filename_format"], width=80, anchor="w")
        self._lbl_fmt.pack(side="left")
        self.entry_filename = ctk.CTkEntry(row_fmt, placeholder_text=DEFAULT_FILENAME_FORMAT, state="disabled")
        self.entry_filename.pack(side="left", fill="x", expand=True, padx=(4, 8))
        self.btn_placeholder = ctk.CTkButton(
            row_fmt, text=t["placeholder_info"], width=86, height=28,
            fg_color="transparent", border_width=1,
            border_color=COLORS["accent"],
            text_color=COLORS["accent"],
            hover_color=("gray90", "gray25"),
            command=lambda: messagebox.showinfo(t["placeholder_info"], t["placeholder_help"]),
        )
        self.btn_placeholder.pack(side="left")

        self.lbl_fmt_hint = ctk.CTkLabel(
            c, text=t["default_format"] + DEFAULT_FILENAME_FORMAT,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self.lbl_fmt_hint.pack(anchor="w", padx=(84, 0), pady=(0, 4))

        row_nums = ctk.CTkFrame(c, fg_color="transparent")
        row_nums.pack(fill="x", pady=2)
        self._lbl_max = ctk.CTkLabel(row_nums, text=t["max_downloads"], width=80, anchor="w")
        self._lbl_max.pack(side="left")
        self.var_max_posts = ctk.CTkEntry(row_nums, width=80, placeholder_text="100")
        self.var_max_posts.insert(0, "100")
        self.var_max_posts.pack(side="left", padx=(4, 20))
        self._lbl_conc = ctk.CTkLabel(row_nums, text=t["concurrent"], width=50, anchor="w")
        self._lbl_conc.pack(side="left")
        self.var_concurrent = ctk.CTkEntry(row_nums, width=80, placeholder_text="8")
        self.var_concurrent.insert(0, "8")
        self.var_concurrent.pack(side="left", padx=(4, 20))
        self._lbl_timeout = ctk.CTkLabel(row_nums, text=t["timeout_sec"], width=60, anchor="w")
        self._lbl_timeout.pack(side="left")
        self.var_timeout = ctk.CTkEntry(row_nums, width=80, placeholder_text="30")
        self.var_timeout.insert(0, "30")
        self.var_timeout.pack(side="left", padx=(4, 0))

        row_opts = ctk.CTkFrame(c, fg_color="transparent")
        row_opts.pack(fill="x", pady=(4, 0))
        self.var_skip_existing = ctk.CTkCheckBox(
            row_opts, text=t["skip_existing"],
            font=ctk.CTkFont(size=13),
        )
        self.var_skip_existing.select()
        self.var_skip_existing.pack(side="left")

        row_video = ctk.CTkFrame(c, fg_color="transparent")
        row_video.pack(fill="x", pady=(4, 0))
        self.var_download_video = ctk.CTkCheckBox(
            row_video, text=t["download_video"],
            font=ctk.CTkFont(size=13),
        )
        self.var_download_video.pack(side="left")

        action_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        action_frame.pack(fill="x", pady=(8, 4))

        self.btn_start = ctk.CTkButton(
            action_frame, text=t["start_download"], height=40, width=160,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._start_download,
        )
        self.btn_start.pack(side="left", padx=(4, 8))

        self.btn_stop = ctk.CTkButton(
            action_frame, text=t["stop_download"], height=40, width=140,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["danger"], hover_color="#C0392B",
            state="disabled",
            command=self._stop_download,
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_clear = ctk.CTkButton(
            action_frame, text=t["clear_log"], height=32, width=90,
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray40"),
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray30"),
            font=ctk.CTkFont(size=12),
            command=self._clear_log,
        )
        self.btn_clear.pack(side="right", padx=4)

        self.card_prog = CardFrame(scroll, t["progress"], icon="📊")
        self.card_prog.pack(fill="x", pady=4)
        c = self.card_prog.content

        self.progress = ctk.CTkProgressBar(c, height=14, corner_radius=7,
                                            progress_color=COLORS["accent"])
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(0, 6))

        self.lbl_stats = ctk.CTkLabel(
            c, text=t["ready"],
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        self.lbl_stats.pack(anchor="w")

        self.card_log = CardFrame(scroll, t["log"], icon="📋")
        self.card_log.pack(fill="both", expand=True, pady=(4, 8))

        self.txt_log = ctk.CTkTextbox(
            self.card_log.content, height=180,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8,
            state="disabled",
        )
        self.txt_log.pack(fill="both", expand=True)

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

    def _update_texts(self, old_rating_val: str = ""):
        t = self.t

        self.title(t["title"])
        self._lbl_title.configure(text="🎨 " + t["title"])
        self.btn_settings.configure(text=t["settings"])
        self.btn_import.configure(text=t["import_config"])
        self.btn_export.configure(text=t["export_config"])

        self.card_site.set_title(t["site_settings"], icon="🌐")
        self._lbl_url.configure(text=t["site_url"])
        self._lbl_user.configure(text=t["username"])
        self._lbl_apikey.configure(text=t["api_key"])

        self.card_search.set_title(t["search_settings"], icon="🔍")
        self._lbl_tags.configure(text=t["search_tags"])
        self._lbl_blocked.configure(text=t["blocked_tags"])
        self._lbl_rating.configure(text=t["rating"])
        self._lbl_minscore.configure(text=t["min_score"])

        self.var_rating.configure(values=t["rating_options"])
        new_rev = self._rating_rev
        self.var_rating.set(new_rev.get(old_rating_val, t["rating_options"][0]))

        self.card_dl.set_title(t["download_settings"], icon="📁")
        self._lbl_folder.configure(text=t["folder_name"])
        self._lbl_fmt.configure(text=t["filename_format"])
        self.var_custom_name.configure(text=t["custom_filename"])
        self.btn_placeholder.configure(text=t["placeholder_info"])
        self._lbl_max.configure(text=t["max_downloads"])
        self._lbl_conc.configure(text=t["concurrent"])
        self._lbl_timeout.configure(text=t["timeout_sec"])
        self.var_skip_existing.configure(text=t["skip_existing"])
        self.var_download_video.configure(text=t["download_video"])

        sub = self.var_folder_name.get().strip()
        if sub:
            preview = str(DEFAULT_DOWNLOAD_DIR / sub)
        else:
            preview = str(DEFAULT_DOWNLOAD_DIR)
        self.lbl_path_preview.configure(text=t["save_path_label"] + preview + "/")

        if self.var_custom_name.get():
            self.lbl_fmt_hint.configure(text=t["custom_format_hint"])
        else:
            self.lbl_fmt_hint.configure(text=t["default_format"] + DEFAULT_FILENAME_FORMAT)

        self.btn_start.configure(text=t["start_download"])
        self.btn_stop.configure(text=t["stop_download"])
        self.btn_clear.configure(text=t["clear_log"])

        self.card_prog.set_title(t["progress"], icon="📊")
        self.card_log.set_title(t["log"], icon="📋")

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
        if sub:
            return str(DEFAULT_DOWNLOAD_DIR / sub)
        return str(DEFAULT_DOWNLOAD_DIR)

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
            base_url=self._get_entry_text(self.var_url) or "https://danbooru.donmai.us",
            username=self._get_entry_text(self.var_username) or None,
            api_key=self._get_entry_text(self.var_apikey) or None,
            tags=self._get_entry_text(self.var_tags),
            blocked_tags=self._get_entry_text(self.var_blocked),
            rating=rating_val or None,
            min_score=min_score,
            save_dir=self._get_save_dir(),
            filename_format=fmt,
            max_posts=max_posts,
            concurrent_downloads=concurrent,
            skip_existing=bool(self.var_skip_existing.get()),
            timeout=timeout,
        )

    def _apply_config(self, config: Config):
        def _set(entry, val):
            entry.configure(state="normal")
            entry.delete(0, "end")
            if val:
                entry.insert(0, val)

        _set(self.var_url, config.base_url)
        _set(self.var_username, config.username or "")
        _set(self.var_apikey, config.api_key or "")
        _set(self.var_tags, config.tags)
        _set(self.var_blocked, config.blocked_tags)
        self.var_rating.set(self._rating_rev.get(config.rating or "", self.t["rating_options"][0]))
        _set(self.var_min_score, str(config.min_score) if config.min_score is not None else "")

        save_str = config.save_dir.replace("\\", "/")
        dl_prefix = str(DEFAULT_DOWNLOAD_DIR).replace("\\", "/") + "/"
        if save_str.startswith(dl_prefix):
            _set(self.var_folder_name, save_str[len(dl_prefix):])
        elif save_str == str(DEFAULT_DOWNLOAD_DIR).replace("\\", "/"):
            _set(self.var_folder_name, "")
        else:
            _set(self.var_folder_name, "")

        _set(self.var_max_posts, str(config.max_posts))
        _set(self.var_concurrent, str(config.concurrent_downloads))
        _set(self.var_timeout, str(config.timeout))

        if config.skip_existing:
            self.var_skip_existing.select()
        else:
            self.var_skip_existing.deselect()

        is_custom = config.filename_format != DEFAULT_FILENAME_FORMAT
        if is_custom:
            self.var_custom_name.select()
        else:
            self.var_custom_name.deselect()
        self._toggle_custom_name()
        if is_custom:
            _set(self.entry_filename, config.filename_format)

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
            self._log_message(f"✅ Imported config: {path}")
        except Exception as e:
            messagebox.showerror(t["import_fail"], t["import_fail_msg"].format(e))

    def _save_config(self):
        t = self.t
        path = filedialog.asksaveasfilename(
            title=t["save_config_title"],
            defaultextension=".yaml",
            filetypes=[(t["yaml_files"], "*.yaml *.yml")],
        )
        if not path:
            return
        try:
            config = self._build_config()
            config.to_yaml(path)
            self._log_message(f"✅ Config saved: {path}")
        except Exception as e:
            messagebox.showerror(t["export_fail"], t["export_fail_msg"].format(e))

    def _log_message(self, msg: str):
        self._msg_queue.put(("log", msg))

    def _update_progress(self, downloaded: int, skipped: int, failed: int, total: int):
        self._msg_queue.put(("progress", (downloaded, skipped, failed, total)))

    def _poll_queue(self):
        try:
            while True:
                kind, data = self._msg_queue.get_nowait()
                if kind == "log":
                    self.txt_log.configure(state="normal")
                    self.txt_log.insert("end", data + "\n")
                    self.txt_log.see("end")
                    self.txt_log.configure(state="disabled")
                elif kind == "progress":
                    downloaded, skipped, failed, total = data
                    done = downloaded + skipped + failed
                    ratio = done / total if total else 0
                    self.progress.set(ratio)
                    self.lbl_stats.configure(
                        text=self.t["stats_fmt"].format(dl=downloaded, sk=skipped, fa=failed, to=total)
                    )
                elif kind == "done":
                    self._on_download_finished(data)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _start_download(self):
        config = self._build_config()
        tags_query = config.build_tags_query()
        if not tags_query.strip():
            messagebox.showwarning(self.t["hint"], self.t["no_tags_warn"])
            return

        download_video = bool(self.var_download_video.get())

        self._cancel_event.clear()
        self.progress.set(0)
        self.lbl_stats.configure(text=self.t["searching"])
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        self._log_message("═" * 50)
        self._log_message(f"🔍 Tags: {tags_query}")
        self._log_message(f"🌐 Site: {config.base_url}")
        self._log_message(f"📁 Save: {Path(config.save_dir).resolve()}")
        self._log_message(f"📝 Format: {config.filename_format}")
        self._log_message(f"📊 Max: {config.max_posts}  |  Concurrent: {config.concurrent_downloads}")
        self._log_message(f"🎬 Video: {'✅' if download_video else '❌'}")
        self._log_message("═" * 50)
        self._log_message("")

        def _worker():
            try:
                self._log_message("🔎 Searching posts...")
                with DanbooruClient(
                    base_url=config.base_url,
                    username=config.username,
                    api_key=config.api_key,
                    timeout=config.timeout,
                ) as client:
                    posts = list(client.search_all(tags=tags_query, max_posts=config.max_posts))

                if self._cancel_event.is_set():
                    self._msg_queue.put(("done", "cancelled"))
                    return

                if not download_video:
                    before = len(posts)
                    posts = [
                        p for p in posts
                        if (p.get("file_ext", "") or "").lower() not in VIDEO_EXTENSIONS
                    ]
                    skipped_video = before - len(posts)
                    if skipped_video:
                        self._log_message(f"🎬 Filtered out {skipped_video} video/animation posts")

                self._log_message(f"✅ Found {len(posts)} downloadable posts")

                if not posts:
                    self._log_message("😢 No matching posts.")
                    self._msg_queue.put(("done", "no_results"))
                    return

                self._log_message("")

                formatter = FilenameFormatter(config.filename_format)
                dl = Downloader(
                    save_dir=config.save_dir,
                    formatter=formatter,
                    max_concurrent=config.concurrent_downloads,
                    skip_existing=config.skip_existing,
                    timeout=config.timeout,
                    on_progress=self._update_progress,
                    on_log=self._log_message,
                    cancel_event=self._cancel_event,
                )

                stats = dl.download_batch(posts)

                self._log_message("")
                self._log_message("═" * 50)
                self._log_message(f"✅ Downloaded: {stats['downloaded']}")
                self._log_message(f"⏭️  Skipped: {stats['skipped']}")
                if stats["failed"]:
                    self._log_message(f"❌ Failed: {stats['failed']}")
                self._log_message(f"📁 Saved: {Path(config.save_dir).resolve()}")
                self._log_message("═" * 50)

                self._msg_queue.put(("done", "success"))

            except Exception as e:
                self._log_message(f"\n❌ Error: {e}")
                self._msg_queue.put(("done", "error"))

        self._download_thread = threading.Thread(target=_worker, daemon=True)
        self._download_thread.start()

    def _stop_download(self):
        self._cancel_event.set()
        self._log_message("⛔ Stopping download...")
        self.btn_stop.configure(state="disabled")

    def _on_download_finished(self, result: str):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        t = self.t

        if result == "cancelled":
            self._log_message("⛔ Download cancelled.")
            self.lbl_stats.configure(text=t["cancelled"])
        elif result == "no_results":
            self.lbl_stats.configure(text=t["no_results"])
        elif result == "error":
            self.lbl_stats.configure(text=t["error_status"])
        else:
            self.lbl_stats.configure(text=t["done"])


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = DanbooruGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
