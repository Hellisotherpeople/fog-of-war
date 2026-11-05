# Working on FOG OF WAR

## Setup

```sh
git clone https://github.com/Hellisotherpeople/fog-of-war.git
cd fog-of-war
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python main.py
```

Python 3.10 or newer (developed on 3.12). The only runtime dependencies are `tcod`, `numpy` and
`pillow`; `numba` (`requirements-fast.txt`) is optional and speeds up distance fields and sight-line kernels
(`fow/fastpath.py`; `FOW_NO_NUMBA=1` turns it off, retaining the reference implementations). `piper-tts`
(`requirements-voices.txt`) is optional too: natural voices (`fow/neural_voice.py`), with models
downloaded into `~/.fogofwar/piper` on first use. Spoken voices use the OS speech engine if there is one: `say` on macOS (built in),
`espeak-ng` on Linux (`sudo apt install espeak-ng`). Without it, everything else still works.

## Running headless

Everything runs without a window under SDL's dummy drivers, which is how the tests, the fuzzer
and the GIF maker work:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -c "
from fow.game import Game
g = Game('bocage44', 'usa', seed=1, setup={'battlefield': 'standard'})
from fow.streaming import ensure
ensure(g)
for _ in range(120):
    g.player.moves = 0
    g.world_turn()
