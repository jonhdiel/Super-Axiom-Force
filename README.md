# Super Axiom Force — Crimson Desert 2.05.00

ALL CREDITS TO THE ORIGINAL AUTHORS LINKED BELOW. THIS HAS BEEN PUT HERE ONLY BECAUSE I WANT TO PLAY IT, AND IT WAS TAKING SOME TIME BEFORE IT WAS UPDATED. AN PATCHER AND OTHER THINGS WERE CREATED TROUGH AI SO IN THE FUTURE IF IT EVER BREAKS OR IS ABANDONED, IT CAN BE REPLICATED FROM WHATS HAPENNING HERE, I WONT BE UPDATING IT, IF NEEDED YOU CAN PUT THIS INTO AN AI AND IT WILL DO IT FOR YOU BASED ON WHATS WRITTEN IN DOCS. AGAIN, ALL CREDITS GOES TO THE ORIGINAL AUTHORS AND MAINTAINERS FROM THE MOD.

The Nexus build of [Super Axiom Force](https://www.nexusmods.com/crimsondesert/mods/2852), patched to run on Crimson Desert **2.05.00** (exe `1.0.0.3663`).

The mod extends Axiom Force range and pull speed, and adds StraightPull and InstantAxiom.

## Install

1. Put [release/SuperAxiomForce.asi](release/SuperAxiomForce.asi) and [release/SuperAxiomForce.ini](release/SuperAxiomForce.ini) into DMM (Definitive Mod Manager) and deploy.
2. Check that both files are in `Crimson Desert\bin64`. If the `.ini` is missing, the mod uses its built-in defaults (500 / 1000 / on / on), and the log shows `exists=false`.
3. Start the game, load a save and wait about 20 seconds. `bin64\SuperAxiomForce.log` should end with `Apply summary: Enabled=true result=complete`.

## Game updated and the mod stopped working?

That's expected: this build only runs on one exact game version. On any other version it does nothing and writes **no log at all**. Follow [docs/UPDATING.md](docs/UPDATING.md). The process is mostly automated.

## Layout

| Path | What it is |
|---|---|
| `release/` | The current working `.asi` and `.ini` |
| `tools/dump_game.py` | Captures the running game's decrypted code to a file |
| `tools/update_saf.py` | Re-targets the `.asi` to a new game build using that file |
| `tools/state/` | What each patched build expects, one file per game version |
| `docs/UPDATING.md` | Step-by-step update guide and technical notes |
| `archive/nexus-2.04.08/` | The original, unmodified Nexus `.asi` (game 2.04.08) |
| `archive/legacy-source-1.0.0.1855/` | Old open-source version for game 1.0.0.1855. Reference only; the Nexus build is a different, newer program |

See [CHANGELOG.md](CHANGELOG.md) for history.
