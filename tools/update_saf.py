"""Re-target the Nexus SuperAxiomForce.asi to a new Crimson Desert build.

The .asi is not rebuilt. It hardcodes game addresses for one exe build; this
script finds where each of those addresses moved in a memory dump of the new
build and rewrites the numbers. See docs/UPDATING.md.

Usage:
  py update_saf.py --asi current.asi --state state.json --dump game.bin \
                   --version 1.0.0.XXXX --out new.asi --state-out new_state.json

--state describes what --asi currently expects (tools/state/ has one per build).
Every value is checked before it is written; any mismatch stops the script
without writing anything.
"""
import argparse
import json
import re
import struct
import sys

import capstone
import numpy as np
import pefile

H = lambda v: f"0x{v:x}"  # noqa: E731
X = lambda s: int(s, 16)  # noqa: E731
MAX_RESIDUAL = 0x1000  # how far a site may drift from its neighbours' shift


def fail(msg):
    sys.exit(f"\nSTOPPED: {msg}\nNothing was written. See docs/UPDATING.md, 'If the script stops'.")


class Asi:
    def __init__(self, path):
        pe = pefile.PE(path)
        self.buf = bytearray(open(path, "rb").read())
        text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
        self.t0, self.t1 = text.PointerToRawData, text.PointerToRawData + text.SizeOfRawData
        self.sections = [(s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData) for s in pe.sections]
        pe.close()

    def off(self, rva):
        for va, vs, raw in self.sections:
            if va <= rva < va + vs:
                return rva - va + raw
        raise ValueError(H(rva))

    def read(self, rva, n):
        o = self.off(rva)
        return bytes(self.buf[o:o + n])

    def write(self, rva, data):
        o = self.off(rva)
        self.buf[o:o + len(data)] = data

    def text_hits(self, value):
        pat = re.escape(struct.pack("<I", value & 0xFFFFFFFF))
        return [self.t0 + m.start() for m in re.finditer(pat, bytes(self.buf[self.t0:self.t1]))]

    def text_count(self, value):
        """Occurrences of an RVA in code, either as +value or -value."""
        return len(self.text_hits(value)) + len(self.text_hits(-value))

    def shift_text_constant(self, old, new, expected):
        pos, neg = self.text_hits(old), self.text_hits(-old)
        if len(pos) + len(neg) != expected:
            fail(f"code constant {H(old)} found {len(pos) + len(neg)} times, state says {expected}")
        for o in pos:
            self.buf[o:o + 4] = struct.pack("<I", new & 0xFFFFFFFF)
        for o in neg:
            self.buf[o:o + 4] = struct.pack("<I", -new & 0xFFFFFFFF)

    def layout(self):
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        return [(i.address, i.size) for i in md.disasm(bytes(self.buf[self.t0:self.t1]), 0)]


def find_all(hay, needle):
    return [m.start() for m in re.finditer(re.escape(needle), hay)]


def rip_target(game, at):
    return at + 4 + struct.unpack_from("<i", game, at)[0]


