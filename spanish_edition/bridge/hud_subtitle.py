"""Superposición HUD Integrada en Pantalla de Subtítulos y Chat Pip-Boy para Fallout 4 [Edición Español v1.1.0].

- Implementación pura con biblioteca estándar de Python y Tkinter (cero dependencias de binarios o hooks externos).
- Se dibuja directamente sobre la pantalla de Fallout 4 en modo Ventana sin Bordes (`bBorderless=1, bFull Screen=0`) sin barra de título de Windows (`overrideredirect(True)`).
- Características:
  1. Barra inferior de subtítulos HUD cuando Lucy habla.
  2. Píldora HUD discreta abajo a la derecha `[● COMMS PIP-BOY: LUCY]` que puedes pulsar en cualquier momento (o activar dentro del juego desde la Opción 1 del menú `E` de Lucy o con el acceso rápido `[Lucy] 0.` en la rueda de Favoritos `Q`).
  3. HUD de Chat Pip-Boy sin bordes en el tercio inferior de la pantalla (`overrideredirect(True)`) para seguir viendo a Lucy y el mundo de Fallout 4 mientras escribes.
  4. `Volver al Juego: SÍ` (activo por defecto): al pulsar `ENTER` para enviar tu mensaje, el HUD de escritura se oculta automáticamente y devuelve el control del teclado/ratón a Fallout 4 mientras Lucy te responde en voz alta y con subtítulos en pantalla.
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

            # 1. Barra inferior de subtítulos HUD en pantalla
            box_w = int(screen_w * 0.72)
            box_h = 180
            pos_x = (screen_w - box_w) // 2
            pos_y = int(screen_h * 0.80)
            root.geometry(f"{box_w}x{box_h}+{pos_x}+{pos_y}")

            frame = tk.Frame(
                root,
                bg="#08110B",
                highlightbackground="#26FF7E",
                highlightthickness=2,
                padx=22,
                pady=12,
            )
            frame.pack(expand=True)

            label = tk.Label(
                frame,
                text="",
                font=("Segoe UI Semibold", 18),
                fg="#E8F5E9",
                bg="#08110B",
                wraplength=box_w - 80,
                justify="center",
            )
            label.pack()

            hint_lbl = tk.Label(
                frame,
                text="[Haz clic aquí, elige la Opción 1 en el menú E de Lucy o usa '[Lucy] 0.' en Favoritos para abrir el Chat HUD]",
                font=("Consolas", 11),
                fg="#26FF7E",
                bg="#08110B",
                cursor="hand2",
            )
            hint_lbl.pack(pady=(6, 0))

            # 2. Píldora HUD discreta abajo a la derecha dentro del juego
            pill_win = tk.Toplevel(root)
            pill_win.overrideredirect(True)
            pill_win.attributes("-topmost", True)
            pill_win.attributes("-alpha", 0.80)
            pill_win.configure(bg="#26FF7E", padx=1, pady=1)
            pill_w = 340
            pill_h = 34
            pill_x = max(20, screen_w - pill_w - 28)
            pill_y = max(20, int(screen_h * 0.94))
            pill_win.geometry(f"{pill_w}x{pill_h}+{pill_x}+{pill_y}")

            pill_inner = tk.Frame(pill_win, bg="#08110B", padx=8, pady=4)
            pill_inner.pack(fill="both", expand=True)

            pill_lbl = tk.Label(
                pill_inner,
                text="● COMMS PIP-BOY: LUCY [CHAT HUD]",
                font=("Consolas", 10, "bold"),
                fg="#26FF7E",
                bg="#08110B",
                cursor="hand2",
            )
            pill_lbl.pack(side="left", fill="x", expand=True)

            pill_dismissed = False

            def _dismiss_pill() -> None:
                nonlocal pill_dismissed
                pill_dismissed = True
                pill_win.withdraw()

            pill_close = tk.Label(
                pill_inner,
                text=" × ",
                font=("Consolas", 10, "bold"),
                fg="#81C784",
                bg="#08110B",
                cursor="hand2",
            )
            pill_close.pack(side="right")
            pill_close.bind("<Button-1>", lambda e: _dismiss_pill())

            # 3. Superposición HUD de Chat Pip-Boy sin bordes (Tercio inferior de la pantalla)
            chat_win = tk.Toplevel(root)
            chat_win.withdraw()
            chat_win.overrideredirect(True)
            chat_win.attributes("-topmost", True)
            chat_win.attributes("-alpha", 0.92)
            chat_win.configure(bg="#26FF7E", padx=2, pady=2)

            compact_mode = True
            auto_hide_on_send = True
            font_size = 16

            def _apply_hud_geometry() -> None:
                if compact_mode:
                    c_w = int(screen_w * 0.66)
                    c_h = int(screen_h * 0.30)
                    c_x = (screen_w - c_w) // 2
                    c_y = int(screen_h * 0.63)
                else:
                    c_w = int(screen_w * 0.72)
                    c_h = int(screen_h * 0.52)
                    c_x = (screen_w - c_w) // 2
                    c_y = int(screen_h * 0.24)
                chat_win.geometry(f"{c_w}x{c_h}+{c_x}+{c_y}")

            _apply_hud_geometry()

            inner = tk.Frame(chat_win, bg="#08110B", padx=18, pady=12)
            inner.pack(fill="both", expand=True)

            # Cabecera HUD arrastrable
            header = tk.Frame(inner, bg="#0D1F14", padx=10, pady=6)
            header.pack(side="top", fill="x", pady=(0, 8))

            title_lbl = tk.Label(
                header,
                text="CHAT HUD PIP-BOY EN PANTALLA // LUCY MACLEAN (REFUGIO 33)",
                font=("Consolas", 13, "bold"),
                fg="#26FF7E",
                bg="#0D1F14",
                cursor="fleur",
            )
            title_lbl.pack(side="left")

            drag_state = {"x": 0, "y": 0}

            def _start_drag(event) -> None:
                drag_state["x"] = event.x_root - chat_win.winfo_x()
                drag_state["y"] = event.y_root - chat_win.winfo_y()

            def _do_drag(event) -> None:
                nx = event.x_root - drag_state["x"]
                ny = event.y_root - drag_state["y"]
                chat_win.geometry(f"+{nx}+{ny}")

            header.bind("<ButtonPress-1>", _start_drag)
            header.bind("<B1-Motion>", _do_drag)
            title_lbl.bind("<ButtonPress-1>", _start_drag)
            title_lbl.bind("<B1-Motion>", _do_drag)

            # Barra inferior de escritura empaquetada ANTES del historial para que jamás se corte
            input_frame = tk.Frame(
                inner,
                bg="#13261A",
                highlightbackground="#26FF7E",
                highlightthickness=2,
                padx=14,
                pady=8,
            )
            input_frame.pack(side="bottom", fill="x", pady=(6, 4))

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
            entry.pack(side="left", fill="x", expand=True, ipady=6)

            status_var = tk.StringVar(
                value="● HUD en Pantalla Activo — Escribe tu mensaje y pulsa ENTER (vuelve directo a Fallout 4 mientras Lucy responde)."
            )
            status_lbl = tk.Label(
                inner,
                textvariable=status_var,
                font=("Consolas", 11),
                fg="#69F0AE",
                bg="#08110B",
                anchor="w",
            )
            status_lbl.pack(side="bottom", fill="x", pady=(2, 2))

            # Historial desplazable de conversación
            history_frame = tk.Frame(
                inner,
                bg="#0D1911",
                highlightbackground="#1B3B26",
                highlightthickness=1,
            )
            history_frame.pack(side="top", fill="both", expand=True, pady=(0, 4))

            scrollbar = tk.Scrollbar(
                history_frame,
                bg="#0D1911",
                troughcolor="#08110B",
                relief="flat",
                width=14,
            )
            scrollbar.pack(side="right", fill="y")

            history = tk.Text(
                history_frame,
                font=("Segoe UI", font_size),
                bg="#0D1911",
                fg="#E8F5E9",
                insertbackground="#26FF7E",
                relief="flat",
                padx=14,
                pady=10,
                wrap="word",
                height=4,
                spacing1=3,
                spacing3=4,
                yscrollcommand=scrollbar.set,
                state="disabled",
            )
            history.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=history.yview)

            def _apply_font_size(new_size: int) -> None:
                nonlocal font_size
                font_size = max(12, min(30, new_size))
                prompt_lbl.config(font=("Consolas", font_size, "bold"))
                entry.config(font=("Segoe UI Semibold", font_size))
                history.config(font=("Segoe UI", font_size))
                history.tag_config("player_tag", foreground="#FFD54F", font=("Segoe UI Bold", font_size))
                history.tag_config("player_msg", foreground="#FFF8E1", font=("Segoe UI", font_size))
                history.tag_config("lucy_tag", foreground="#26FF7E", font=("Segoe UI Bold", font_size))
                history.tag_config("lucy_msg", foreground="#E8F5E9", font=("Segoe UI", font_size))
                history.tag_config("sys_msg", foreground="#81C784", font=("Consolas", max(11, font_size - 3), "italic"))
                history.see("end")

            _apply_font_size(font_size)

            def _focus_entry(event=None) -> None:
                try:
                    chat_win.lift()
                    chat_win.focus_force()
                    entry.focus_set()
                    entry.focus_force()
                except Exception:
                    pass

            def _show_chat(event=None) -> None:
                self.chat_open = True
                root.withdraw()
                chat_win.deiconify()
                chat_win.lift()
                chat_win.attributes("-topmost", True)
                _focus_entry()
                chat_win.after(60, _focus_entry)
                chat_win.after(180, _focus_entry)

            def _hide_chat(event=None) -> None:
                self.chat_open = False
                chat_win.withdraw()
                if not pill_dismissed:
                    pill_win.deiconify()
                    pill_win.lift()

            def _toggle_compact() -> None:
                nonlocal compact_mode
                compact_mode = not compact_mode
                btn_size_mode.config(text=" Ampliar HUD " if compact_mode else " HUD Compacto ")
                _apply_hud_geometry()
                _focus_entry()

            def _toggle_auto_hide() -> None:
                nonlocal auto_hide_on_send
                auto_hide_on_send = not auto_hide_on_send
                if auto_hide_on_send:
                    btn_auto.config(text=" Volver al Juego: SÍ ", fg="#08110B", bg="#26FF7E")
                else:
                    btn_auto.config(text=" Volver al Juego: NO ", fg="#26FF7E", bg="#13261A")
                _focus_entry()

            btn_hide = tk.Button(
                header,
                text=" Ocultar HUD (ESC) ",
                font=("Consolas", 10, "bold"),
                fg="#FFD54F",
                bg="#13261A",
                activebackground="#1B3B26",
                relief="flat",
                command=_hide_chat,
            )
            btn_hide.pack(side="right", padx=3)

            btn_size_mode = tk.Button(
                header,
                text=" Ampliar HUD ",
                font=("Consolas", 10, "bold"),
                fg="#26FF7E",
                bg="#13261A",
                activebackground="#1B3B26",
                relief="flat",
                command=_toggle_compact,
            )
            btn_size_mode.pack(side="right", padx=3)

            btn_auto = tk.Button(
                header,
                text=" Volver al Juego: SÍ ",
                font=("Consolas", 10, "bold"),
                fg="#08110B",
                bg="#26FF7E",
                activebackground="#69F0AE",
                relief="flat",
                command=_toggle_auto_hide,
            )
            btn_auto.pack(side="right", padx=3)

            btn_plus = tk.Button(
                header,
                text=" A+ ",
                font=("Consolas", 10, "bold"),
                fg="#26FF7E",
                bg="#13261A",
                activebackground="#1B3B26",
                relief="flat",
                command=lambda: (_apply_font_size(font_size + 2), _focus_entry()),
            )
            btn_plus.pack(side="right", padx=2)

            btn_minus = tk.Button(
                header,
                text=" A- ",
                font=("Consolas", 10, "bold"),
                fg="#26FF7E",
                bg="#13261A",
                activebackground="#1B3B26",
                relief="flat",
                command=lambda: (_apply_font_size(font_size - 2), _focus_entry()),
            )
            btn_minus.pack(side="right", padx=2)

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
                "--- HUD Pip-Boy en Pantalla conectado con Lucy MacLean (Refugio 33). ¡Escribe abajo y pulsa ENTER! ---",
            )

            def _on_submit(event=None):
                msg = entry.get().strip()
                if not msg:
                    if auto_hide_on_send:
                        _hide_chat()
                    return "break"
                entry.delete(0, "end")
                _append_history("player", "Tú (Refugio 111)", msg)
                status_var.set("● Lucy está pensando...")
                if auto_hide_on_send:
                    _hide_chat()
                    self._sub_queue.put(("Lucy MacLean", "[Pensando...]", 10.0))
                if self.on_player_chat:
                    threading.Thread(target=self.on_player_chat, args=(msg,), daemon=True).start()
                return "break"

            hint_lbl.bind("<Button-1>", _show_chat)
            label.bind("<Button-1>", _show_chat)
            pill_lbl.bind("<Button-1>", _show_chat)
            pill_inner.bind("<Button-1>", _show_chat)
            input_frame.bind("<Button-1>", _focus_entry)
            prompt_lbl.bind("<Button-1>", _focus_entry)
            entry.bind("<Button-1>", lambda e: chat_win.focus_force())
            history.bind("<Button-1>", _focus_entry)
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
