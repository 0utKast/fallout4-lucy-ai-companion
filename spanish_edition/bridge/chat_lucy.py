"""Ventana Interactiva de Comunicaciones Pip-Boy Vault-Tec con Lucy MacLean (Edición 100% en Español — Formato Grande 4K).

- Implementación pura con biblioteca estándar de Python y Tkinter.
- Tamaño amplio (~70% ancho x ~52% alto de pantalla) para poder leerse cómodamente a distancia en pantallas 4K.
- Tipografía grande de 18pt por defecto con botones [A-] / [A+] en la cabecera para ajustar el tamaño en vivo.
- La caja de escritura está anclada con `side="bottom"` primero y margen vertical generoso (`ipady=8`) para que nunca se corte.
- Soporta todos los caracteres del castellano (`á, é, í, ó, ú, ñ, ü, ¿, ¡`) y voz en español (`ef_dora`) en tiempo real.
"""

import json
import queue
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request

BRIDGE_STREAM_URL = "http://127.0.0.1:7777/chat_stream"


def main() -> None:
    ui_queue: queue.Queue = queue.Queue()

    root = tk.Tk()
    root.title("Comunicaciones Pip-Boy Vault-Tec — Lucy MacLean (F8 / ESC: Minimizar)")
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.96)
    root.configure(bg="#08110B")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    c_w = int(screen_w * 0.70)
    c_h = int(screen_h * 0.52)
    c_x = (screen_w - c_w) // 2
    c_y = int(screen_h * 0.24)
    root.geometry(f"{c_w}x{c_h}+{c_x}+{c_y}")
    root.minsize(900, 460)

    font_size = 18

    outer = tk.Frame(root, bg="#26FF7E", padx=3, pady=3)
    outer.pack(fill="both", expand=True)

    inner = tk.Frame(outer, bg="#08110B", padx=24, pady=18)
    inner.pack(fill="both", expand=True)

    # 1. Cabecera superior
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
        text="[ENTER: Enviar  |  ESC o F8: Minimizar]",
        font=("Consolas", 12, "bold"),
        fg="#A5D6A7",
        bg="#08110B",
    )
    help_lbl.pack(side="right", padx=(12, 0))

    # 2. Barra de escritura inferior empaquetada ANTES del historial para que jamás quede cortada
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
        value="● Listo — Escribe tu mensaje para Lucy en español y pulsa ENTER (Pulsa F8 o ESC para minimizar)."
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

    # 3. Historial central de conversación
    history_frame = tk.Frame(inner, bg="#0D1911", highlightbackground="#1B3B26", highlightthickness=1)
    history_frame.pack(side="top", fill="both", expand=True, pady=(0, 6))

    scrollbar = tk.Scrollbar(history_frame, bg="#0D1911", troughcolor="#08110B", relief="flat", width=18)
    scrollbar.pack(side="right", fill="y")

    history = tk.Text(
        history_frame,
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
        yscrollcommand=scrollbar.set,
        state="disabled",
    )
    history.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=history.yview)

    def _apply_font_size(new_size: int) -> None:
        nonlocal font_size
        font_size = max(12, min(32, new_size))
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

    chat_visible = True

    def _show_chat() -> None:
        nonlocal chat_visible
        chat_visible = True
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()
        entry.focus_force()

    def _hide_chat() -> None:
        nonlocal chat_visible
        chat_visible = False
        root.iconify()

    def _toggle_chat(event=None):
        if chat_visible and root.state() != "iconic":
            _hide_chat()
        else:
            _show_chat()
        return "break"

    btn_hide = tk.Button(
        header,
        text=" Minimizar ",
        font=("Consolas", 11, "bold"),
        fg="#26FF7E",
        bg="#13261A",
        activebackground="#1B3B26",
        relief="flat",
        command=_hide_chat,
    )
    btn_hide.pack(side="right", padx=4)

    btn_plus = tk.Button(
        header,
        text=" A+ ",
        font=("Consolas", 12, "bold"),
        fg="#08110B",
        bg="#26FF7E",
        activebackground="#69F0AE",
        relief="flat",
        command=lambda: _apply_font_size(font_size + 2),
    )
    btn_plus.pack(side="right", padx=4)

    btn_minus = tk.Button(
        header,
        text=" A- ",
        font=("Consolas", 12, "bold"),
        fg="#26FF7E",
        bg="#13261A",
        activebackground="#1B3B26",
        relief="flat",
        command=lambda: _apply_font_size(font_size - 2),
    )
    btn_minus.pack(side="right", padx=4)

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
        "--- Enlace directo Pip-Boy establecido con Lucy MacLean (Refugio 33). ¡Pregúntale lo que quieras en español! (Usa [A+] / [A-] arriba a la derecha para cambiar el tamaño de letra, o F8 / ESC para minimizar) ---",
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
                print(f"\nLUCY ({dt:.1f}s) > {final_say}\nTÚ > ", end="", flush=True)
                ui_queue.put(("lucy_done", "Lucy MacLean", final_say))
                ui_queue.put(
                    (
                        "status",
                        "",
                        f"● Lucy ha respondido ({dt:.1f}s) — Escribe otro mensaje y pulsa ENTER (o ESC/F8 para minimizar).",
                    )
                )
            else:
                ui_queue.put(("status", "", "● Listo — Escribe tu mensaje y pulsa ENTER."))
        except Exception as e:
            ui_queue.put(("sys", "", f"[Error conectando con el servidor en 127.0.0.1:7777: {e}]"))
            ui_queue.put(("status", "", "● Comprueba que el servidor Bridge esté en marcha."))

    def _on_submit(event=None):
        msg = entry.get().strip()
        if not msg:
            return "break"
        entry.delete(0, "end")
        _append_msg("player", "Tú (Refugio 111)", msg)
        status_var.set("● Lucy está pensando...")
        threading.Thread(target=_send_to_bridge, args=(msg,), daemon=True).start()
        return "break"

    entry.bind("<Return>", _on_submit)
    entry.bind("<Escape>", _toggle_chat)
    entry.bind("<F8>", _toggle_chat)
    root.bind("<Escape>", _toggle_chat)
    root.bind("<F8>", _toggle_chat)

    def _console_input_loop() -> None:
        print("============================================================================", flush=True)
        print("  CHAT EN VIVO CON LUCY MACLEAN (REFUGIO 33) LISTO", flush=True)
        print("  - La ventana flotante 'Comunicaciones Pip-Boy Vault-Tec' está abierta.", flush=True)
        print("  - También puedes escribir aquí en la consola y pulsar ENTER.", flush=True)
        print("============================================================================\n", flush=True)
        while True:
            try:
                line = input("TÚ > ").strip()
            except EOFError:
                break
            if not line:
                continue
            ui_queue.put(("player", "Tú (Refugio 111)", line))
            ui_queue.put(("status", "", "● Lucy está pensando..."))
            _send_to_bridge(line)

    threading.Thread(target=_console_input_loop, daemon=True).start()

    def _poll():
        try:
            while True:
                role, speaker, text = ui_queue.get_nowait()
                _append_msg(role, speaker, text)
        except queue.Empty:
            pass
        root.after(45, _poll)

    root.after(100, entry.focus_force)
    root.after(45, _poll)
    root.mainloop()


if __name__ == "__main__":
    main()
