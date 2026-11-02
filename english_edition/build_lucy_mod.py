# -*- coding: utf-8 -*-
"""
Builder for 'Lucy MacLean — Vault 33 Generative AI Companion'
  - LucyCompanionFO4.esp (HEDR v1.0, FormIDs >= 0x01000800)
  - LucyCompanionFO4 - Main.ba2 (BTDX v1 GNRL: Papyrus .pex + Vault 33 .bgsm materials)
  - LucyCompanionFO4 - Textures.ba2 (BTDX v1 DX10: VaultSuitNumber33 _d/_n/_s DDS mipmaps)

Compliance (AGENTS.md):
  - HEDR v1.0 (Universal compatibility: Fallout 4 1.10.163 Pre-Next-Gen/GOG + 1.10.980+ Next-Gen/AE)
  - BA2 v1 (GNRL v1 & DX10 v1)
  - Zero Creation Club, DLC, or F4SE dependencies (Only Fallout4.esm)
  - 100% Open Permissions & Standalone
"""

import os
import shutil
import struct
import subprocess
import sys
import zlib

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
FO4_ROOT = r"C:\Program Files (x86)\Steam\steamapps\common\Fallout 4"
FO4_DATA_DIR = os.path.join(FO4_ROOT, "Data")
FO4_ESM_PATH = os.path.join(FO4_DATA_DIR, "Fallout4.esm")
PAPYRUS_COMPILER = os.path.join(FO4_ROOT, "Papyrus Compiler", "PapyrusCompiler.exe")

PAPYRUS_SRC_DIR = os.path.join(THIS_DIR, "papyrus_src")
PAPYRUS_OUT_DIR = os.path.join(THIS_DIR, "papyrus_out")
BUILD_OUT_DIR = os.path.join(THIS_DIR, "build_out")

ESP_NAME = "LucyCompanionFO4.esp"
BA2_NAME = "LucyCompanionFO4 - Main.ba2"
TEX_BA2_NAME = "LucyCompanionFO4 - Textures.ba2"

INSTALL_TO_FO4_DATA = "--install" in sys.argv


def pack_sub(st: str, val_bytes: bytes) -> bytes:
    b_st = st.encode("ascii")
    n = len(val_bytes)
    if n <= 0xFFFF:
        return struct.pack("<4sH", b_st, n) + val_bytes
    return b"XXXX\x04\x00" + struct.pack("<I4sH", n, b_st, 0) + val_bytes


def pack_zstr(st: str, text: str) -> bytes:
    return pack_sub(st, text.encode("utf-8") + b"\x00")


def pack_record(
    rt: str,
    fid: int,
    body_bytes: bytes,
    flags: int = 0,
    fver: int = 131,
    v2: int = 0,
) -> bytes:
    return (
        struct.pack(
            "<4sIIIIHH",
            rt.encode("ascii"),
            len(body_bytes),
            flags,
            fid,
            0,
            fver,
            v2,
        )
        + body_bytes
    )


def pack_grup_top(label: bytes, records_bytes: bytes) -> bytes:
    return (
        b"GRUP"
        + struct.pack("<I4sIII", 24 + len(records_bytes), label, 0, 0, 0)
        + records_bytes
    )


def build_simple_vmad(script_name: str, props: list[tuple[str, int]] | None = None) -> bytes:
    sname = script_name.encode("ascii")
    props = props or []
    prop_bytes = bytearray()
    for pname, pfid in props:
        pb = pname.encode("ascii")
        prop_bytes.extend(struct.pack("<H", len(pb)) + pb)
        prop_bytes.extend(struct.pack("<BBHHI", 1, 1, 0, 0xFFFF, pfid))
    return (
        struct.pack("<HHHH", 6, 2, 1, len(sname))
        + sname
        + struct.pack("<BH", 0, len(props))
        + bytes(prop_bytes)
    )


def make_ctda_getglobalvalue(glob_fid: int, val: float = 1.0) -> bytes:
    return struct.pack(
        "<B3sfH2sIIIIi",
        0x00,
        b"\x00\x00\x00",
        val,
        0x004A,
        b"\x00\x00",
        glob_fid,
        0,
        0,
        0,
        -1,
    )


def _ba2_crc32(data: bytes) -> int:
    crc = 0
    for b in data:
        c = (crc ^ b) & 0xFF
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if (c & 1) else (c >> 1)
        crc = (crc >> 8) ^ c
    return crc


def compile_papyrus_scripts() -> None:
    os.makedirs(PAPYRUS_OUT_DIR, exist_ok=True)
    base_scripts = os.path.join(FO4_DATA_DIR, "Scripts", "Source", "Base")
    cmd = [
        PAPYRUS_COMPILER,
        PAPYRUS_SRC_DIR,
        "-f=Institute_Papyrus_Flags.flg",
        f"-i={base_scripts};{PAPYRUS_SRC_DIR}",
        f"-o={PAPYRUS_OUT_DIR}",
        "-a",
    ]
    subprocess.run(cmd, check=True)
    print("[Papyrus] Compiled 6 scripts into papyrus_out/.")


def build_vault33_materials() -> dict[str, str]:
    result_map: dict[str, str] = {}
    mat_ba2_path = os.path.join(FO4_DATA_DIR, "Fallout4 - Materials.ba2")
    if not os.path.exists(mat_ba2_path):
        return result_map

    with open(mat_ba2_path, "rb") as mf:
        hdr = mf.read(24)
        _m, _v, _t, nf, ntbl = struct.unpack("<4sI4sIQ", hdr)
        mf.seek(ntbl)
        names = [
            mf.read(struct.unpack("<H", mf.read(2))[0]).decode("utf-8", "replace")
            for _ in range(nf)
        ]
        vs_num81_idx = None
        vs_num81_dirty_idx = None
        for idx, nm in enumerate(names):
            low = nm.lower().replace("/", "\\")
            if low == "materials\\clothes\\vaultsuit\\vaultsuitmnumber81.bgsm":
                vs_num81_idx = idx
            elif low == "materials\\clothes\\vaultsuit\\vaultsuitmnumber81dirty.bgsm":
                vs_num81_dirty_idx = idx

        vs_bgsm_dir = os.path.join(THIS_DIR, "assets", "materials", "clothes", "vaultsuit")
        os.makedirs(vs_bgsm_dir, exist_ok=True)
        for v_idx, fn_33 in [
            (vs_num81_idx, "vaultsuitMnumber33.bgsm"),
            (vs_num81_dirty_idx, "vaultsuitMnumber33dirty.bgsm"),
        ]:
            if v_idx is not None:
                mf.seek(24 + v_idx * 36)
                _nh, _ext, _dh, _unk, ofs, packed_sz, unpacked_sz, _align = struct.unpack(
                    "<I4sIIQIII", mf.read(36)
                )
                mf.seek(ofs)
                raw_vs_bgsm = (
                    zlib.decompress(mf.read(packed_sz))
                    if packed_sz > 0
                    else mf.read(unpacked_sz)
                )
                patched_vs_bgsm = raw_vs_bgsm.replace(
                    b"VaultSuitNumber81", b"VaultSuitNumber33"
                )
                vs_path = os.path.join(vs_bgsm_dir, fn_33)
                with open(vs_path, "wb") as wf:
                    wf.write(patched_vs_bgsm)
                result_map[f"materials\\clothes\\vaultsuit\\{fn_33.lower()}"] = vs_path
                print(f"  [Material] Packaged Vault 33 Jumpsuit Number BGSM: {fn_33}")

    return result_map


