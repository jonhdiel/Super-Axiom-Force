# Changelog

## 2.05.01 (game exe 1.0.0.3732) — 2026-11-19

- Re-targeted to 2.05.01 with `tools/update_saf.py`. It ran without stopping, so no manual work was needed. The log reports the build as `1.0.0.3732-native-r22-owned-contract`.
- The Axiom code block moved by `+0x1B80`. Range/Limit/PullSpeed and InstantAxiom sites moved by about `+0x370`. Range data moved from `0x716B7E8` to `0x7171898`.
- Verified in-game.

## 2.05.00 (game exe 1.0.0.3663) — 2026-11-15

- Patched the Nexus build (`1.0.0.3576-native-r22-owned-contract`) to run on 2.05.00. The log now reports the build as `1.0.0.3663-native-r22-owned-contract`.
- Version check updated to the 2.05.00 exe header.
- The Axiom code block moved by `+0x3E690`. Range/Limit/PullSpeed and InstantAxiom sites moved by about `+0x2BA30`. Range data moved from `0x70E73E8` to `0x716B7E8`.
- Startup check now verifies the second maneuver CALL twice, so a NOP from ImprovedAxiomManeuver no longer disables the mod.
- Verified in-game: all features apply (`result=complete`) alongside ImprovedAxiomManeuver.
- Added `tools/` (memory dump + automatic updater) and `docs/UPDATING.md`.

## 2.04.08 (game exe 1.0.0.3576)

- Original Nexus release. Kept in `archive/nexus-2.04.08/`.
