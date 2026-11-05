# FOG OF WAR: notes for agents

A WWII roguelike on python-tcod. About 83,000 lines of Python in `fow/`, so read the module, not the package.

- **Where things are:** the module map at the end of `docs/ARCHITECTURE.md` (one line per module). Content is
  data in `fow/data/` (items, vehicles, nations, theatres); item pictures are painters in `fow/icons.py`.
- **Biggest files** (read them in ranges, and grep first): `play.py` (in-battle input and UI), `game.py` (turn
  loop, sound, saves), `ui.py` (app shell, menus), `ai.py` (squad, soldier and vehicle AI), `mapgen.py`.
- **Headless:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, and always `FOW_HOME=<scratch dir>` so a run
  never touches the real save in `~/.fogofwar`. `docs/DEVELOPMENT.md` has a runnable snippet and `FakeApp`.
- **Tests:** `.venv/bin/python -m pytest -q tests` (parallel by default, about 30 seconds; `-n0` for serial
  debugging, `--deselect tests/test_smoke.py::test_every_theatre_starts_and_runs` skips the slowest one).
  After interface or AI changes also run `tools/fuzz.py bocage44,kursk43 1 300`.
- **New content:** drills live in `doctrine.py` (nation/rank/skill gated, mods read by `ai.py`); camps in `camp.py`;
  politics in `politics.py`; quotes in `quotes.py`; autopilot trades and survival in `jobs.py` (the player only,
  called from `ai.soldier_act`), sleep and rest in `sleep.py` (NPC sleep is hooked in `garrison.py`), and vehicle
  repair seeking in `maintenance._seek_repair`; trade duties in `trade.py`, section memory in `bonds.py`, the
  enemy commander in `opponent.py`, the rear in `rear_cycle.py`, and the diary in `diary.py`; command reception
  in `friction.py`, reputation in `renown.py`, the lull in `consolidate.py`, the manual in `manual.py`, fronts in
  `weather_director.py`, packs in `packs.py`. Storeys are separate plans in `floors.py` (`soldier_at` is the
  ground store only; `soldier_at_z` and `actor_at/set_actor_at/pop_actor_at` carry upper floors). Difficulty is
  `difficulty.py`; run slots are `runs.py`/`runcode.py`; the after-action record is `reportcard.py`; the first
  hour is `enlist.py`. Saves are versioned (`Game._migrate_save`, `.bak` fallback): bump
  `SAVE_VERSION` when adding a field an old save needs. Re-run
  `tools/longplay.py 2000` after AI or simulation changes.
- **Speed:** `tools/benchmark_world.py --save ~/.fogofwar/save.pkl --turns 150 [--profile out.prof]` copies a
  save and times real world turns; `FOW_CODE_ROOT=<old checkout>` gives a baseline. The moving world
  (`streaming.py`) reframes between turns; anything that forces a reframe every turn is the usual cause of a
  long game slowing down.
- **Style:** comments are sparse, plain and in the game's voice; parenthesised asides explain why. Match the
  surrounding code. Keep the simulation's random-draw order unless a change means to alter behaviour.
