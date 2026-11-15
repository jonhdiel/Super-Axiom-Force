# Updating Super Axiom Force after a game update

Follow this guide when Crimson Desert updates and the mod stops working.

**What you'll see:** no `SuperAxiomForce.log` in `bin64` at all. This build checks the game exe on startup and quietly does nothing if the version isn't the one it was patched for.

**Why it needs updating:** the mod uses fixed locations in the game's code. A game update moves that code around, so the locations have to be found again and written into the `.asi`. Nothing is recompiled. The scripts in `tools/` do the finding and patching.

---

## Quick procedure (about 10 minutes)

### 1. One-time setup

Install Python 3 (the `py` launcher), then:

```
py -m pip install --user -r tools/requirements.txt
```

### 2. Capture the new game build

1. Update the game. Start it, load your save, and **use Axiom Force once** so its code is loaded.
2. With the game still running, open a terminal in `tools/` and run:

   ```
   py dump_game.py C:\temp\game_NEW.bin
   ```

   This writes a file of a few hundred MB containing the game's decrypted code. The `.exe` on disk is encrypted, so this file is what we search instead. Don't commit it (`.gitignore` excludes `*.bin`).
3. Note the exe version: right-click `bin64\CrimsonDesert.exe` → Properties → Details → File version (for example `1.0.0.3663`). You can close the game now.

### 3. Run the updater

From `tools/`, using the newest file in `tools/state/` as the starting point:

```
py update_saf.py --asi ..\release\SuperAxiomForce.asi --state state\2.05.00.json ^
    --dump C:\temp\game_NEW.bin --version 1.0.0.XXXX --game-version 2.0X.XX ^
    --out ..\release\SuperAxiomForce.new.asi --state-out state\2.0X.XX.json
```

- `--version` is the exe file version from step 2. It must have the same length as the current one (four-digit build number).
- `--game-version` is the version shown in-game. It's only used as a label.

The script prints each value it moves (old → new). It stops without writing anything if something doesn't match. See "If the script stops" below.

### 4. Install and test

1. Replace `release/SuperAxiomForce.asi` with the new file.
2. Deploy through DMM, start the game, load in, and wait about 20 seconds.
3. `bin64\SuperAxiomForce.log` should:
   - start with `Starting up build=1.0.0.XXXX-native-r22-owned-contract`
   - contain `Discovery summary: Range=scoped-ready Limit=scoped-ready PullSpeed=scoped-ready StraightPull=scoped-ready InstantAxiom=ready`
   - end with `Apply summary: Enabled=true result=complete`
4. Try it in-game, then add an entry to `CHANGELOG.md` and commit the new `.asi` and state file.

---

## If the script stops

Each message points to a specific part of the mod that changed in the update.

| Message | Meaning | What to do |
|---|---|---|
| `gate value ... not found` | `--state` doesn't describe `--asi` | Use the state file that matches the `.asi` you passed |
| `Axiom block anchors do not agree` | The Axiom code itself was changed (not just moved) | Manual work, see below |
| `call site ... no longer a CALL` | The maneuver loop changed | Manual |
| `instruction at ... changed shape` | The call at the InstantAxiom hook changed | Manual |
| `could not identify the Range/Limit/PullSpeed data` | The range-reading code was reorganised | Manual |
| `code site ... not found` | An InstantAxiom branch changed | Manual |
| `instruction layout changed` | A replaced number wasn't a real constant | Bug in the script; investigate |

The easiest case is a small update (a hotfix) that only moves code around. The script handles that fully. If the update rewrote the Axiom code itself, the Nexus author's own update may be the better route. Check the Nexus page first.

### Manual work

Open a Claude Code session in this repo, attach this guide, and paste the failing output. All the information needed is in "How it works" below, and the dump file contains everything to search. The 2.05.00 update was done that way from scratch. `update_saf.py` is that work automated.

---

## How it works (technical reference)

All addresses below are RVAs, i.e. offsets from the game's image base `0x140000000`. "asi RVA" means a location inside `SuperAxiomForce.asi`.

### Startup and the version check

- `DllMain` (asi `0x15260`) calls a host check (asi `0xD7E0`). That check confirms the process is `CrimsonDesert.exe`, then calls asi `0x17B0`.
- asi `0x17B0` reads the game's PE header and requires exact values: TimeDateStamp, SizeOfImage and CheckSum, plus machine, magic, image base and DllCharacteristics. If any differ, it returns false and the mod exits **before creating the log**.
- The updater reads the new values from the dump's header (`gate` in the state file).

### Hardcoded game locations

**1. Axiom code block**

About 18 KB of game code, moved as one piece (2.04.08 → 2.05.00: `+0x3E690`). The mod uses it in three ways:
- as code immediates, some stored negated (`state.block.constants`, with how many times each appears in the `.asi`)
- through four byte copies stored in the `.asi`'s `.rdata`, which the mod compares against the game (`state.block.anchors`)
- through a 10-byte copy, `lea rcx,[rsp+40h]` followed by a CALL, at `call_site_bytes`. The CALL's displacement changes when its target moves, so the updater copies the new bytes from the dump.

**2. Native contract table**

Lives at asi `0x3E080`: 11 entries of 28 bytes each, laid out as `{u32 rva, u32 len, u32 group, u8 bytes[16]}`.
- 4-byte entries are RIP-relative reads of the **Limit** (Range − 0x50), **Range** and **PullSpeed** (Range + 0xB40) floats. Their stored bytes are the instruction's displacement, which changes when either the code or the data moves.
- The other entries are InstantAxiom code sites, matched byte-for-byte.
- The updater finds the new Range float by looking for a data address with references to all three floats. Two limit/range reads sit 7 bytes apart (a signature that survives updates). It then matches each old entry to the nearest corresponding new reference.

**3. StraightPull calls**

Three CALLs to the Axiom helper (`call_target`) inside the maneuver loop. ImprovedAxiomManeuver NOPs the first one. The mod's startup check (asi `0xD4D4`, a list of three addresses) would then reject everything. So the patch replaces the first entry of that list with the second CALL (`relaxed_contract`). The mod itself copes with the NOPed call: its log shows `can_restore=false` for it.

### Useful commands

Disassembling the `.asi` (with pefile + capstone) is how all of the above was found. The useful starting points:
- calls to `memcmp` (asi `0x3ABF0`) show what the mod verifies
- immediates in the code block's range show the hardcoded addresses
- the `Discovery summary` log string leads to the discovery code