def _transform_bc16_mips_81_to_33(raw_mips: bytes, w0: int, h0: int, mips: int) -> bytes:
    """Transforms Vault 81 number decal ('81') into Vault 33 ('33') across all mipmaps."""
    out_mips = bytearray()
    off = 0
    for m in range(mips):
        mw = max(1, w0 >> m)
        mh = max(1, h0 >> m)
        bw = max(1, (mw + 3) // 4)
        bh = max(1, (mh + 3) // 4)
        sz = bw * bh * 16
        chunk = raw_mips[off : off + sz]
        off += sz
        if bw >= 16 and bh >= 16:
            bg_block = chunk[0:16]
            bg_row = bg_block * bw

            def sc_x(bx256: int) -> int:
                return int(round(bx256 * bw / 256.0))

            def sc_y(by256: int) -> int:
                return int(round(by256 * bh / 256.0))

            # Source digit '8' in VaultSuitNumber81 is at X=[44..148] (width 104 blocks)
            sx3, ex3 = sc_x(44), sc_x(148)
            w3 = ex3 - sx3

            # Place two '3' digits side-by-side centered at X=128:
            # Left '3' (tens) at dx_left=19..123, Right '3' (units) at dx_right=133..237
            dx_left = sc_x(19)
            dx_right = sc_x(133)

            y_u0, y_u1 = sc_y(91), sc_y(113)
            y_l0, y_l1 = sc_y(143), sc_y(166)
            y_m0, y_m1 = sc_y(110), sc_y(146)
            cut_loop = sc_x(45)
            cut_mid = sc_x(42)

            for by in range(bh):
                out_row = bytearray(bg_row)
                r_ofs = by * bw * 16
                if (y_u0 <= by < y_u1) or (y_l0 <= by < y_l1):
                    cx = cut_loop
                elif y_m0 <= by < y_m1:
                    cx = cut_mid
                else:
                    cx = 0
                carved_3_slice = chunk[
                    r_ofs + (sx3 + cx) * 16 : r_ofs + (sx3 + w3) * 16
                ]
                # Tens digit '3'
                out_row[(dx_left + cx) * 16 : (dx_left + w3) * 16] = carved_3_slice
                # Units digit '3'
                out_row[(dx_right + cx) * 16 : (dx_right + w3) * 16] = carved_3_slice
                out_mips.extend(out_row)
        else:
            out_mips.extend(chunk)
    return bytes(out_mips)


def _extract_vanilla_dx10_mips(ba2_filename: str, target_rel: str) -> bytes | None:
    ba2_path = os.path.join(FO4_DATA_DIR, ba2_filename)
    if not os.path.exists(ba2_path):
        return None
    with open(ba2_path, "rb") as f:
        hdr = f.read(24)
        _m, _v, _t, nf, ntbl = struct.unpack("<4sI4sIQ", hdr)
        f.seek(ntbl)
        names = [
            f.read(struct.unpack("<H", f.read(2))[0]).decode("utf-8", "replace")
            for _ in range(nf)
        ]
        f.seek(24)
        for nm in names:
            entry = f.read(24)
            _nh, _ext, _dh, _unk, nch, _ch_sz, _h, _w, _mips, _fmt, _fl = struct.unpack(
                "<I4sIBBHHHBBH", entry
            )
            chunks = [struct.unpack("<QIIHHI", f.read(24)) for _ in range(nch)]
            if nm.lower().replace("/", "\\") == target_rel.lower().replace("/", "\\"):
                raw_mips = bytearray()
                for cofs, cpk, cunpk, _smip, _emip, _align in chunks:
                    f.seek(cofs)
                    raw_mips.extend(
                        zlib.decompress(f.read(cpk)) if cpk > 0 else f.read(cunpk)
                    )
                return bytes(raw_mips)
    return None


def build_vault33_textures_ba2(dst_tex_ba2: str) -> None:
    tex_records: list[tuple[str, int, int, int, int, list[tuple[int, int, int, int]], bytes]] = []
    chunks_1024_bc16 = [
        (0, 1048576, 0, 0),
        (1048576, 262144, 1, 1),
        (1048576 + 262144, 87408, 2, 10),
    ]
    chunks_512_bc16 = [
        (0, 262144, 0, 0),
        (262144, 87408, 1, 9),
    ]
    for ba2_src, src_rel, dst_33_rel, w0, h0, mips, dxgi_fmt, cdefs in [
        (
            "Fallout4 - Textures2.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81dirty_d.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33dirty_d.DDS",
            1024,
            1024,
            11,
            77,
            chunks_1024_bc16,
        ),
        (
            "Fallout4 - Textures2.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81dirty_n.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33dirty_n.DDS",
            1024,
            1024,
            11,
            83,
            chunks_1024_bc16,
        ),
        (
            "Fallout4 - Textures2.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81dirty_s.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33dirty_s.DDS",
            512,
            512,
            10,
            83,
            chunks_512_bc16,
        ),
        (
            "Fallout4 - Textures5.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81_d.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33_d.DDS",
            1024,
            1024,
            11,
            77,
            chunks_1024_bc16,
        ),
        (
            "Fallout4 - Textures5.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81_n.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33_n.DDS",
            1024,
            1024,
            11,
            83,
            chunks_1024_bc16,
        ),
        (
            "Fallout4 - Textures5.ba2",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber81_s.DDS",
            "Textures\\Clothes\\VaultSuit\\VaultSuitNumber33_s.DDS",
            512,
            512,
            10,
            83,
            chunks_512_bc16,
        ),
    ]:
        orig_mips = _extract_vanilla_dx10_mips(ba2_src, src_rel)
        if orig_mips is not None:
            v33_mips = _transform_bc16_mips_81_to_33(orig_mips, w0, h0, mips)
            tex_records.append((dst_33_rel, w0, h0, mips, dxgi_fmt, cdefs, v33_mips))

    total_chunks = sum(len(r[5]) for r in tex_records)
    hdr_size = 24 + 24 * len(tex_records) + 24 * total_chunks
    cur_ofs = hdr_size
    entry_headers_and_chunks: list[bytes] = []
    payloads: list[bytes] = []
    name_bytes_list: list[bytes] = []

    for tex_rel, w0, h0, mips, dxgi_fmt, cdefs, r_mips in tex_records:
        norm_bs = tex_rel.replace("/", "\\")
        dir_part, base_part = norm_bs.rsplit("\\", 1)
        stem_part = base_part.rsplit(".", 1)[0]
        comp_chunks = []
        for st_off, sz_unpk, st_mip, end_mip in cdefs:
            raw_slice = r_mips[st_off : st_off + sz_unpk]
            comp_slice = zlib.compress(raw_slice)
            comp_chunks.append((comp_slice, sz_unpk, st_mip, end_mip))
        tex_entry_hdr = bytearray(
            struct.pack(
                "<I4sIBBHHHBBH",
                _ba2_crc32(stem_part.lower().encode("ascii")),
                b"dds\x00",
                _ba2_crc32(dir_part.lower().encode("ascii")),
                0,
                len(comp_chunks),
                24,
                h0,
                w0,
                mips,
                dxgi_fmt,
                0x0800,
            )
        )
        for comp_slice, sz_unpk, st_mip, end_mip in comp_chunks:
            tex_entry_hdr.extend(
                struct.pack(
                    "<QIIHHI", cur_ofs, len(comp_slice), sz_unpk, st_mip, end_mip, 0xBAADF00D
                )
            )
            payloads.append(comp_slice)
            cur_ofs += len(comp_slice)
        entry_headers_and_chunks.append(bytes(tex_entry_hdr))
        nb = norm_bs.encode("ascii")
        name_bytes_list.append(struct.pack("<H", len(nb)) + nb)

    name_tbl_ofs = cur_ofs
    with open(dst_tex_ba2, "wb") as wf:
        wf.write(
            struct.pack("<4sI4sIQ", b"BTDX", 1, b"DX10", len(tex_records), name_tbl_ofs)
        )
        for eh in entry_headers_and_chunks:
            wf.write(eh)
        for pl in payloads:
            wf.write(pl)
        for nb in name_bytes_list:
            wf.write(nb)
    print(
        f"[BA2 DX10] {TEX_BA2_NAME} built successfully: {dst_tex_ba2} ({len(tex_records)} textures)"
    )


def build_ba2_archive(dst_ba2: str, file_map: dict[str, str]) -> None:
    entries = []
    names = []
    payloads = []

    for norm_key in sorted(file_map.keys()):
        src_path = file_map[norm_key]
        with open(src_path, "rb") as rf:
            raw_bytes = rf.read()
        norm_bs = norm_key.replace("/", "\\")
        dir_part, base_part = norm_bs.rsplit("\\", 1)
        stem_part, ext_part = base_part.rsplit(".", 1)
        ext_bytes = ext_part.lower().encode("ascii")[:4].ljust(4, b"\x00")
        entries.append([
            _ba2_crc32(stem_part.lower().encode("ascii")),
            ext_bytes,
            _ba2_crc32(dir_part.lower().encode("ascii")),
            1048832,
            0,
            0,
            len(raw_bytes),
            0xBAADF00D,
        ])
        names.append(norm_bs)
        payloads.append(raw_bytes)

    cur_offset = 24 + 36 * len(entries)
    for i in range(len(entries)):
        entries[i][4] = cur_offset
        cur_offset += len(payloads[i])
    name_tbl_offset = cur_offset

    with open(dst_ba2, "wb") as wf:
        wf.write(b"BTDX")
        wf.write(struct.pack("<I4sIQ", 1, b"GNRL", len(entries), name_tbl_offset))
        for e in entries:
            wf.write(struct.pack("<I4sIIQIII", *e))
        for p in payloads:
            wf.write(p)
        for name in names:
            nb = name.encode("utf-8")
            wf.write(struct.pack("<H", len(nb)) + nb)

    print(f"[BA2 GNRL] {BA2_NAME} built successfully: {dst_ba2} ({len(entries)} packaged files)")


def extract_esm_templates() -> dict:
    needed_records = {
        (b"MGEF", 0x00106E53): "mgef_self_script",
        (b"ALCH", 0x0004F4A6): "alch_stealthboy",
        (b"ARMA", 0x000976B6): "arma_v111_clean",
        (b"ARMO", 0x000976B7): "armo_v111_clean",
        (b"BOOK", 0x0024800F): "book_note",
        (b"NPC_", 0x0002A82A): "npc_tina",
        (b"NPC_", 0x0018B5F7): "npc_preset_f1",
        (b"PACK", 0x00003641): "pack_stay_editor_loc",
        (b"PERK", 0x00178D54): "perk_piper",
    }
    found: dict = {}

    with open(FO4_ESM_PATH, "rb") as f:
        data = f.read()

    p = 0
    n = len(data)
    while p < n:
        rt = data[p : p + 4]
        if rt == b"GRUP":
            gsz, lbl, gt, _stmp, _unk = struct.unpack("<I4sIII", data[p + 4 : p + 24])
            if gt == 0 and lbl == b"WRLD":
                wp = p + 24
                whdr = data[wp : wp + 24]
                wsz = struct.unpack("<I", whdr[4:8])[0]
                wpay = data[wp + 24 : wp + 24 + wsz]
                g1p = wp + 24 + wsz
                chdr = data[g1p + 24 : g1p + 48]
                csz = struct.unpack("<I", chdr[4:8])[0]
                cpay = data[g1p + 48 : g1p + 48 + csz]
                found["wrld_3c_pay"] = wpay
                found["cell_18aa2_raw"] = chdr + cpay
            p += 24
            continue

        sz, fl, fid, _rev, fver, v2 = struct.unpack("<IIIIHH", data[p + 4 : p + 24])
        if (rt, fid) in needed_records:
            body = data[p + 24 : p + 24 + sz]
            if fl & 0x00040000:
                body = zlib.decompress(body[4:])
            found[needed_records[(rt, fid)]] = (fl & ~0x00040000, fver, v2, body)
        p += 24 + sz

    return found


def build_esp_file(tpl: dict, dst_esp: str) -> None:
    # 1. GLOB:
    #   0x01000801 GlobLucyWaitMode (1.0 default = Waiting at Vault 111 Overlook)
    #   0x01000802 GlobLucyRecruited (0.0 default = Not Recruited yet, 1.0 = Active Companion)
    #   0x01000803 GlobLucyAffinity (250.0 default, range 0.0..1000.0)
    def make_glob(fid: int, edid: str, val: float) -> bytes:
        subs = (
            pack_zstr("EDID", edid)
            + pack_sub("FNAM", b"s")
            + pack_sub("FLTV", struct.pack("<f", val))
        )
        return pack_record("GLOB", fid, subs, fver=107)

    grup_glob = pack_grup_top(
        b"GLOB",
        make_glob(0x01000801, "GlobLucyWaitMode", 1.0)
        + make_glob(0x01000802, "GlobLucyRecruited", 0.0)
        + make_glob(0x01000803, "GlobLucyAffinity", 250.0),
    )

    # 2. MGEF: 0x01000850..0x01000853 (Self-targeted Fire-and-Forget command effects)
    _, _, _, mgef_raw = tpl["mgef_self_script"]

    def make_cmd_mgef(
        new_fid: int, edid: str, full_name: str, script_name: str, alch_fid: int
    ) -> bytes:
        vmad_b = build_simple_vmad(
            script_name,
            [("LucyQuest", 0x01000800), ("CommandPotion", alch_fid)],
        )
        subs = bytearray()
        subs.extend(pack_zstr("EDID", edid))
        subs.extend(pack_sub("VMAD", vmad_b))
        subs.extend(pack_zstr("FULL", full_name))
        sp_m = 0
        while sp_m + 6 <= len(mgef_raw):
            st_m = mgef_raw[sp_m : sp_m + 4].decode("ascii", "ignore")
            ss_m = struct.unpack_from("<H", mgef_raw, sp_m + 4)[0]
            if st_m in ("EDID", "VMAD", "FULL", "DNAM"):
                pass
            else:
                subs.extend(mgef_raw[sp_m : sp_m + 6 + ss_m])
            sp_m += 6 + ss_m
        subs.extend(pack_zstr("DNAM", ""))
        return pack_record("MGEF", new_fid, bytes(subs))

    grup_mgef = pack_grup_top(
        b"MGEF",
        make_cmd_mgef(
            0x01000850,
            "MgefLucyCmdAsk",
            "Lucy Command: Ask What Do You Think",
            "LucyCmdAskScript",
            0x01000840,
        )
        + make_cmd_mgef(
            0x01000851,
            "MgefLucyCmdFollowWait",
            "Lucy Command: Toggle Follow / Wait Here",
            "LucyCmdFollowWaitScript",
            0x01000841,
        )
        + make_cmd_mgef(
            0x01000852,
            "MgefLucyCmdLore",
            "Lucy Command: Vault 33 & Wasteland Chat",
            "LucyCmdLoreScript",
            0x01000842,
        )
        + make_cmd_mgef(
            0x01000853,
            "MgefLucyCmdSummon",
            "Lucy Command: Summon Lucy Here",
            "LucyCmdSummonScript",
            0x01000843,
        ),
    )

    # 3. MSWP: 0x01000810 (VaultSuit33CleanM) + 0x01000811 (VaultSuit33CleanF)
    mswp_33_m_subs = (
        pack_zstr("EDID", "VaultSuit33CleanM")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitdirtymtrim.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitcleanmtrim.bgsm")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitdirtym.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitcleanm.bgsm")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitmnumber111dirty.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitmnumber33.bgsm")
    )
    mswp_33_f_subs = (
        pack_zstr("EDID", "VaultSuit33CleanF")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitdirtyftrim.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitcleanftrim.bgsm")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitmnumber111dirty.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitmnumber33.bgsm")
        + pack_zstr("BNAM", "clothes\\vaultsuit\\vaultsuitdirtyf.bgsm")
        + pack_zstr("SNAM", "clothes\\vaultsuit\\vaultsuitcleanf.bgsm")
    )
    grup_mswp = pack_grup_top(
        b"MSWP",
        pack_record("MSWP", 0x01000810, mswp_33_m_subs, fver=118, v2=1)
        + pack_record("MSWP", 0x01000811, mswp_33_f_subs, fver=118, v2=1),
    )

    # 4. ARMA: 0x01000812 (AAVault33SuitClean)
    _, arma_fver, arma_v2, arma_raw = tpl["arma_v111_clean"]
    arma_33_subs = bytearray()
    arma_33_subs.extend(pack_zstr("EDID", "AAVault33SuitClean"))
    sp_aa = 0
    while sp_aa + 6 <= len(arma_raw):
        st_aa = arma_raw[sp_aa : sp_aa + 4].decode("ascii", "ignore")
        ss_aa = struct.unpack_from("<H", arma_raw, sp_aa + 4)[0]
        if st_aa == "EDID":
            pass
        elif st_aa == "MO2S":
            arma_33_subs.extend(pack_sub("MO2S", struct.pack("<I", 0x01000810)))
        elif st_aa == "MO3S":
            arma_33_subs.extend(pack_sub("MO3S", struct.pack("<I", 0x01000811)))
        else:
            arma_33_subs.extend(arma_raw[sp_aa : sp_aa + 6 + ss_aa])
        sp_aa += 6 + ss_aa
    grup_arma = pack_grup_top(
        b"ARMA",
        pack_record("ARMA", 0x01000812, bytes(arma_33_subs), fver=arma_fver, v2=arma_v2),
    )

    # 5. ARMO: 0x01000813 (ArmoVault33LucyJumpsuit)
    _, armo_fver, armo_v2, armo_raw = tpl["armo_v111_clean"]
    armo_33_subs = bytearray()
    armo_33_subs.extend(pack_zstr("EDID", "ArmoVault33LucyJumpsuit"))
    sp_ar = 0
    while sp_ar + 6 <= len(armo_raw):
        st_ar = armo_raw[sp_ar : sp_ar + 4].decode("ascii", "ignore")
        ss_ar = struct.unpack_from("<H", armo_raw, sp_ar + 4)[0]
        if st_ar == "EDID":
            pass
        elif st_ar == "FULL":
            armo_33_subs.extend(pack_zstr("FULL", "Vault 33 Jumpsuit"))
        elif st_ar == "DESC":
            armo_33_subs.extend(
                pack_zstr(
                    "DESC",
                    "Standard-issue blue and gold Vault-Tec jumpsuit from Vault 33 (Santa Monica), featuring the golden 33 on the back and collar.",
                )
            )
        elif st_ar == "MODL" and ss_ar == 4:
            armo_33_subs.extend(pack_sub("MODL", struct.pack("<I", 0x01000812)))
        elif st_ar == "DAMA":
            # Give +15 Physical, +20 Energy, +25 Radiation Resistance
            armo_33_subs.extend(
                pack_sub(
                    "DAMA",
                    struct.pack("<IIII", 0x00060A81, 20, 0x00060A85, 25),
                )
            )
        else:
            armo_33_subs.extend(armo_raw[sp_ar : sp_ar + 6 + ss_ar])
        sp_ar += 6 + ss_ar
    grup_armo = pack_grup_top(
        b"ARMO",
        pack_record("ARMO", 0x01000813, bytes(armo_33_subs), fver=armo_fver, v2=armo_v2),
    )

    # 5b. BOOK: 0x01000860 (BookLucyVault33Journal — Lucy MacLean's Expedition Journal)
    _, book_fver, book_v2, book_raw = tpl["book_note"]
    book_subs = bytearray()
    book_subs.extend(pack_zstr("EDID", "BookLucyVault33Journal"))
    journal_text_en = (
        "FIELD JOURNAL OF LUCY MACLEAN — VAULT 33 DWELLER\n\n"
        "Entry 1 (Santa Monica -> Griffith Observatory):\n"
        "I left Vault 33 to rescue my father, Hank MacLean, after Lee Moldaver kidnapped him. "
        "On the surface I survived torture at the hands of Cooper Howard (The Ghoul), who cut off my index finger "
        "outside the Super Duper Mart and sold me to the medical robot Snip-Snip—yet I refused to become like him.\n\n"
        "Entry 2 (The Secret of Vault 31 & New Vegas):\n"
        "At Griffith Observatory I learned the heartbreaking truth: my father was a pre-war Vault-Tec executive "
        "cryo-frozen in Vault 31 who destroyed Shady Sands and turned my mother Rose into a feral ghoul. "
        "I pursued him alongside Cooper all the way to the ruins of New Vegas.\n\n"
        "Entry 3 (The Vault 111 Emergency Transponder):\n"
        "Inside a central Vault-Tec mainframe in New Vegas, I intercepted a cryogenic pod depressurization alert "
        "broadcasting from Vault 111 in the Commonwealth. Another genuine Vault Dweller had just woken up! "
        "I crossed the country following my Pip-Boy signal to the Vault 111 exterior overlook. "
        "Okey-dokey—I hope we can travel together and prove that the Golden Rule still has a place in this world!"
    )
    sp_bk = 0
    while sp_bk + 6 <= len(book_raw):
        st_bk = book_raw[sp_bk : sp_bk + 4].decode("ascii", "ignore")
        ss_bk = struct.unpack_from("<H", book_raw, sp_bk + 4)[0]
        if st_bk == "EDID":
            pass
        elif st_bk == "FULL":
            book_subs.extend(pack_zstr("FULL", "Lucy MacLean's Expedition Journal (Vault 33)"))
        elif st_bk == "DESC":
            book_subs.extend(pack_zstr("DESC", journal_text_en))
        else:
            book_subs.extend(book_raw[sp_bk : sp_bk + 6 + ss_bk])
        sp_bk += 6 + ss_bk
    grup_book = pack_grup_top(
        b"BOOK",
        pack_record("BOOK", 0x01000860, bytes(book_subs), fver=book_fver, v2=book_v2),
    )

    # 6. ALCH: 0x01000840..0x01000843 (Pip-Boy Aid & Favorites Wheel Hotkey Items)
    _, alch_fver, alch_v2, alch_raw = tpl["alch_stealthboy"]

    def make_cmd_alch(
        new_fid: int, edid: str, full_name: str, desc_txt: str, mgef_fid: int
    ) -> bytes:
        subs = bytearray()
        subs.extend(pack_zstr("EDID", edid))
        sp_al = 0
        wrote_ef = False
        while sp_al + 6 <= len(alch_raw):
            st_al = alch_raw[sp_al : sp_al + 4].decode("ascii", "ignore")
            ss_al = struct.unpack_from("<H", alch_raw, sp_al + 4)[0]
            if st_al in ("EDID", "EFID", "EFIT"):
                if not wrote_ef and st_al == "EFID":
                    subs.extend(pack_sub("EFID", struct.pack("<I", mgef_fid)))
                    subs.extend(pack_sub("EFIT", struct.pack("<fII", 0.0, 0, 1)))
                    wrote_ef = True
            elif st_al == "FULL":
                subs.extend(pack_zstr("FULL", full_name))
            elif st_al == "DESC":
                subs.extend(pack_zstr("DESC", desc_txt))
            elif st_al == "DATA":
                subs.extend(pack_sub("DATA", struct.pack("<f", 0.0)))
            elif st_al == "ENIT":
                subs.extend(pack_sub("ENIT", struct.pack("<iIIII", 0, 0x00010001, 0, 0, 0x000F47A1)))
            else:
                subs.extend(alch_raw[sp_al : sp_al + 6 + ss_al])
            sp_al += 6 + ss_al
        return pack_record("ALCH", new_fid, bytes(subs), fver=alch_fver, v2=alch_v2)

    grup_alch = pack_grup_top(
        b"ALCH",
        make_cmd_alch(
            0x01000840,
            "AlchLucyCmdAsk",
            "[Lucy] 1. Ask: What do you think?",
            "Assign to Favorites (Q). Prompts Lucy MacLean to observe your surroundings and speak her mind via local AI & Kokoro voice.",
            0x01000850,
        )
        + make_cmd_alch(
            0x01000841,
            "AlchLucyCmdFollowWait",
            "[Lucy] 2. Order: Follow / Wait Here",
            "Assign to Favorites (Q). Toggles Lucy MacLean between Following you and Waiting at her current spot.",
            0x01000851,
        )
        + make_cmd_alch(
            0x01000842,
            "AlchLucyCmdLore",
            "[Lucy] 3. Chat: Vault 33 & Wasteland Lore",
            "Assign to Favorites (Q). Asks Lucy MacLean to share a Vault 33 memory, TV series story, or Fallout lore reflection.",
            0x01000852,
        )
        + make_cmd_alch(
            0x01000843,
            "AlchLucyCmdSummon",
            "[Lucy] 4. Call / Summon Lucy Here",
            "Assign to Favorites (Q). Teleports Lucy MacLean directly to your side and sets her to Follow mode.",
            0x01000853,
        ),
    )

    # 7. NPC_: 0x01000820 (NPC_LucyMacLean)
    # Built as a runtime CharGen World Actor (ACBS 0x00000037 -> bit 0x04 Is CharGen Face Preset enabled!)
    # with SkinHeadFemaleYoung (0x000F7E65), slender athletic build (MWGT 0.68, 0.22, 0.10),
    # 'On The Go' Ponytail (0x000F9E23 + 0x00186FC1), Deep Brown Hair (0x0019EE65), Brown Eyes (0x0014EC28),
    # and custom Ella Purnell / Lucy MacLean facial bone & morph sculpt (large round expressive eyes,
    # petite upturned nose, full pouty lips, high cheekbones, and narrow heart-shaped jaw/chin).
    _, _, _, tina_raw = tpl["npc_tina"]

    face_morph_subs = bytearray()
    # FTST: SkinHeadFemaleYoung (0x000F7E65)
    face_morph_subs.extend(pack_sub("FTST", struct.pack("<I", 0x000F7E65)))
    # QNAM: Warm fair Vault-dweller skin tone (0.97, 0.94, 0.93, 1.0)
    face_morph_subs.extend(pack_sub("QNAM", struct.pack("<4f", 0.97, 0.94, 0.93, 1.0)))

    # MSDK / MSDV: Ella Purnell Morph Preset Sliders (Smooth skin, Wide eyes, Upper/Lower lids open, Pretty petite nose, Full Pout lips)
    lucy_msdk_pairs = [
        (0x36EF3650, 1.00),   # Forehead: Smooth
        (0x36EF3673, 1.00),   # Cheeks: Smooth
        (0x36EF369A, 1.00),   # Neck: Smooth
        (0x36EF34F2, 1.00),   # Eyes: Wide 1
        (0x36EF35D7, 0.92),   # EyesUpprLidUp (opens upper eyelids wide)
        (0x36EF35D9, -0.55),  # EyesLowLidDown (opens lower eyelids down for rounder eyes)
        (0x36EF35D8, -0.45),  # EyesHoodThin (clean eyelid crease)
        (0x36EF35F0, 1.00),   # Nose: Pretty 2
        (0x36EF3562, 1.00),   # Mouth: Full Pout 1
        (0x36EF353B, 0.85),   # Ears: Small 1
    ]
    face_morph_subs.extend(
        pack_sub("MSDK", struct.pack(f"<{len(lucy_msdk_pairs)}I", *[k for k, _ in lucy_msdk_pairs]))
    )
    face_morph_subs.extend(
        pack_sub("MSDV", struct.pack(f"<{len(lucy_msdk_pairs)}f", *[v for _, v in lucy_msdk_pairs]))
    )

    # TETI / TEND: Clean Vault 33 Makeup (Arched Brows, Crisp Eyeliner & Waterline, Warm Rose Lips, Zero Blemishes)
    lucy_tints = [
        ((2, 1238), bytes.fromhex("00")),              # Thin Rounded (off)
        ((2, 1246), bytes.fromhex("64")),              # Average Arched Brows (100%)
        ((1, 1320), bytes.fromhex("385a1214003405")),  # Lipstick (natural warm rose)
        ((1, 1862), bytes.fromhex("5a382f25002c07")),  # Eye Liner Waterline
        ((1, 1860), bytes.fromhex("5a000000002007")),  # Eye Liner 6 (crisp dark lash liner)
        ((1, 1310), bytes.fromhex("302b2c2f00ffff")),  # Eye Shadow 1 (subtle warm contour)
        ((1, 1311), bytes.fromhex("18000000002007")),  # Lower Eye Shadow 1
        ((1, 1718), bytes.fromhex("00ffffffffffff")),  # Lip Color base
    ]
    for (t_type, t_idx), t_val in lucy_tints:
        face_morph_subs.extend(pack_sub("TETI", struct.pack("<HH", t_type, t_idx)))
        face_morph_subs.extend(pack_sub("TEND", t_val))

    # MRSV: Head morph weights
    face_morph_subs.extend(pack_sub("MRSV", bytes.fromhex("85ebd13e00000000000000000000000000000000")))

    # FMRI / FMRS: Ella Purnell 3D Facial Bone Regions (pos_x, pos_y, pos_z, rot_x, rot_y, rot_z, scale_x, scale_y, scale_z)
    lucy_fmrs_regions = [
        (100016, (0.35, -0.35, -0.25,  0.00,  0.00, 0.15,  0.85,  0.85,  0.85)),  # Eyes (Large, round, expressive)
        (100000, (-0.10, -0.20,  0.15,  0.22,  0.00, 0.00,  0.00,  0.00,  0.00)),  # Eyebrows - Full
        (100001, (0.10, -0.30, -0.15,  0.00,  0.00, 0.00,  0.00,  0.00,  0.00)),   # Eyebrows - Inner
        (100018, (0.00, -0.20,  0.25,  0.00,  0.00, 0.00,  0.25,  0.00,  0.00)),   # Eyebrows - Middle (Arched)
        (100002, (0.15, -0.25, -0.10,  0.00,  0.00, 0.00,  0.00,  0.00,  0.00)),   # Eyebrows - Outer
        (100024, (0.00, -0.45, -0.30,  0.00,  0.00, 0.00, -0.15,  0.00,  0.00)),   # Forehead
        (100013, (-0.15, -0.10, -0.30,  0.00,  0.00, 0.00,  0.00,  0.00,  0.00)),  # Temples
        (100003, (0.42,  0.12,  0.25,  0.00,  0.00, 0.00,  0.45,  0.00,  0.00)),   # Cheekbones (High & defined)
        (100027, (-0.15,  0.05,  0.10,  0.00,  0.00, 0.00,  0.00,  0.00,  0.00)),  # Cheekbones - Back
        (100004, (-0.20, -0.25,  0.10,  0.00,  0.00, 0.00, -0.15,  0.00,  0.00)),  # Cheeks
        (100009, (0.00, -0.18,  0.08,  0.00,  0.00, 0.00, -0.42, -0.35, -0.35)),   # Nose - Full (Petite button nose)
        (100017, (0.00, -0.25, -0.20, -0.12,  0.00, 0.00, -0.45,  0.00,  0.00)),   # Nose - Bridge (Slender)
        (10063,  (0.00, -0.20,  0.05,  0.00,  0.00, 0.00, -0.30,  0.00,  0.00)),   # Nose - Ridge
        (100019, (0.00, -0.22,  0.28, -0.18,  0.00, 0.00, -0.32,  0.00,  0.00)),   # Nose - Tip (Slightly upturned)
        (100010, (-0.15, -0.20,  0.05,  0.00,  0.00, 0.00, -0.40,  0.00,  0.00)),  # Nostrils
        (100020, (0.00,  0.22, -0.10,  0.00,  0.00, 0.00,  0.18,  0.25,  0.25)),   # Mouth - Full
        (100022, (0.00,  0.18,  0.16,  0.00,  0.00, 0.00,  0.55,  0.00,  0.00)),   # Mouth - Top (Full upper lip)
        (100023, (0.00,  0.16, -0.08,  0.00,  0.00, 0.00,  0.52,  0.00,  0.00)),   # Mouth - Bottom (Full lower lip)
        (100021, (-0.12,  0.08,  0.25,  0.00,  0.00, 0.20,  0.00,  0.00,  0.00)),  # Mouth - Corners (Gentle smile)
        (100014, (0.00,  0.14,  0.25, -0.15,  0.00, 0.00, -0.42,  0.00,  0.00)),   # Chin (Small heart-shaped chin)
        (100011, (-0.48,  0.12, -0.15,  0.00,  0.00, 0.00, -0.45,  0.00,  0.00)),  # Jaw - Outer (Narrow delicate jaw)
        (100012, (-0.40, -0.20, -0.10,  0.00,  0.00, 0.00, -0.35,  0.00,  0.00)),  # Jaw - Middle
        (100025, (-0.25, -0.15,  0.15,  0.00,  0.00, 0.00, -0.25,  0.00,  0.00)),  # Face - Lower
        (100026, (-0.40, -0.25,  0.10,  0.00,  0.00, 0.00, -0.40,  0.00,  0.00)),  # Jowls - Upper
        (10062,  (-0.40, -0.25,  0.10,  0.00,  0.00, 0.00, -0.40,  0.00,  0.00)),  # Jowls - Lower
        (100005, (-0.20, -0.15, -0.25,  0.00, -0.15, 0.00, -0.20,  0.00,  0.00)),  # Ears - Full
        (100015, (-0.35,  0.00, -0.45,  0.00,  0.00, 0.00, -0.30,  0.00,  0.00)),  # Neck (Slender)
    ]
    for fmri_id, fmrs_vals in lucy_fmrs_regions:
        face_morph_subs.extend(pack_sub("FMRI", struct.pack("<I", fmri_id)))
        face_morph_subs.extend(pack_sub("FMRS", struct.pack("<9f", *fmrs_vals)))

    lucy_pnam_fids = [
        0x000F9E23,  # HairFemale06 ('On The Go' Ponytail)
        0x00186FC1,  # HairFemale06_Hairline
        0x0014EC28,  # FemaleEyesHumanBrown (Ella Purnell warm brown eyes)
        0x0004D0EC,  # FemaleEyesHumanLashes
        0x000F159E,  # FemaleEyesHumanAO
        0x0014EC22,  # FemaleEyesHumanWet
        0x0004D0E9,  # FemaleHeadHumanRearTEMP
        0x000CFB4E,  # FemaleMouthHumanoidDefault
        0x000CFB3F,  # FemaleHeadHuman
    ]
    lucy_inv_items = [
        (0x00004822, 1),    # 10mm Pistol
        (0x0001F276, 200),  # 10mm Rounds
        (0x00023736, 5),    # Stimpaks
        (0x01000860, 1),    # Lucy MacLean's Expedition Journal (Vault 33)
    ]

    lucy_subs = bytearray()
    lucy_subs.extend(pack_zstr("EDID", "NPC_LucyMacLean"))
    lucy_subs.extend(
        pack_sub("VMAD", build_simple_vmad("LucyActorScript", [("LucyQuest", 0x01000800)]))
    )

    sp_n = 0
    wrote_snam = False
    wrote_pkid = False
    wrote_cnto = False
    wrote_pnam = False
    wrote_face_morphs = False

    while sp_n + 6 <= len(tina_raw):
        st_n = tina_raw[sp_n : sp_n + 4].decode("ascii", "ignore")
        ss_n = struct.unpack_from("<H", tina_raw, sp_n + 4)[0]
        sv_n = bytearray(tina_raw[sp_n + 6 : sp_n + 6 + ss_n])

        if st_n in (
            "EDID",
            "VMAD",
            "CRIF",
            "TPLT",
            "TPTA",
            "FTST",
            "QNAM",
            "MSDK",
            "MSDV",
            "TETI",
            "TEND",
            "MRSV",
            "FMRI",
            "FMRS",
            "FMIN",
        ):
            if st_n == "QNAM" and not wrote_face_morphs:
                lucy_subs.extend(face_morph_subs)
                wrote_face_morphs = True
        elif st_n == "ACBS" and ss_n >= 4:
            fl_n = struct.unpack_from("<I", sv_n, 0)[0]
            # 0x00000026 = Essential (0x02) + Is CharGen Face Preset (0x04) + Unique (0x20)
            # Setting 0x04 (like MQ101PlayerSpouseFemale 0x000A7D35) forces Fallout 4 to run
            # runtime CharGen facial sculpting on this world NPC without needing a static FaceGeom NIF!
            fl_n |= 0x00000026
            fl_n &= ~0x00000808
            struct.pack_into("<I", sv_n, 0, fl_n)
            struct.pack_into("<H", sv_n, 6, 15)  # Level 15
            if ss_n >= 20:
                struct.pack_into("<H", sv_n, 18, 0)
            lucy_subs.extend(pack_sub("ACBS", bytes(sv_n)))
        elif st_n == "MWGT":
            # Slender athletic Vault-dweller build (Thin=0.68, Muscular=0.22, Fat=0.10)
            lucy_subs.extend(pack_sub("MWGT", struct.pack("<3f", 0.68, 0.22, 0.10)))
        elif st_n == "SNAM":
            if not wrote_snam:
                # PlayerFaction (0x0001C21C) so she fights alongside the player
                lucy_subs.extend(pack_sub("SNAM", struct.pack("<IB", 0x0001C21C, 0)))
                wrote_snam = True
        elif st_n == "AIDT" and ss_n >= 4:
            sv_n[0] = 1  # Aggressive (attacks enemies in combat)
            sv_n[1] = 3  # Brave
            sv_n[3] = 2  # Helps Friends and Allies
            lucy_subs.extend(pack_sub("AIDT", bytes(sv_n)))
        elif st_n == "PKID":
            if not wrote_pkid:
                # 1) Wait Here when GlobLucyWaitMode == 1.0
                # 2) Follow Player (defaultFollowPlayerPKG 0x00021E76) when GlobLucyWaitMode == 0.0
                lucy_subs.extend(pack_sub("PKID", struct.pack("<I", 0x01000830)))
                lucy_subs.extend(pack_sub("PKID", struct.pack("<I", 0x00021E76)))
                wrote_pkid = True
                if not wrote_cnto:
                    lucy_subs.extend(pack_sub("COCT", struct.pack("<I", len(lucy_inv_items))))
                    for i_fid, i_cnt in lucy_inv_items:
                        lucy_subs.extend(pack_sub("CNTO", struct.pack("<II", i_fid, i_cnt)))
                    wrote_cnto = True
        elif st_n in ("COCT", "CNTO"):
            if not wrote_cnto:
                lucy_subs.extend(pack_sub("COCT", struct.pack("<I", len(lucy_inv_items))))
                for i_fid, i_cnt in lucy_inv_items:
                    lucy_subs.extend(pack_sub("CNTO", struct.pack("<II", i_fid, i_cnt)))
                wrote_cnto = True
        elif st_n == "FULL":
            lucy_subs.extend(pack_zstr("FULL", "Lucy MacLean"))
            lucy_subs.extend(pack_zstr("SHRT", "Lucy"))
        elif st_n == "SHRT":
            pass
        elif st_n == "PNAM":
            if not wrote_pnam:
                for p_fid in lucy_pnam_fids:
                    lucy_subs.extend(pack_sub("PNAM", struct.pack("<I", p_fid)))
                wrote_pnam = True
        elif st_n == "HCLF":
            # HairColor18DeepBrown (0x0019EE65)
            lucy_subs.extend(pack_sub("HCLF", struct.pack("<I", 0x0019EE65)))
        elif st_n == "DOFT":
            # Outfit_LucyVault33 (0x01000815)
            lucy_subs.extend(pack_sub("DOFT", struct.pack("<I", 0x01000815)))
        else:
            lucy_subs.extend(tina_raw[sp_n : sp_n + 6 + ss_n])
        sp_n += 6 + ss_n

    comp_lucy = zlib.compress(bytes(lucy_subs))
    grup_npc = pack_grup_top(
        b"NPC_",
        pack_record(
            "NPC_",
            0x01000820,
            struct.pack("<I", len(lucy_subs)) + comp_lucy,
            flags=0x00040000,
        ),
    )

    # 8. OTFT: 0x01000815 (Outfit_LucyVault33: Vault 33 Jumpsuit + Vault Pip-Boy + Right Leather Bracer)
    grup_otft = pack_grup_top(
        b"OTFT",
        pack_record(
            "OTFT",
            0x01000815,
            pack_zstr("EDID", "Outfit_LucyVault33")
            + pack_sub(
                "INAM",
                struct.pack("<3I", 0x01000813, 0x001B9B87, 0x0007B9C3),
            ),
        ),
    )

    # 9. PACK: 0x01000830 (PackLucyWaitHere — active when GlobLucyWaitMode == 1.0)
    _, pk_fver, pk_v2, raw_pack = tpl["pack_stay_editor_loc"]
    pack_wait_subs = bytearray()
    pack_wait_subs.extend(pack_zstr("EDID", "PackLucyWaitHere"))
    sp_pk = 0
    while sp_pk + 6 <= len(raw_pack):
        st_pk = raw_pack[sp_pk : sp_pk + 4].decode("ascii", "ignore")
        ss_pk = struct.unpack_from("<H", raw_pack, sp_pk + 4)[0]
        if st_pk == "EDID":
            pass
        elif st_pk == "PSDT":
            pack_wait_subs.extend(raw_pack[sp_pk : sp_pk + 6 + ss_pk])
            # Add CTDA: GetGlobalValue(0x01000801 GlobLucyWaitMode) == 1.0
            pack_wait_subs.extend(pack_sub("CTDA", make_ctda_getglobalvalue(0x01000801, 1.0)))
        elif st_pk == "PLDT":
            # 0x0C = Current Location (stay right where ordered)
            pack_wait_subs.extend(pack_sub("PLDT", struct.pack("<4I", 0x0C, 0, 0, 0)))
        else:
            pack_wait_subs.extend(raw_pack[sp_pk : sp_pk + 6 + ss_pk])
        sp_pk += 6 + ss_pk

    grup_pack = pack_grup_top(
        b"PACK",
        pack_record("PACK", 0x01000830, bytes(pack_wait_subs), fver=pk_fver, v2=pk_v2),
    )

    # 9b. PERK: 0x01000880 (CompLucyGoldenRulePerk — "The Golden Rule (Vault 33)")
    _, perk_fver, perk_v2, perk_raw = tpl["perk_piper"]
    perk_subs = bytearray()
    perk_subs.extend(pack_zstr("EDID", "CompLucyGoldenRulePerk"))
    sp_prk = 0
    while sp_prk + 6 <= len(perk_raw):
        st_prk = perk_raw[sp_prk : sp_prk + 4].decode("ascii", "ignore")
        ss_prk = struct.unpack_from("<H", perk_raw, sp_prk + 4)[0]
        if st_prk == "EDID":
            pass
        elif st_prk == "FULL":
            perk_subs.extend(pack_zstr("FULL", "The Golden Rule (Vault 33)"))
        elif st_prk == "DESC":
            perk_subs.extend(
                pack_zstr(
                    "DESC",
                    "You have reached maximum affinity with Lucy MacLean. Gain double XP when succeeding at Speech persuasion checks and discovering new locations, plus +15% combat damage in self-defense.",
                )
            )
        else:
            perk_subs.extend(perk_raw[sp_prk : sp_prk + 6 + ss_prk])
        sp_prk += 6 + ss_prk
    # Add 3rd PRKE entry: +15% Weapon Attack Damage (0x23 Multiply Value 1.15)
    perk_subs.extend(pack_sub("PRKE", b"\x02\x00\x00"))
    perk_subs.extend(pack_sub("DATA", b"\x23\x03\x01"))
    perk_subs.extend(pack_sub("EPFT", b"\x01"))
    perk_subs.extend(pack_sub("EPFB", b"\x04\x00"))
    perk_subs.extend(pack_sub("EPFD", struct.pack("<f", 1.15)))
    perk_subs.extend(pack_sub("PRKF", b""))
    grup_perk = pack_grup_top(
        b"PERK",
        pack_record("PERK", 0x01000880, bytes(perk_subs), fver=perk_fver, v2=perk_v2),
    )

    # 9c. MESG: 0x01000870..0x01000874 (Vault 111 Recruitment Menu, Companion Menu & Affinity Status)
    def make_mesg_box(
        fid: int, edid: str, title: str, body: str, buttons: list[str]
    ) -> bytes:
        subs = bytearray()
        subs.extend(pack_zstr("EDID", edid))
        subs.extend(pack_zstr("DESC", body))
        subs.extend(pack_zstr("FULL", title))
        subs.extend(pack_sub("INAM", struct.pack("<I", 0)))
        subs.extend(pack_sub("DNAM", struct.pack("<I", 1)))
        for btn in buttons:
            subs.extend(pack_zstr("ITXT", btn))
        return pack_record("MESG", fid, bytes(subs), fver=131, v2=0)

    mesg_recruit = make_mesg_box(
        0x01000870,
        "MesgLucyRecruitMenu",
        "Lucy MacLean — Vault 33 Dweller",
        (
            "\"Okey-dokey! You finally stepped out of Vault 111! My name is Lucy MacLean, from Vault 33 in Santa Monica.\n\n"
            "On one of my dad Hank's Vault-Tec terminals in New Vegas, I picked up the depressurization signal from your "
            "cryogenic pod and crossed the whole country following my Pip-Boy to this overlook because I knew I'd find "
            "another real Vault Dweller here.\n\n"
            "Would you like us to travel together as companions across the Commonwealth and practice the Golden Rule?\""
        ),
        [
            "Yes, come with me as my companion (Okey-dokey, let's get to it!)",
            "Read her story from Vault 33 and New Vegas to Vault 111",
            "Not right now, wait for me here at the Vault 111 overlook",
        ],
    )

    mesg_companion = make_mesg_box(
        0x01000871,
        "MesgLucyCompanionMenu",
        "Lucy MacLean — Vault 33 Companion",
        (
            "\"Okey-dokey! What do you need, Vault 111 partner?\"\n\n"
            "• Current Affinity with Lucy: %.0f / 1000\n"
            "• Tip: Press F8 at any time to open the live voice & text chat window with Lucy."
        ),
        [
            "1. What do you think of this place? (AI)",
            "2. Tell me a story about Vault 33 or your journey",
            "3. Trade gear (Open inventory)",
            "4. Wait here / Follow me (Toggle order)",
            "5. Check Affinity & \"The Golden Rule\" Perk status",
            "6. Dismiss (Send to the Vault 111 overlook)",
            "7. Close",
        ],
    )

    mesg_story = make_mesg_box(
        0x01000872,
        "MesgLucyStoryIntro",
        "From Vault 33 (Santa Monica) to the Vault 111 Overlook",
        (
            "Lucy MacLean left Vault 33 in California to rescue her father, Hank MacLean. "
            "On the surface she survived Cooper Howard (The Ghoul)—who cut off her finger outside the Super Duper Mart—, "
            "traveled with Maximus, and discovered at Griffith Observatory that her own father was a pre-war Vault-Tec "
            "executive from Vault 31 who destroyed Shady Sands.\n\n"
            "After pursuing Hank to New Vegas, Lucy intercepted the opening signal of your cryogenic pod in Vault 111 "
            "on the Vault-Tec network. Determined to find someone who still believes in the Golden Rule, she traveled "
            "to this overlook to wait for you."
        ),
        [
            "Join forces as companions! (Okey-dokey, let's get to it!)",
            "Leave her waiting at the Vault 111 overlook for now",
        ],
    )

    mesg_affinity = make_mesg_box(
        0x01000873,
        "MesgLucyAffinityStatus",
        "Companion Affinity & Perk — Lucy MacLean",
        (
            "• Current Affinity with Lucy MacLean: %.0f / 1000\n\n"
            "• Likes / Loves (+Affinity):\n"
            "  Completing quests to help the Commonwealth (+45), hacking terminals (+20), "
            "picking locks (+15), improving weapons/armor (+15), and building settlement objects (+15).\n\n"
            "• Dislikes / Hates (-Affinity):\n"
            "  Murdering innocents (-80), pickpocketing (-25), trespassing (-20), and chem addiction (-30).\n\n"
            "• Max Affinity Perk (1000 / 1000) — \"The Golden Rule (Vault 33)\":\n"
            "  Double XP on Speech checks and discovering locations, plus +15%% combat damage in self-defense."
        ),
        ["Back"],
    )

    mesg_perk_unlocked = make_mesg_box(
        0x01000874,
        "MesgLucyPerkUnlocked",
        "Maximum Affinity with Lucy MacLean!",
        (
            "\"Okey-dokey! After everything I went through with my dad Hank and Cooper Howard, you proved to me "
            "that the Golden Rule is still alive on the surface. You can count on me forever, partner!\"\n\n"
            "You have gained the permanent perk \"The Golden Rule (Vault 33)\":\n"
            "• Double XP for succeeding at Speech persuasion checks.\n"
            "• Double XP when discovering new locations across the Commonwealth.\n"
            "• +15%% combat damage when defending yourself and your companions."
        ),
        ["Okey-dokey, let's get to it!"],
    )

    grup_mesg = pack_grup_top(
        b"MESG",
        mesg_recruit + mesg_companion + mesg_story + mesg_affinity + mesg_perk_unlocked,
    )

    # 10. QUST: 0x01000800 (LucyCompanionQuest — Start Game Enabled)
    q_vmad = build_simple_vmad(
        "LucyCompanionSensorScript",
        [
            ("LucyRef", 0x01000821),
            ("Vault111ExitMarkerRef", 0x0005632D),
            ("GlobWaitMode", 0x01000801),
            ("GlobRecruited", 0x01000802),
            ("GlobAffinity", 0x01000803),
            ("CmdAskItem", 0x01000840),
            ("CmdFollowWaitItem", 0x01000841),
            ("CmdLoreItem", 0x01000842),
            ("CmdSummonItem", 0x01000843),
            ("Vault33SuitItem", 0x01000813),
            ("LucyJournalItem", 0x01000860),
            ("MesgRecruitMenu", 0x01000870),
            ("MesgCompanionMenu", 0x01000871),
            ("MesgStoryIntro", 0x01000872),
            ("MesgAffinityStatus", 0x01000873),
            ("MesgPerkUnlocked", 0x01000874),
            ("CompLucyPerk", 0x01000880),
        ],
    )
    q_subs = (
        pack_zstr("EDID", "LucyCompanionQuest")
        + pack_sub("VMAD", q_vmad)
        + pack_zstr("FULL", "Lucy MacLean — Vault 33 Companion")
        + pack_sub("DNAM", bytes.fromhex("110150000000000007000000"))
    )
    grup_qust = pack_grup_top(
        b"QUST",
        pack_record("QUST", 0x01000800, q_subs),
    )

    # 11. WRLD: 0x0000003C (Commonwealth) -> Persistent Cell 0x00018AA2 -> ACHR 0x01000821 (LucyMacLeanRef)
    wpay = tpl["wrld_3c_pay"]
    wrld_3c_subs = bytearray()
    sp = 0
    next_sz32 = None
    while sp + 6 <= len(wpay):
        st = wpay[sp : sp + 4].decode("ascii", "ignore")
        ss = struct.unpack_from("<H", wpay, sp + 4)[0]
        if next_sz32 is not None:
            ss = next_sz32
            next_sz32 = None
        if st == "XXXX":
            next_sz32 = struct.unpack_from("<I", wpay, sp + 6)[0]
            sp += 6 + ss
            continue
        if st == "FULL":
            wrld_3c_subs.extend(pack_zstr("FULL", "Commonwealth"))
        elif st not in ("RNAM", "MHDT", "OFST", "CLSZ"):
            wrld_3c_subs.extend(wpay[sp : sp + 6 + ss])
        sp += 6 + ss
    wrld_3c_rec = pack_record("WRLD", 0x0000003C, bytes(wrld_3c_subs))

    # Persistent ACHR 0x01000821 (LucyMacLeanRef) placed right by the Vault 111 Surface Control Stand (~12.5m off the elevator platform)!
    lucy_achr_subs = (
        pack_zstr("EDID", "LucyMacLeanRef")
        + pack_sub("NAME", struct.pack("<I", 0x01000820))
        + pack_sub("DATA", struct.pack("<6f", -88200.0, 91217.0, 9003.0, 0.0, 0.0, 3.78))
    )
    ext_refs = pack_record("ACHR", 0x01000821, lucy_achr_subs, flags=0x00000400)

    w_g8 = b"GRUP" + struct.pack("<IIIII", 24 + len(ext_refs), 0x00018AA2, 8, 0, 0) + ext_refs
    w_g6 = b"GRUP" + struct.pack("<IIIII", 24 + len(w_g8), 0x00018AA2, 6, 0, 0) + w_g8
    w_g1_body = tpl["cell_18aa2_raw"] + w_g6
    w_g1 = b"GRUP" + struct.pack("<IIIII", 24 + len(w_g1_body), 0x0000003C, 1, 0, 0) + w_g1_body
    grup_wrld = pack_grup_top(b"WRLD", wrld_3c_rec + w_g1)

    all_grups = (
        grup_glob
        + grup_mgef
        + grup_mswp
        + grup_arma
        + grup_armo
        + grup_book
        + grup_alch
        + grup_npc
        + grup_otft
        + grup_pack
        + grup_perk
        + grup_mesg
        + grup_qust
        + grup_wrld
    )

    def count_esp_items(buf: bytes, s: int, e: int) -> int:
        cnt = 0
        q = s
        while q < e:
            rt_b = buf[q : q + 4]
            sz_b = struct.unpack_from("<I", buf, q + 4)[0]
            cnt += 1
            if rt_b == b"GRUP":
                cnt += count_esp_items(buf, q + 24, q + sz_b)
                q += sz_b
            else:
                q += 24 + sz_b
        return cnt

    total_items = count_esp_items(all_grups, 0, len(all_grups))
    tes4_subs = (
        pack_sub("HEDR", struct.pack("<fII", 1.0, total_items, 0x00000900))
        + pack_zstr("CNAM", "OutKast & Antigravity")
        + pack_zstr(
            "SNAM",
            "Lucy MacLean (Vault 33) — 100% Local Generative AI Companion for Fallout 4 (Ollama + Kokoro-ONNX Voice + Custom Vault 33 Jumpsuit). Inspired by Bagomojo/rdr2-companion (MIT).",
        )
        + pack_zstr("MAST", "Fallout4.esm")
        + pack_sub("DATA", struct.pack("<Q", 0))
    )
    tes4_rec = pack_record("TES4", 0, tes4_subs)

    os.makedirs(os.path.dirname(dst_esp), exist_ok=True)
    with open(dst_esp, "wb") as wf:
        wf.write(tes4_rec + all_grups)

    print(
        f"[ESP] {ESP_NAME} built successfully: {dst_esp} ({len(tes4_rec) + len(all_grups)} bytes, {total_items} records/groups)"
    )


