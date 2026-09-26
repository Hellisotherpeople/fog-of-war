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
`pillow`. Spoken voices use the OS speech engine if there is one: `say` on macOS (built in),
`espeak-ng` on Linux (`sudo apt install espeak-ng`). Without it, everything else still works.

## Running headless

Everything runs without a window under SDL's dummy drivers, which is how the tests, the fuzzer
and the GIF maker work:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -c "
from fow.game import Game
g = Game('bocage44', 'usa', seed=1, setup={'battlefield': 'standard'})
for _ in range(120):
    g.player.moves = 0
    g.world_turn()
print(g.player.name, g.turn, len(g.actors), 'men on the field')
for m in list(g.messages)[-5:]: print(' ', m.text)
"
```

`Game(theatre, nation, role=None, seed=None, setup={...})` takes the same choices as the
creator: `service` (army/navy/air), `scenario` (`front`, `armour`, `raid`, `sea:carrier`,
`air:strategic`...), `rank`, `battlefield` (`standard`/`large`/`huge`) and so on. To drive the
real interface, build a `PlayState` around it with a stand-in app (see `FakeApp` in
`tests/test_smoke.py`) and call `on_key`.

`FOW_DEBUG=1` makes an exception inside one soldier's AI stop the game instead of being logged
and skipped. Errors in a normal run go to `~/.fogofwar/error.log`.

## Tests

```sh
.venv/bin/python -m pytest tests          # or: .venv/bin/python tests/test_smoke.py
```

The smoke tests start every battle on both sides, every service, save and load aboard a ship
and a bomber, check a carrier is built full size, and run a carrier battle for four hours of game
time to make sure the war at sea goes somewhere. About twenty seconds.

**The fuzzer** plays the real interface with random keys and mouse clicks and reports crashes:

```sh
.venv/bin/python tools/fuzz.py all 1 300                  # every battle, 300 inputs each
.venv/bin/python tools/fuzz.py bocage44,kursk43 3 500 allies cmd   # as senior officers
```

Run it after any change to the interface or the AI. Neither the tests nor the fuzzer touch your
own `~/.fogofwar/settings.json`.

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
- **A vehicle or gun**: `fow/data/vehicles.py` (armour per facing, penetration, crew seats).
  Its footprint on the ground comes from its real dimensions (`fow/footprint.py`).
- **A ship**: `ship(...)` in `fow/data/ships.py` for her guns, armour, speed and air group; her
  hull and decks come from her class in `SPEC` in `fow/shipyard.py` (length and beam in two-metre
  tiles, and the list of decks). A new class needs a `SPEC` entry and, if its layout differs, a
  deck builder.
- **A battle**: `theatre(...)` in `fow/data/theatres.py`: date and climate, sides and nations,
  who attacks from where, biomes, air/artillery/armour strength, place names, the real divisions.
  Commanders by date go in `fow/data/commanders.py`.
- **A nation**: names, doctrine and shouts in `fow/data/nations.py`, ranks in `fow/data/ranks.py`,
  phrases in `fow/data/phrases.py`.

## Style

- Diegetic first: if a soldier wouldn't know it, the screen shouldn't say it. Knowledge comes from
  kit (a watch, a map, a compass, binoculars, a radio) and from what people tell you.
- The same rules for every soldier on the field: if the player gets tired, cold, seen, or
  suppressed, so does everyone else, by the same code.
- Numbers the player sees must be real: a strength on a staff screen is what spawns.
- Docstrings and comments say *why*, in plain words. User-facing text is written like the rest of
  the game: short, concrete, period-appropriate.
