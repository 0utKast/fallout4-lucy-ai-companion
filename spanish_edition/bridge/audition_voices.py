"""Generates WAV voice samples for Lucy MacLean across candidate English Kokoro voices."""

import os
import sys
import time
from pathlib import Path

if "PHONEMIZER_ESPEAK_PATH" not in os.environ and Path(r"C:\Program Files\eSpeak NG").exists():
    os.environ["PHONEMIZER_ESPEAK_PATH"] = r"C:\Program Files\eSpeak NG"

import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from voice_local import LocalVoice

CANDIDATE_VOICES = [
    ("lucy_blend", "Custom Blend (60% af_heart + 25% af_bella + 15% bf_emma — Ella Purnell style)"),
    ("af_heart", "American Female 'Heart' (Warm, expressive, Grade A)"),
    ("af_bella", "American Female 'Bella' (Bright, enthusiastic Vault-girl energy)"),
    ("af_sky", "American Female 'Sky' (Light, youthful, innocent)"),
    ("af_sarah", "American Female 'Sarah' (Clear, articulate committee leader)"),
    ("bf_emma", "British Female 'Emma' (Crisp articulation)"),
]

SAMPLE_LINE = (
    "Okey-dokey! Back in Vault 33, the Golden Rule says we should always resolve disputes "
    "with a polite committee vote... though if that Mister Handy calls me Snip-Snip, I'm shooting first!"
)


def main():
    out_dir = Path(__file__).parent / "voice_samples"
    out_dir.mkdir(exist_ok=True)
    lv = LocalVoice(enabled=True, voice_name="lucy_blend")
    if not lv.kokoro:
        print("Kokoro not available.")
        return

    print(f"Generating Lucy MacLean voice samples in: {out_dir}\n")
    for v_id, desc in CANDIDATE_VOICES:
        t0 = time.perf_counter()
        style = lv.resolve_voice(v_id)
        samples, sr = lv.kokoro.create(SAMPLE_LINE, voice=style, speed=1.04, lang="en-us")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        wav_path = out_dir / f"lucy_{v_id}.wav"
        sf.write(str(wav_path), samples, sr)
        print(f"  - {v_id:12s} ({elapsed_ms:4.0f} ms) -> {wav_path.name} | {desc}")


if __name__ == "__main__":
    main()
