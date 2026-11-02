"""Superposición de Subtítulos HUD para Fallout 4 + Chat en Vivo Pip-Boy en Español.

- Implementación pura con biblioteca estándar de Python y Tkinter.
"""

import queue
import threading
import time
from typing import Callable


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
        if not text or not self.enabled:
            return
        if duration_s is None:
            words = len(text.split())
            duration_s = max(5.0, min(16.0, words / 2.6 + 2.5))
        self._sub_queue.put((speaker, text, duration_s))
        self._chat_queue.put(("lucy_stream", speaker, text))

    def add_chat_message(self, role: str, speaker: str, text: str) -> None:
        if not self.enabled:
            return
        self._chat_queue.put((role, speaker, text))

    def open_chat(self) -> None:
        if self.enabled:
            self._chat_queue.put(("__open__", "", ""))

    def _run_tk(self) -> None:
        try:
            import tkinter as tk

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
                text="[Haz clic aquí o abre el Chat en Vivo con Lucy en cualquier momento]",
                font=("Consolas", 12),
                fg="#26FF7E",
                bg="#0C120E",
                cursor="hand2",
            )
            hint_lbl.pack(pady=(6, 0))

            chat_win = tk.Toplevel(root)
            chat_win.title("Comunicaciones Pip-Boy Vault-Tec — Lucy MacLean (ESC / F8: Ocultar)")
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
                text="COMUNICACIONES PIP-BOY VAULT-TEC // LUCY MACLEAN (REFUGIO 33)",
                font=("Consolas", 15, "bold"),
                fg="#26FF7E",
                bg="#08110B",
            )
            title_lbl.pack(side="left")

            help_lbl = tk.Label(
                header,
                text="[ENTER: Enviar  |  ESC o F8: Ocultar]",
                font=("Consolas", 12, "bold"),
                fg="#A5D6A7",
                bg="#08110B",
            )
            help_lbl.pack(side="right")

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
                text="TÚ > ",
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
                value="● Listo — Escribe cualquier pregunta o comentario en español y pulsa ENTER."
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
                "--- Enlace directo Pip-Boy establecido con Lucy MacLean (Refugio 33). ¡Pregúntale lo que quieras en español! ---",
            )

            def _show_chat(event=None) -> None:
                self.chat_open = True
                chat_win.deiconify()
                chat_win.lift()
                chat_win.attributes("-topmost", True)
                chat_win.focus_force()
                entry.focus_force()

            def _hide_chat(event=None) -> None:
                self.chat_open = False
                chat_win.withdraw()

            def _on_submit(event=None):
                msg = entry.get().strip()
                if not msg:
                    return "break"
                entry.delete(0, "end")
                _append_history("player", "Tú (Refugio 111)", msg)
                status_var.set("● Lucy está pensando...")
                if self.on_player_chat:
                    threading.Thread(target=self.on_player_chat, args=(msg,), daemon=True).start()
                return "break"

            hint_lbl.bind("<Button-1>", _show_chat)
            label.bind("<Button-1>", _show_chat)
            entry.bind("<Return>", _on_submit)
            entry.bind("<Escape>", lambda e: (_hide_chat(), "break")[1])
            entry.bind("<F8>", lambda e: (_hide_chat(), "break")[1])
            chat_win.bind("<Escape>", _hide_chat)
            chat_win.bind("<F8>", _hide_chat)
            chat_win.protocol("WM_DELETE_WINDOW", _hide_chat)

            hide_at = 0.0

            def poll():
                nonlocal hide_at
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
                                status_var.set("● Lucy está hablando... (Puedes escribir tu siguiente respuesta)")
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
            print(f"[HUD] Error en superposición gráfica ({e}); usando consola.", flush=True)
