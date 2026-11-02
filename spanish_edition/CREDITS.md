# Credits, Licenses & Open Modding Policy Compliance

**Mod Title:** Lucy MacLean — Vault 33 Generative AI Companion for Fallout 4
**Version:** 1.0.0
**License of this Mod:** **100% Open Permissions (MIT / Creative Commons Attribution — Free to modify, reuse assets, translate, and redistribute)**

---

## 1. Open Modding Policy & Universal Compatibility Statement

In strict compliance with our **Open Modding Policy**:
- **100% Open Permissions:** Anyone in the community is free to study, modify, translate, repackage, or build upon this mod and its Python/Papyrus source code without asking for permission.
- **Zero Creation Club / Creations Dependencies:** This mod requires **only** base `Fallout4.esm`. It contains zero dependencies on Creation Club content or Next-Gen/Anniversary Edition exclusives.
- **Universal Compatibility (`1.10.163` + Next-Gen / AE `1.10.980+`):**
  - Plugin header compiled as **`HEDR v1.0`** with all custom FormIDs allocated at `>= 0x01000800`.
  - Archive packages compiled as **`BA2 Version 1` (`GNRL v1` & `DX10 v1`)** so they load natively on **Fallout 4 `1.10.163` (Pre-Next-Gen / GOG / Downgraded)** as well as **Next-Gen / Anniversary Edition (`1.10.980+`)** without patches.
  - **Zero F4SE Dependency:** Works out-of-the-box on pure Vanilla Fallout 4 via native Papyrus FormID telemetry (`GetFormID()`) resolved by the local Python bridge (`fo4_resolver.py`).
- **100% Local AI Execution (Zero Cloud APIs, Zero Paid Subscriptions):** Both the LLM brain (Ollama + `qwen2.5:7b`) and the synchronous neural voice engine (`kokoro-onnx`) run entirely on your local PC hardware at zero cost.

---

## 2. Full Attribution & Third-Party Open-Source Credits

We gratefully acknowledge and credit the original creators whose open-source work and research made this project possible:

1. **Bagomojo — [`rdr2-companion`](https://github.com/Bagomojo/rdr2-companion)**
   - **Original Author:** [Bagomojo](https://github.com/Bagomojo) ([Reddit Architecture Post](https://www.reddit.com/r/ClaudeAI/comments/1xle862/i_created_a_rdr2_mod_in_code_which_allowed_me_to/))
   - **License:** MIT License (Open Permissions: commercial/non-commercial use, modification, and redistribution permitted)
   - **Contribution:** Inspiration and foundational architecture for the game-to-LLM bridge (`decide`, `memory`, `LINE_STYLES` rotation, 4-gram anti-repeat filter, and persistent companion state), adapted and re-engineered here for Fallout 4, local Ollama (`qwen2.5:7b`), non-F4SE FormID resolution, and synchronous local Kokoro-ONNX TTS.

2. **Kokoro-ONNX & Kokoro-82M TTS**
   - **Original Authors:** [hexgrad (Kokoro-82M)](https://huggingface.co/hexgrad/Kokoro-82M) & [thewh1teagle (`kokoro-onnx`)](https://github.com/thewh1teagle/kokoro-onnx)
   - **License:** Apache License 2.0 (Open Permissions)
   - **Contribution:** High-speed local neural text-to-speech synthesis in English (`en-us`), enabling ~250 ms Time-To-First-Audio clause streaming on CPU with zero GPU VRAM overhead.

3. **Ollama & Qwen2.5 (`qwen2.5:7b`)**
   - **Original Authors:** [Ollama Team](https://ollama.com/) (MIT License) & [Qwen Team / Alibaba Cloud](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) (Apache License 2.0)
   - **Contribution:** Local GPU-accelerated LLM inference with structured JSON schema output (`DECISION_SCHEMA`).

4. **Fallout 4 Base Game Assets & Fallout TV Series Character Homage**
   - **Bethesda Game Studios / Amazon MGM Studios / Kilter Films:** All 3D meshes, base textures, and animations are referenced from `Fallout4.esm`, with custom standalone Vault 33 material swaps (`vaultsuitMnumber33.bgsm`) and custom DDS number decals (`vaultsuit33_d.dds` / `vaultsuit33_n.dds`) generated procedurally for `LucyCompanionFO4`. Lucy MacLean is a fan-made non-commercial homage to the *Fallout* television series character portrayed by Ella Purnell.
