# FOG OF WAR: notes for agents

A WWII roguelike on python-tcod. About 83,000 lines of Python in `fow/`, so read the module, not the package.

- **Where things are:** the module map at the end of `docs/ARCHITECTURE.md` (one line per module). Content is
  data in `fow/data/` (items, vehicles, nations, theatres); item drawings are `assets/art/*.txt`.
- **Biggest files** (read them in ranges, and grep first): `play.py` (in-battle input and UI), `game.py` (turn
  loop, sound, saves), `ui.py` (app shell, menus), `ai.py` (squad, soldier and vehicle AI), `mapgen.py`.
- **Headless:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, and always `FOW_HOME=<scratch dir>` so a run
  never touches the real save in `~/.fogofwar`. `docs/DEVELOPMENT.md` has a runnable snippet and `FakeApp`.
- **Tests:** `.venv/bin/python -m pytest -q tests` (about 3 minutes;
  `--deselect tests/test_smoke.py::test_every_theatre_starts_and_runs` skips the slowest one). After interface
  or AI changes also run `tools/fuzz.py bocage44,kursk43 1 300`.
- **Speed:** `tools/benchmark_world.py --save ~/.fogofwar/save.pkl --turns 150 [--profile out.prof]` copies a
  save and times real world turns; `FOW_CODE_ROOT=<old checkout>` gives a baseline. The moving world
  (`streaming.py`) reframes between turns; anything that forces a reframe every turn is the usual cause of a
  long game slowing down.
- **Style:** comments are sparse, plain and in the game's voice; parenthesised asides explain why. Match the
  surrounding code. Keep the simulation's random-draw order unless a change means to alter behaviour.