print(g.player.name, g.turn, len(g.actors), 'men on the field')
for m in list(g.messages)[-5:]: print(' ', m.text)
"
```

`Game(theatre, nation, role=None, seed=None, setup={...})` takes the same choices as the
creator: `service` (army/navy/air), `scenario` (`front`, `armour`, `raid`, `sea:carrier`,
`air:strategic`...), `rank` (a grade or national rank identity), `reality_radius`, `battlefield` (`standard`/`large`/`huge`) and so on. To drive the
real interface, build a `PlayState` around it with a stand-in app (see `FakeApp` in
`tests/test_smoke.py`) and call `on_key`. `PlayState` initializes seamless streaming; direct headless games must call
`streaming.ensure(g)` to opt into the same moving world. `setup={"seamless": False}` retains an
isolated single-field scene for focused tests.

`tools/benchmark_world.py --radius 240 --turns 180` measures full tactical turns. Run each radius
in a fresh process, with no concurrent tests; see [world notes](LIVING_WORLD.md).
Add `--profile /tmp/world.prof` for a separate cProfile run. Profiled timings include instrumentation
overhead and must not be compared directly with ordinary runs. See [native-core estimates](PERFORMANCE.md).
`--digest` adds a hash of core simulation results after timing, useful when comparing optimizations
at the same seed and turn count. It includes random-generator state, but is not an exhaustive replay verifier.
`--budget-ms 250` exits 3 if p95 exceeds the budget; CI runs this. Budget against a quiet machine, and only
raise it with a measured reason.

Saves carry `SAVE_VERSION` and are written to a temp file, fsynced, then swapped in behind a `.bak` copy;
`Game.load` falls back to the `.bak`. Add a migration in `Game._migrate_save` and bump the version when a new
field must exist in old saves. Content packs and their schema are in [PACKS.md](PACKS.md).

`FOW_DEBUG=1` makes an exception inside one soldier's AI stop the game instead of being logged
and skipped. Errors in a normal run go to `~/.fogofwar/error.log`.

`FOW_HOME=/some/dir` moves saves, settings, the memorial and the error log out of `~/.fogofwar`.
The tests, the fuzzer and the GIF maker set it to a scratch folder, so a test soldier's death never
lands in your memorial and a test game never overwrites (or, dying, deletes) your save. Do the same
in any script that plays the game.

## Tests

```sh
.venv/bin/python -m pytest tests          # or: .venv/bin/python tests/test_smoke.py
.venv/bin/python tools/longplay.py 3000   # long headless run with invariants checked every turn
.venv/bin/python tests/test_expansion.py  # weather, civilians, security, supply, air and sea additions
.venv/bin/python tests/test_orders_time_awards.py  # authority, real-time pacing and persistent citations
.venv/bin/python tests/test_identity_loot_ballistics.py  # dialogue, leads, physical loot, condition and ricochets
.venv/bin/python tests/test_squadcare.py  # observed needs, leader dispatch, triage and finite ammunition delivery
.venv/bin/python tests/test_vehicle_figures.py  # visible occupants, gun traverse, casualties and fog of war
.venv/bin/python -m pytest tests/test_command_realism.py tests/test_vehicle_start.py
.venv/bin/python -m pytest tests/test_staff_career.py tests/test_ui_search.py
.venv/bin/python -m pytest tests/test_doctrine_politics.py  # drills, politics, trace, camps, quotes, binding
```

`pytest.ini` runs test files across all cores by default (`pytest-xdist`, from
`requirements-dev.txt`), which takes the suite from about three minutes to about thirty seconds on
an M4 Pro. Add `-n0` to run serially when debugging a shared-state problem, or `-k` to narrow it.
Each worker gets its own scratch home through the test harness.

The smoke tests start every battle on both sides, every service, save and load aboard a ship
and a bomber, check a carrier is built full size, and run a carrier battle for four hours of game
time to make sure the war at sea goes somewhere. The full suite also exercises the moving land world;
runtime depends on the optional accelerator and hardware.

**The fuzzer** plays the real interface with random keys and mouse clicks and reports crashes:

```sh
.venv/bin/python tools/fuzz.py all 1 300                  # every battle, 300 inputs each
.venv/bin/python tools/fuzz.py bocage44,kursk43 3 500 allies cmd   # as senior officers
```

Run it after any change to the interface or the AI. Neither the tests nor the fuzzer touch your
own `~/.fogofwar/settings.json`. A scenario is capped at 2,000 world turns by default
(`FOW_FUZZ_TURN_LIMIT` overrides it), and long automatic waits yield to the next fuzz input after
60 world turns. This bounds random overnight-wait commands without changing simulation speed.
The result reports inputs and whether the turn cap was reached; any crash exits nonzero.

**Content packs** are checked before shipping:

```sh
.venv/bin/python tools/packcheck.py path/to/pack.json   # exit 1 on any malformed or duplicate entry
```

Packs can add theatres, items, vehicles, roles, missions, quotes and phrases. The schema is in
[PACKS.md](PACKS.md); they never contain code and are switched off in Options > Content packs.

## The GIFs in the README

```sh
.venv/bin/python tools/make_media.py            # all of them into docs/media/
.venv/bin/python tools/make_media.py carrier    # one
.venv/bin/python tools/make_media.py --list
```

Each clip is a real game run headless: the frames are read back from the renderer and assembled
with ffmpeg's palette filters (Pillow if ffmpeg isn't installed). The battle clips lift the fog of
war and hold the camera on the fighting; the rest are exactly what the player would see.

## Adding things

Most content is data, declared with small helper functions:

- **A weapon**: `gun(...)` in `fow/data/items.py`: calibre, magazine, damage, dispersion, range,
  equipment pools, years, then weight, fire modes, reload and shot costs, jam and heat, sound.
  Which soldiers carry it comes from the pools in `fow/data/nations.py` and the role kits in
  `fow/data/roles.py`.
- **Its picture**: a painter in `fow/icons.py`, keyed from `item_key` by the item's kind and family (above the
  item's own dimensions). It's drawn when the thing is hovered in the kit screen, looked at in the world, or
  looked over. `quality.py` reads a gun's worth off its stats and rarity; the AI and the men use it to decide
  what to carry and trade.
- **A vehicle or gun**: `fow/data/vehicles.py` (armour per facing, penetration, crew seats).
  Its footprint on the ground comes from its real dimensions (`fow/footprint.py`).
- **A ship**: `ship(...)` in `fow/data/ships.py` for her guns, armour, speed and air group; her
  hull and decks come from her class in `SPEC` in `fow/shipyard.py` (length and beam in two-metre
  tiles, and the list of decks). A new class needs a `SPEC` entry and, if its layout differs, a
  deck builder.
- **A historical place**: an entry in `fow/data/history.py`, keyed by theatre, laid by
  `landmarks.historical`; the note is shown when the marker is looked at. Keep it factual and short.
- **A battlefield scene**: a builder in `fow/tableaux.py` (weighted by ground and intensity) - props and
  cover, not decoration alone.
- **Country furniture**: a builder in `fow/varia.py`, returning `True` only after claiming a spot with
  `landmarks.spot` and `protect`; add it to `varia.menu` by ground/climate, or to `varia.rare` for a set
  piece. Buildings vary their footprint themselves (`mapgen.Gen.building`: wings, courtyards, cross plans,
  chamfered bays); do not assume a rectangle.
- **A tile**: `T(...)` in `fow/tiles.py` with physical properties (walk, cover, height, HP, what it becomes
  when destroyed, fire and crush behaviour) and a description; a palette variant goes through `variant` so
  the climate colours stay together.
- **A wound or treatment**: the clinical state lives on `body.Wound` (bleed, dirt, infection, arterial,
  fracture, dressing age) and `body` (shock, fever, splints). Treatments are selected in `actions.treat`
  and `medical.first_aid`; the AI triages with `medical.triage`/`squadcare.care_need`. Add new medical kit
  as `med=` in `fow/data/items.py` and handle it in `treat`.
- **A lesson**: a `(text, check)` pair in `fow/drill.py`; checks poll game state and must be true to pass.
- **A battle drill**: an entry in `fow/doctrine.py` with its nation, rank and leadership gate and its mods;
  the base order kind and the weights are read by the squad AI.  Add the spoken line to `fow/data/phrases.py`
  and its English to the automatic drill table in `fow/data/translations.py`.
- **A translated line**: add it to `fow/data/translations.py`; the speech tables are checked by
  `tests/test_sound_and_translation.py` and the option (`translate` in settings) shows it beside the original.
- **A quote**: `(tags, text, who, bio)` in `fow/quotes.py`; tags match cause, kit, role and nation.
- **A battle**: `theatre(...)` in `fow/data/theatres.py`: date and climate, sides and nations,
  who attacks from where, biomes, air/artillery/armour strength, place names, the real divisions.
  Commanders by date go in `fow/data/commanders.py`.
- **A nation**: names, doctrine and shouts in `fow/data/nations.py`, ranks in `fow/data/ranks.py`,
  phrases in `fow/data/phrases.py`.

Hand-drawn text (quotes, the after-action timeline, the death page) goes through `fow/textfit.py`:
`wrap`, `fit` once, `clip` to a row budget. Popups truncate and wrap their own lines, but anything
printed straight to a console must never be wider than its column.

## Style

- Diegetic first: if a soldier wouldn't know it, the screen shouldn't say it. Knowledge comes from
  kit (a watch, a map, a compass, binoculars, a radio) and from what people tell you.
- The same rules for every soldier on the field: if the player gets tired, cold, seen, or
  suppressed, so does everyone else, by the same code.
- Numbers the player sees must be real: a strength on a staff screen is what spawns.
- Docstrings and comments say *why*, in plain words. User-facing text is written like the rest of
  the game: short, concrete, period-appropriate.
