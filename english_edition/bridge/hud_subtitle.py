"""Fallout 4 HUD Subtitle Overlay + Interactive Vault-Tec Pip-Boy Live Chat (F8).

1. Click-through Subtitle HUD:
   Displays Lucy's spoken lines at the bottom of the screen without stealing focus.
2. Interactive Live Chat Window (Toggled anytime with F8):
   Opens a large, distance-readable Vault-Tec / Pip-Boy comms panel on top of Fallout 4 (Borderless Windowed),
   with 18pt typography and input box packed at `side="bottom"` first so text is never clipped.
"""

import ctypes
import queue
import threading
import time
from typing import Callable

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def _force_foreground(hwnd: int) -> None:
    """Reliably brings `hwnd` to the foreground on Windows 10/11 using AttachThreadInput."""
    if not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
        cur_tid = kernel32.GetCurrentThreadId()
        if fg_tid and fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, True)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.BringWindowToTop(hwnd)
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        if fg_tid and fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, False)
    except Exception:
        pass


class SubtitleHUD:
    def __init__(
        self,
        enabled: bool = True,
        speaker_color: str = "#26FF7E",
        on_player_chat: Callable[[str], None] | None = None,
    ):
        self.enabled = enabled
        self.speaker_color = speaker_color
        self.on_player_chat = on_player_chat
        self._sub_queue: queue.Queue = queue.Queue()
        self._chat_queue: queue.Queue = queue.Queue()
        self.chat_open = False
        if self.enabled:
            threading.Thread(target=self._run_tk, daemon=True).start()

    def show(self, speaker: str, text: str, duration_s: float | None = None) -> None:
        """Shows a subtitle on the click-through overlay AND updates the live chat log if open."""
        if not text or not self.enabled:
            return
        if duration_s is None:
            words = len(text.split())
            duration_s = max(5.0, min(16.0, words / 2.6 + 2.5))
        self._sub_queue.put((speaker, text, duration_s))
        self._chat_queue.put(("lucy_stream", speaker, text))

    def add_chat_message(self, role: str, speaker: str, text: str) -> None:
        """Appends a finalized message ('player', 'lucy', or 'status') to the chat window."""
        if not self.enabled:
            return
        self._chat_queue.put((role, speaker, text))

    def open_chat(self) -> None:
        """Requests opening the interactive chat overlay from any thread."""
        if self.enabled:
            self._chat_queue.put(("__open__", "", ""))

    def _run_tk(self) -> None:
        try:
            import tkinter as tk

            user32 = ctypes.windll.user32

            # 1. Click-through Subtitle Window
            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-transparentcolor", "#010101")
            root.configure(bg="#010101")

            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            box_w = int(screen_w * 0.72)
            box_h = 180
            pos_x = (screen_w - box_w) // 2
            pos_y = int(screen_h * 0.80)
            root.geometry(f"{box_w}x{box_h}+{pos_x}+{pos_y}")

            frame = tk.Frame(root, bg="#0C120E", bd=2, relief="solid", padx=22, pady=12)
            frame.pack(expand=True)

            label = tk.Label(
                frame,
                text="",
                font=("Segoe UI Semibold", 18),
                fg="#E8F5E9",
                bg="#0C120E",
                wraplength=box_w - 80,
                justify="center",
            )
            label.pack()

            hint_lbl = tk.Label(
                frame,
                text="[Press F8 anytime to open Live Chat with Lucy]",
                font=("Consolas", 12),
                fg="#26FF7E",
                bg="#0C120E",
            )
            hint_lbl.pack(pady=(6, 0))

            root.update_idletasks()
            sub_hwnd = user32.GetParent(root.winfo_id())
            if sub_hwnd:
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x00080000
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_TOOLWINDOW = 0x00000080
                style = user32.GetWindowLongW(sub_hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    sub_hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                )

            # 2. Interactive Pip-Boy Live Chat Window (Toggled by F8)
            chat_win = tk.Toplevel(root)
            chat_win.title("Vault-Tec Pip-Boy Comms — Lucy MacLean (F8: Show/Hide)")
            chat_win.withdraw()
            chat_win.attributes("-topmost", True)
            chat_win.attributes("-alpha", 0.96)
            chat_win.configure(bg="#26FF7E", padx=3, pady=3)

            c_w = int(screen_w * 0.70)
            c_h = int(screen_h * 0.52)
            c_x = (screen_w - c_w) // 2
            c_y = int(screen_h * 0.24)
            chat_win.geometry(f"{c_w}x{c_h}+{c_x}+{c_y}")
            chat_win.minsize(900, 460)

            font_size = 18

            inner = tk.Frame(chat_win, bg="#08110B", padx=24, pady=18)
            inner.pack(fill="both", expand=True)

            header = tk.Frame(inner, bg="#08110B")
            header.pack(side="top", fill="x", pady=(0, 12))

            title_lbl = tk.Label(
                header,
                text="VAULT-TEC PIP-BOY COMMS // LUCY MACLEAN (VAULT 33)",
                font=("Consolas", 15, "bold"),
                fg="#26FF7E",
                bg="#08110B",
            )
            title_lbl.pack(side="left")

            help_lbl = tk.Label(
                header,
                text="[ENTER: Send  |  ESC or F8: Close & Return to Fallout 4]",
                font=("Consolas", 12, "bold"),
                fg="#A5D6A7",
                bg="#08110B",
            )
            help_lbl.pack(side="right")

            # Pack input bar at side="bottom" FIRST so it is never pushed off or clipped
            input_frame = tk.Frame(
                inner,
                bg="#13261A",
                highlightbackground="#26FF7E",
                highlightthickness=2,
                padx=16,
                pady=12,
            )
            input_frame.pack(side="bottom", fill="x", pady=(8, 6))

            prompt_lbl = tk.Label(
                input_frame,
                text="YOU > ",
                font=("Consolas", font_size, "bold"),
                fg="#FFD54F",
                bg="#13261A",
            )
            prompt_lbl.pack(side="left")

            entry = tk.Entry(
                input_frame,
                font=("Segoe UI Semibold", font_size),
                bg="#13261A",
                fg="#FFFFFF",
                insertbackground="#26FF7E",
                relief="flat",
            )
            entry.pack(side="left", fill="x", expand=True, ipady=8)

            status_var = tk.StringVar(
                value="● Ready — Type any question or comment for Lucy in English and press ENTER."
            )
            status_lbl = tk.Label(
                inner,
                textvariable=status_var,
                font=("Consolas", 13),
                fg="#69F0AE",
                bg="#08110B",
                anchor="w",
            )
            status_lbl.pack(side="bottom", fill="x", pady=(6, 4))

            history = tk.Text(
                inner,
                font=("Segoe UI", font_size),
                bg="#0D1911",
                fg="#E8F5E9",
                insertbackground="#26FF7E",
                relief="flat",
                padx=18,
                pady=14,
                wrap="word",
                height=6,
                spacing1=4,
                spacing3=6,
                state="disabled",
            )
            history.pack(side="top", fill="both", expand=True, pady=(0, 6))
            history.tag_config("player_tag", foreground="#FFD54F", font=("Segoe UI Bold", font_size))
            history.tag_config("player_msg", foreground="#FFF8E1", font=("Segoe UI", font_size))
            history.tag_config("lucy_tag", foreground="#26FF7E", font=("Segoe UI Bold", font_size))
            history.tag_config("lucy_msg", foreground="#E8F5E9", font=("Segoe UI", font_size))
            history.tag_config("sys_msg", foreground="#81C784", font=("Consolas", 14, "italic"))

            chat_win.update_idletasks()
            chat_hwnd = user32.GetParent(chat_win.winfo_id()) or chat_win.winfo_id()
            saved_game_hwnd = 0
            streaming_line_active = False

            def _append_history(role: str, speaker: str, text: str) -> None:
                nonlocal streaming_line_active
                history.config(state="normal")
                if role == "lucy_stream":
                    if streaming_line_active:
                        history.delete("end-2l", "end-1c")
                        history.insert("end", "\n")
                    history.insert("end", f"{speaker}: ", "lucy_tag")
                    history.insert("end", f"{text}\n", "lucy_msg")
                    streaming_line_active = True
                elif role == "player":
                    streaming_line_active = False
                    history.insert("end", f"{speaker}: ", "player_tag")
                    history.insert("end", f"{text}\n", "player_msg")
                elif role == "status":
                    status_var.set(text)
                else:
                    streaming_line_active = False
                    history.insert("end", f"{text}\n", "sys_msg")
                history.see("end")
                history.config(state="disabled")

            _append_history(
                "sys",
                "",
                "--- Vault-Tec Pip-Boy Direct Link established with Lucy MacLean (Vault 33). Ask her anything in English! ---",
            )

            def _show_chat() -> None:
                nonlocal saved_game_hwnd
                if self.chat_open:
                    return
                fg = user32.GetForegroundWindow()
                if fg and fg != chat_hwnd and fg != sub_hwnd:
                    saved_game_hwnd = fg
                self.chat_open = True
                chat_win.deiconify()
                chat_win.lift()
                chat_win.update_idletasks()
                hwnd = user32.GetParent(chat_win.winfo_id()) or chat_win.winfo_id()
                _force_foreground(hwnd)
                entry.focus_force()

            def _hide_chat() -> None:
                if not self.chat_open:
                    return
                self.chat_open = False
                chat_win.withdraw()
                if saved_game_hwnd:
                    _force_foreground(saved_game_hwnd)

            def _on_submit(event=None):
                msg = entry.get().strip()
                if not msg:
                    return "break"
                entry.delete(0, "end")
                _append_history("player", "You (Vault 111)", msg)
                status_var.set("● Lucy is thinking...")
                if self.on_player_chat:
                    threading.Thread(target=self.on_player_chat, args=(msg,), daemon=True).start()
                return "break"

            entry.bind("<Return>", _on_submit)
            entry.bind("<Escape>", lambda e: (_hide_chat(), "break")[1])
            chat_win.bind("<Escape>", lambda e: _hide_chat())

            hide_at = 0.0
            f8_was_down = False

            def poll():
                nonlocal hide_at, f8_was_down
                f8_down = bool(user32.GetAsyncKeyState(0x77) & 0x8000)
                if f8_down and not f8_was_down:
                    if self.chat_open:
                        _hide_chat()
                    else:
                        _show_chat()
                f8_was_down = f8_down

                try:
                    while True:
                        speaker, text, dur = self._sub_queue.get_nowait()
                        label.config(text=f"{speaker}: {text}")
                        if not self.chat_open:
                            root.deiconify()
                            root.lift()
                        hide_at = time.monotonic() + dur
                except queue.Empty:
                    pass

                try:
                    while True:
                        role, speaker, text = self._chat_queue.get_nowait()
                        if role == "__open__":
                            _show_chat()
                        else:
                            if role == "lucy_stream":
                                status_var.set("● Lucy is speaking... (Type your next reply anytime)")
                            _append_history(role, speaker, text)
                except queue.Empty:
                    pass

                if hide_at and time.monotonic() >= hide_at:
                    root.withdraw()
                    hide_at = 0.0

                root.after(45, poll)

            root.after(45, poll)
            root.mainloop()
        except Exception as e:
            print(f"[HUD] Graphic overlay error ({e}); using console.", flush=True)