def enable_plugin_in_appdata() -> None:
    local_app = os.environ.get("LOCALAPPDATA", "")
    if not local_app:
        return
    plugins_txt = os.path.join(local_app, "Fallout4", "plugins.txt")
    if not os.path.exists(plugins_txt):
        return
    with open(plugins_txt, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    entry = f"*{ESP_NAME}"
    if not any(ln.lstrip("*").lower() == ESP_NAME.lower() for ln in lines):
        lines.append(entry)
    else:
        lines = [entry if ln.lstrip("*").lower() == ESP_NAME.lower() else ln for ln in lines]
    with open(plugins_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  [Enabled in plugins.txt] {entry}")


def main() -> None:
    os.makedirs(BUILD_OUT_DIR, exist_ok=True)
    compile_papyrus_scripts()

    ba2_files = build_vault33_materials()
    for fn in sorted(os.listdir(PAPYRUS_OUT_DIR)):
        if fn.endswith(".pex"):
            src_pex = os.path.join(PAPYRUS_OUT_DIR, fn)
            ba2_key = f"scripts\\{fn.lower()}"
            ba2_files[ba2_key] = src_pex
            print(f"  [Script] Packaged: {fn}")

    tpl = extract_esm_templates()
    staged_esp = os.path.join(BUILD_OUT_DIR, ESP_NAME)
    staged_ba2 = os.path.join(BUILD_OUT_DIR, BA2_NAME)
    staged_tex_ba2 = os.path.join(BUILD_OUT_DIR, TEX_BA2_NAME)

    build_esp_file(tpl, staged_esp)
    build_ba2_archive(staged_ba2, ba2_files)
    build_vault33_textures_ba2(staged_tex_ba2)

    if INSTALL_TO_FO4_DATA:
        for src_f, dst_name in [
            (staged_esp, ESP_NAME),
            (staged_ba2, BA2_NAME),
            (staged_tex_ba2, TEX_BA2_NAME),
        ]:
            if not os.path.exists(src_f):
                continue
            dst_f = os.path.join(FO4_DATA_DIR, dst_name)
            try:
                shutil.copyfile(src_f, dst_f)
                print(f"  [Installed to Fallout 4\\Data] {dst_name}")
            except PermissionError:
                print(f"  [Notice] {dst_name} is currently in use by Fallout 4.")
        enable_plugin_in_appdata()

    print("\n'Lucy MacLean — Vault 33 Generative AI Companion' built successfully in lucy_companion_fo4/build_out/!")


if __name__ == "__main__":
    main()
