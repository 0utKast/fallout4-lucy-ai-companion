"""Superposición HUD de Comunicaciones Pip-Boy en Pantalla con Lucy MacLean [Edición Español v1.1.0].

- Si el Servidor Puente local (`iniciar_lucy_bridge.py`) ya está en marcha con el HUD integrado en el juego activo,
  ejecutar `abrir_chat_lucy.py` abre directamente ese HUD de Chat Pip-Boy en la pantalla de Fallout 4
  (`POST http://127.0.0.1:7777/open_chat`) sin duplicar ventanas.
- Si se ejecuta en modo `--standalone`, dibuja una superposición HUD Pip-Boy sin bordes (`overrideredirect(True)`)
  en el tercio inferior de la pantalla con `Volver al Juego: SÍ` (se oculta al pulsar `ENTER` para devolver el control a Fallout 4).
"""

import json
import queue
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request

BRIDGE_OPEN_URL = "http://127.0.0.1:7777/open_chat"
BRIDGE_STREAM_URL = "http://127.0.0.1:7777/chat_stream"


def _try_trigger_bridge_hud() -> bool:
    if "--standalone" in sys.argv:
        return False
    try:
        req = urllib.request.Request(
            BRIDGE_OPEN_URL,
            data=b"{}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if data.get("ok") and data.get("hud_active"):
                print(
                    "[HUD Pip-Boy] ¡Abierto el Chat HUD Pip-Boy en Pantalla directamente dentro de Fallout 4!",
                    flush=True,
                )
                return True
    except Exception:
        pass
    return False


def main() -> None:
    if _try_trigger_bridge_hud():
        return

    ui_queue: queue.Queue = queue.Queue()

    root = tk.Tk()
    root.title("Chat HUD Pip-Boy en Pantalla — Lucy MacLean")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.92)
    root.configure(bg="#26FF7E", padx=2, pady=2)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

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
        root.geometry(f"{c_w}x{c_h}+{c_x}+{c_y}")

    _apply_hud_geometry()

    # Píldora HUD discreta abajo a la derecha al ocultar
    pill_win = tk.Toplevel(root)
    pill_win.withdraw()
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

    inner = tk.Frame(root, bg="#08110B", padx=18, pady=12)
    inner.pack(fill="both", expand=True)

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
        drag_state["x"] = event.x_root - root.winfo_x()
        drag_state["y"] = event.y_root - root.winfo_y()

    def _do_drag(event) -> None:
        nx = event.x_root - drag_state["x"]
        ny = event.y_root - drag_state["y"]
        root.geometry(f"+{nx}+{ny}")

    header.bind("<ButtonPress-1>", _start_drag)
    header.bind("<B1-Motion>", _do_drag)
    title_lbl.bind("<ButtonPress-1>", _start_drag)
    title_lbl.bind("<B1-Motion>", _do_drag)

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

    history_frame = tk.Frame(inner, bg="#0D1911", highlightbackground="#1B3B26", highlightthickness=1)
    history_frame.pack(side="top", fill="both", expand=True, pady=(0, 4))

    scrollbar = tk.Scrollbar(history_frame, bg="#0D1911", troughcolor="#08110B", relief="flat", width=14)
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
            root.lift()
            root.focus_force()
            entry.focus_set()
            entry.focus_force()
        except Exception:
            pass

    def _show_chat(event=None) -> None:
        pill_win.withdraw()
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        _focus_entry()

    def _hide_chat(event=None) -> None:
        root.withdraw()
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

    streaming_active = False

    def _append_msg(role: str, speaker: str, text: str) -> None:
        nonlocal streaming_active
        history.config(state="normal")
        if role == "player":
            streaming_active = False
            history.insert("end", f"{speaker}: ", "player_tag")
            history.insert("end", f"{text}\n", "player_msg")
        elif role == "lucy_partial":
            if streaming_active:
                history.delete("end-2l", "end-1c")
                history.insert("end", "\n")
            history.insert("end", f"{speaker}: ", "lucy_tag")
            history.insert("end", f"{text}\n", "lucy_msg")
            streaming_active = True
        elif role == "lucy_done":
            if streaming_active:
                history.delete("end-2l", "end-1c")
                history.insert("end", "\n")
            history.insert("end", f"{speaker}: ", "lucy_tag")
            history.insert("end", f"{text}\n\n", "lucy_msg")
            streaming_active = False
        elif role == "status":
            status_var.set(text)
        else:
            streaming_active = False
            history.insert("end", f"{text}\n\n", "sys_msg")
        history.see("end")
        history.config(state="disabled")

    _append_msg(
        "sys",
        "",
        "--- Enlace directo HUD Pip-Boy establecido con Lucy MacLean (Refugio 33). ¡Escribe abajo y pulsa ENTER! ---",
    )

    def _send_to_bridge(msg: str) -> None:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(
                BRIDGE_STREAM_URL,
                data=json.dumps({"text": msg}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            final_say = ""
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    pkt = json.loads(line)
                    if pkt.get("type") == "partial":
                        partial_say = (pkt.get("say") or "").strip()
                        if partial_say:
                            final_say = partial_say
                            ui_queue.put(("lucy_partial", "Lucy MacLean", partial_say))
                            ui_queue.put(("status", "", "● Lucy está hablando... (Puedes escribir tu siguiente respuesta)"))
                    elif pkt.get("type") == "done":
                        dec = pkt.get("decision") or {}
                        final_say = (dec.get("say") or final_say).strip()
            dt = time.perf_counter() - t0
            if final_say:
                ui_queue.put(("lucy_done", "Lucy MacLean", final_say))
                ui_queue.put(
                    (
                        "status",
                        "",
                        f"● Lucy ha respondido ({dt:.1f}s) — Escribe otro mensaje y pulsa ENTER (o ESC/F8 para ocultar).",
                    )
                )
            else:
                ui_queue.put(("status", "", "● Listo — Escribe tu mensaje y pulsa ENTER."))
        except Exception as e:
            ui_queue.put(("sys", "", f"[Error conectando con el servidor en 127.0.0.1:7777: {e}]"))
            ui_queue.put(("status", "", "● Comprueba que iniciar_lucy_bridge.py esté en marcha."))

    def _on_submit(event=None):
        msg = entry.get().strip()
        if not msg:
            if auto_hide_on_send:
                _hide_chat()
            return "break"
        entry.delete(0, "end")
        _append_msg("player", "Tú (Refugio 111)", msg)
        status_var.set("● Lucy está pensando...")
        if auto_hide_on_send:
            _hide_chat()
        threading.Thread(target=_send_to_bridge, args=(msg,), daemon=True).start()
        return "break"

    pill_lbl.bind("<Button-1>", _show_chat)
    pill_inner.bind("<Button-1>", _show_chat)
    input_frame.bind("<Button-1>", _focus_entry)
    prompt_lbl.bind("<Button-1>", _focus_entry)
    entry.bind("<Button-1>", lambda e: root.focus_force())
    history.bind("<Button-1>", _focus_entry)
    entry.bind("<Return>", _on_submit)
    entry.bind("<Escape>", lambda e: (_hide_chat(), "break")[1])
    entry.bind("<F8>", lambda e: (_hide_chat(), "break")[1])
    root.bind("<Escape>", _hide_chat)
    root.bind("<F8>", _hide_chat)

    def _poll_ui() -> None:
        try:
            while True:
                role, speaker, text = ui_queue.get_nowait()
                _append_msg(role, speaker, text)
        except queue.Empty:
            pass
        root.after(40, _poll_ui)

    root.after(40, _poll_ui)
    root.after(80, _focus_entry)
    root.mainloop()


if __name__ == "__main__":
    main()
