"""Interactive Vault-Tec Pip-Boy Live Chat Window for Lucy MacLean (Fallout 4 — Large 4K Couch-Readable Edition).

- Pure standard Python & Tkinter implementation.
- Sized generously (~70% screen width x ~52% screen height) so it is effortless to read from a distance on 4K displays.
- Large 18pt default typography with live [A-] / [A+] buttons in the header to adjust text size on the fly.
- Input bar is packed at `side="bottom"` first with generous vertical padding (`ipady=8`) so large text is never clipped.
- Connects to `http://127.0.0.1:7777/chat_stream` for real-time synchronized voice + text streaming.
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
    root.title("Vault-Tec Pip-Boy Comms — Lucy MacLean (F8 / ESC: Minimize)")
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

    # 1. Pack TOP header first
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
        text="[ENTER: Send  |  ESC or F8: Minimize]",
        font=("Consolas", 12, "bold"),
        fg="#A5D6A7",
        bg="#08110B",
    )
    help_lbl.pack(side="right", padx=(12, 0))

    # 2. Pack BOTTOM input bar & status line BEFORE history so they ALWAYS have full height and are never clipped
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
        value="● Ready — Type your message to Lucy in English and press ENTER (Press F8 or ESC anytime to minimize)."
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

    # 3. Pack CENTER conversation history last (`expand=True`) to fill the middle space
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
        text=" Minimize ",
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
        "--- Pip-Boy Direct Comms established with Lucy MacLean (Vault 33). Ask her anything in English! (Use [A+] / [A-] at the top right to adjust text size, or press F8 / ESC to minimize) ---",
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
                            ui_queue.put(("status", "", "● Lucy is speaking... (Type your next reply anytime)"))
                    elif pkt.get("type") == "done":
                        dec = pkt.get("decision") or {}
                        final_say = (dec.get("say") or final_say).strip()
            dt = time.perf_counter() - t0
            if final_say:
                print(f"\nLUCY ({dt:.1f}s) > {final_say}\nYOU > ", end="", flush=True)
                ui_queue.put(("lucy_done", "Lucy MacLean", final_say))
                ui_queue.put(
                    (
                        "status",
                        "",
                        f"● Lucy replied ({dt:.1f}s) — Type another message and press ENTER (or ESC/F8 to minimize).",
                    )
                )
            else:
                ui_queue.put(("status", "", "● Ready — Type your message and press ENTER."))
        except Exception as e:
            ui_queue.put(("sys", "", f"[Error connecting to Bridge at 127.0.0.1:7777: {e}]"))
            ui_queue.put(("status", "", "● Please check that the Bridge server is running."))

    def _on_submit(event=None):
        msg = entry.get().strip()
        if not msg:
            return "break"
        entry.delete(0, "end")
        _append_msg("player", "You (Vault 111)", msg)
        status_var.set("● Lucy is thinking...")
        threading.Thread(target=_send_to_bridge, args=(msg,), daemon=True).start()
        return "break"

    entry.bind("<Return>", _on_submit)
    entry.bind("<Escape>", _toggle_chat)
    entry.bind("<F8>", _toggle_chat)
    root.bind("<Escape>", _toggle_chat)
    root.bind("<F8>", _toggle_chat)

    def _console_input_loop() -> None:
        print("============================================================================", flush=True)
        print("  LIVE CHAT WITH LUCY MACLEAN (VAULT 33) READY", flush=True)
        print("  - The floating 'Vault-Tec Pip-Boy Comms' window is open on screen.", flush=True)
        print("  - You can also type here in the console and press ENTER.", flush=True)
        print("============================================================================\n", flush=True)
        while True:
            try:
                line = input("YOU > ").strip()
            except EOFError:
                break
            if not line:
                continue
            ui_queue.put(("player", "You (Vault 111)", line))
            ui_queue.put(("status", "", "● Lucy is thinking..."))
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