def find_range_data(game, old_entries, old_range):
    """Locate the new Range float by the shape of the code that references it.

    Range (R), AxiomLimitRange (R-0x50) and PullSpeed (R+0xB40) are read by
    RIP-relative instructions. Several limit/range reads come as a pair 7 bytes
    apart. A candidate R wins when every old reference has a counterpart close to
    where the nearby pairs moved.
    """
    print("  indexing RIP-relative references (takes a minute)...")
    g = np.frombuffer(game, dtype=np.uint8)
    p = np.nonzero((g[:-4] & 0xC7) == 0x05)[0] + 1  # byte after a RIP modrm
    disp = (g[p].astype(np.int64) | (g[p + 1].astype(np.int64) << 8)
            | (g[p + 2].astype(np.int64) << 16) | (g[p + 3].astype(np.int64) << 24))
    disp = np.where(disp >= 2**31, disp - 2**32, disp)
    t = p + 4 + disp
    keep = (t >= 0x100000) & (t < len(game))
    p, t = p[keep], t[keep]
    order = np.argsort(t, kind="stable")
    p, t = p[order], t[order]

    def refs(T):
        i, j = np.searchsorted(t, T), np.searchsorted(t, T, side="right")
        return p[i:j]

    role_off = {"limit": -0x50, "range": 0, "pull": 0xB40}
    old_pairs = [(e["rva"], e["rva"] + 7) for e in old_entries if e["role"] == "limit"
                 and any(f["role"] == "range" and f["rva"] == e["rva"] + 7 for f in old_entries)]

    uniq = np.unique(t)
    present = set(uniq.tolist())
    best = None
    for R in uniq:
        R = int(R)
        if (R - 0x50) not in present or (R + 0xB40) not in present:
            continue
        lim, rng = refs(R - 0x50), refs(R)
        rng_set = set(rng.tolist())
        new_pairs = [int(a) for a in lim if int(a) + 7 in rng_set]
        if len(new_pairs) < len(old_pairs):
            continue
        pair_delta = {}
        for (ol, _) in old_pairs:
            nl = min(new_pairs, key=lambda x: abs(x - ol))
            pair_delta[ol] = nl - ol
        mapping, worst = {}, 0
        for e in old_entries:
            anchor = min(pair_delta, key=lambda a: abs(a - e["rva"]))
            want = e["rva"] + pair_delta[anchor]
            cands = refs(R + role_off[e["role"]])
            got = int(cands[np.argmin(np.abs(cands - want))])
            worst = max(worst, abs(got - want))
            mapping[e["rva"]] = got
        if best is None or worst < best[0]:
            best = (worst, R, mapping, pair_delta)
    if best is None or best[0] > MAX_RESIDUAL:
        fail("could not identify the Range/Limit/PullSpeed data in the new build")
    worst, R, mapping, pair_delta = best
    print(f"  Range data {H(old_range)} -> {H(R)} (worst drift {H(worst)})")
    return R, mapping, pair_delta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("--asi", "--state", "--dump", "--version", "--out", "--state-out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--game-version", default="", help="in-game version label, e.g. 2.05.00")
    args = ap.parse_args()

    st = json.load(open(args.state))
    asi = Asi(args.asi)
    game = open(args.dump, "rb").read()
    layout_before = asi.layout()

    # ---- 1. version gate -------------------------------------------------
    pe = struct.unpack_from("<I", game, 0x3C)[0]
    new_gate = {"timestamp": struct.unpack_from("<I", game, pe + 0x08)[0],
                "size_of_image": struct.unpack_from("<I", game, pe + 0x50)[0],
                "checksum": struct.unpack_from("<I", game, pe + 0x58)[0]}
    print("Version gate:")
    for k, new in new_gate.items():
        old = X(st["gate"][k])
        print(f"  {k}: {H(old)} -> {H(new)}")
        if len(asi.text_hits(old)) != 1:
            fail(f"gate value {k}={H(old)} not found exactly once in the .asi (wrong --state?)")
        if old == new:
            print("  (same build as the state file, nothing to do?)")
        asi.shift_text_constant(old, new, 1)

    # ---- 2. Axiom code block: one shared shift -------------------------
    print("Axiom code block:")
    deltas = None
    for b in st["block"]["anchors"]:
        blob = asi.read(X(b["asi_rva"]), b["len"])
        hits = {h - X(b["rva"]) for h in find_all(game, blob)}
        deltas = hits if deltas is None else deltas & hits
        print(f"  {b['name']}: {len(hits)} match(es)")
    if not deltas or len(deltas) != 1:
        fail(f"Axiom block anchors do not agree on one shift (candidates: {sorted(map(H, deltas or []))})")
    D = deltas.pop()
    print(f"  shift = {'+' if D >= 0 else '-'}{H(abs(D))}")

    anchor0 = X(st["block"]["call_target"]) + D
    for cs in st["block"]["call_sites"]:
        n = X(cs) + D
        if game[n - 5] != 0xE8 or rip_target(game, n - 4) != anchor0:
            fail(f"call site {cs} is no longer a CALL to the Axiom helper after the shift")

    ce = st["block"]["call_site_bytes"]
    q_rva, w_rva, site = X(ce["qword_asi_rva"]), X(ce["word_asi_rva"]), X(ce["rva"]) + D
    old_bytes = asi.read(q_rva, 8) + asi.read(w_rva, 2)
    new_bytes = game[site:site + 10]
    if new_bytes[:6] != old_bytes[:6]:
        fail(f"instruction at {ce['rva']} changed shape: {old_bytes.hex(' ')} vs {new_bytes.hex(' ')}")
    asi.write(q_rva, new_bytes[:8])
    asi.write(w_rva, new_bytes[8:])

    for c, count in st["block"]["constants"].items():
        asi.shift_text_constant(X(c), X(c) + D, count)
    print(f"  {len(st['block']['constants'])} code constants shifted")

    lo, hi = min(map(X, st["block"]["constants"])), max(map(X, st["block"]["constants"]))
    in_block = lambda r: lo <= r <= hi  # noqa: E731

    # ---- 3. native contract table --------------------------------------
    print("Native contract table:")
    tbl = X(st["table"]["asi_rva"])
    entries = []
    for i in range(st["table"]["count"]):
        e = tbl + 28 * i
        rva, ln, idx = struct.unpack("<III", asi.read(e, 12))
        entries.append({"at": e, "rva": rva, "len": ln, "bytes": asi.read(e + 12, ln)})

    old_range = X(st["data"]["range"])
    role_of = {old_range - 0x50: "limit", old_range: "range", old_range + 0xB40: "pull"}
    data_entries = []
    for e in entries:
        if e["len"] == 4 and not in_block(e["rva"]):
            target = e["rva"] + 4 + struct.unpack("<i", e["bytes"])[0]
            if target not in role_of:
                fail(f"table entry {H(e['rva'])} points at {H(target)}, not Range/Limit/Pull")
            e["role"] = role_of[target]
            data_entries.append(e)

    R, ref_map, pair_delta = find_range_data(game, data_entries, old_range)

    for e in entries:
        if in_block(e["rva"]):
            new = e["rva"] + D
            nb = game[new:new + e["len"]]
            if nb != e["bytes"]:
                fail(f"block site {H(e['rva'])} bytes changed")
        elif "role" in e:
            new = ref_map[e["rva"]]
            nb = game[new:new + 4]
        else:
            anchor = min(pair_delta, key=lambda a: abs(a - e["rva"]))
            want = e["rva"] + pair_delta[anchor]
            hits = find_all(game, e["bytes"])
            if not hits:
                fail(f"code site {H(e['rva'])} ({e['bytes'].hex(' ')}) not found")
            new = min(hits, key=lambda h: abs(h - want))
            if abs(new - want) > MAX_RESIDUAL:
                fail(f"code site {H(e['rva'])} only found far from where it should be")
            nb = e["bytes"]
        asi.write(e["at"], struct.pack("<I", new))
        asi.write(e["at"] + 12, nb)
        print(f"  {H(e['rva'])} -> {H(new)}  {e.get('role', 'code')}")

    # ---- 4. startup contract: check the second maneuver CALL twice ------
    # Another mod (ImprovedAxiomManeuver) NOPs the first maneuver CALL. The
    # contract loop would then reject the whole native layer, so its first
    # entry is pointed at the second CALL, which is always intact.
    rc = st["relaxed_contract"]
    imm = X(rc["asi_rva"]) + 6
    first_site = st["block"]["call_sites"][0]
    asi.write(imm, struct.pack("<I", X(first_site) + D))

    # ---- 5. build tag ----------------------------------------------------
    old_tag = st["build_tag"].encode()
    new_tag = (args.version + st["build_tag"][st["build_tag"].index("-"):]).encode()
    if len(new_tag) != len(old_tag):
        fail(f"--version must have the same length as {st['build_tag'].split('-')[0]}")
    i = asi.buf.find(old_tag)
    if i < 0:
        fail("build tag not found")
    asi.buf[i:i + len(old_tag)] = new_tag

    # ---- 6. sanity and output -------------------------------------------
    if asi.layout() != layout_before:
        fail("instruction layout changed (a replaced number was not a real constant)")

    new_state = json.loads(json.dumps(st))
    new_state["game_version"] = args.game_version or "unknown"
    new_state["game_exe_version"] = args.version
    new_state["build_tag"] = new_tag.decode()
    new_state["gate"] = {k: H(v) for k, v in new_gate.items()}
    for b in new_state["block"]["anchors"]:
        b["rva"] = H(X(b["rva"]) + D)
    blk = new_state["block"]
    blk["call_target"] = H(X(blk["call_target"]) + D)
    blk["call_sites"] = [H(X(c) + D) for c in blk["call_sites"]]
    blk["call_site_bytes"]["rva"] = H(X(blk["call_site_bytes"]["rva"]) + D)
    blk["constants"] = {H(X(c) + D): asi.text_count(X(c) + D) for c in st["block"]["constants"]}
    new_state["data"]["range"] = H(R)

    open(args.out, "wb").write(asi.buf)
    json.dump(new_state, open(args.state_out, "w"), indent=2)
    print(f"\nWrote {args.out}\nWrote {args.state_out}")


if __name__ == "__main__":
    main()
