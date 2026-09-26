# How FOG OF WAR is put together

About 46,000 lines of Python in one package, `fow/`, on top of
[python-tcod](https://github.com/libtcod/python-tcod) (SDL3), NumPy and Pillow. There is no
engine besides those: the map, the AI, the sprites, the sound and the war are all generated
by the code here.

The one rule the design comes back to: **you are one person, and the whole war is simulated
around you.** Everything below serves that, from the size of a battlefield to the way a carrier
is built deck by deck.

## Scale: space and time

| | |
|---|---|
| one tile | 2 metres |
| one turn | 1 second (a normal soldier gets 100 *moves* a turn; walking a tile costs about 100) |
| a battlefield (sector) | 270 × 180 tiles by default: about 540 × 360 m (`standard` 180 × 120, `huge` 360 × 240) |
| the strategic map | a grid of sectors that never ends: the front runs on, the rear goes back, countries change |
| the strategic tick | every 600 turns (10 minutes): attacks resolve, reserves move, the front shifts |
| the sky and the sea | a separate world in 100 m units (`fow/skysea.py`), stepped once a second |
| a ship | built 1:1 from her real length and beam, every deck (`fow/shipyard.py`) |

Numbers on the general's screens are the numbers that really spawn: a division's "1,035 men"
is what you'd count if you walked its sectors (`Strategic.scale` multiplies troops for the
bigger battlefields; `oob.py` builds the formations over them).

## The layers

```
 data           fow/data/*          nations, ranks, weapons, vehicles, ships, battles, commanders
   │
 the war        strategic.py        sectors, control, the front, reserves, depots, the strategic tick
                world.py            the world beyond the battle: regions, coasts, place names
                operations.py oob.py  divisions, corps and armies over those sectors, with commanders
                hierarchy.py        your chain of command up to the head of state, by date
   │
 a sector       mapgen.py           procedural battlefield: terrain by biome, towns, forts, depots
                gamemap.py tiles.py the map arrays (terrain, cover, sight, cost, items, mines, fire)
                spawn.py            soldiers, squads, vehicles, the player; filling a battlefield
   │
 the fight      game.py             the Game object and its turn loop
                brain.py            per-side Dijkstra maps: threat, safety, objectives, cover
                ai.py commander.py  squads, soldiers, vehicles, side commanders
                senses.py stealth.py  sight, light, hearing; being noticed takes time
                combat.py body.py   ballistics, penetration, blasts, wounds, bleeding, consciousness
                actions.py          verbs shared by the player and the AI
                command.py duty.py  orders and how they travel; what's expected of you
   │
 sea and air    skysea.py           ships and aircraft in their own world; missions in skysea_missions.py
                aboard.py           you, one man on a ship's deck or in a bomber's fuselage
                shipyard.py         ships built deck by deck at real size
                shipboard.py        watches, general quarters, the ship's company, your jobs
   │
 the interface  ui.py               the App: window, event loop, menus, full-screen views
                play.py             the in-battle state: keys, mouse, targeting, popups, Enter-to-do-it
                render.py           the text console: map, HUD, popups, effects
                gfx.py sprites.py render_sprites.py figures.py   the sprite layers
                audio.py voice.py   synthesised sound; spoken lines through the OS's speech engine
```

## One game, one object

`fow.game.Game` owns everything: the strategic map, the current sector's `GameMap`, the actors,
squads and vehicles on it, the two sides' `Brain`s, the command structure, the sky-and-sea
world if you're in it, the clock, and the message log. Saving is `pickle.dump(game)` to
`~/.fogofwar/save.pkl` (`Game.__getstate__` drops the few things that can't be pickled, such
as lambdas and UI hints). There is no separate save format to keep in step with the code.

`App` (`fow/ui.py`) holds a stack of *states*: the title menu, the creator, the battle
(`PlayState`), the war map, the general staff and so on. Each has `render(console)` and
`on_key(key)`; the top one gets the input and is drawn.

## The turn

`PlayState` turns your key presses into actions. Each action costs *moves*, and `Game.world_turn()`
runs once per second of game time until you have moves again. A turn, in order:

1. the clock; light, if it's dark;
2. each side's brain refreshes the Dijkstra maps that are due (every 8 turns, 4 if something
   urgent happened; the expensive ones lazily);
3. squads decide what they're doing (every other turn); side commanders reassign objectives (every 20);
4. every soldier gets his moves (his speed: load, wounds, breath, pace) and spends them through
   `ai.soldier_act`: move, shoot, reload, bandage, dig, surrender...;
5. vehicles act, crew seat by seat;
6. bodies: bleeding, shock, consciousness, morale (leaders nearby help), stamina, cold and heat;
7. fire and smoke spread, shells in flight land, sounds propagate;
8. medicine, banter, discipline, the war around you (threats: patrols, air raids, barrages);
9. every 600 turns, the strategic tick: the whole theatre moves on.

The player obeys the same rules as everyone: the same pace and breath model (`pace.py`), the
same cold (`thermal.py`), the same stealth (`stealth.py`) and the same ballistics.

## The AI: Dijkstra maps

Following RogueBasin's "The Incredible Power of Dijkstra Maps", each side's `Brain` keeps
whole-map distance fields: distance to the objectives, to known enemies, to cover, to safety;
and a threat field built from where the enemy has been seen and heard. A soldier doesn't
path-find; he rolls downhill on a weighted sum of these maps, with weights set by his squad's
order (attack, hold, fall back, flank) and his own state (pinned, wounded, out of ammo). The
flee map is the distance-to-the-enemy field multiplied by -1.2 and scanned again, so men run
*away* and round obstacles rather than into corners. The maps are NumPy arrays scanned with
`tcod.path.dijkstra2d`, so a whole side costs a few milliseconds.

## The war around you

The battlefield you're on is one sector of `Strategic`. The sectors next to it are simulated
more coarsely but honestly: their forces are counts of real squads and vehicles, and when they
attack you, those men march in over your map edge. Walk off the edge and the next sector is
generated at full detail, with the same men in it. At every strategic tick the front
resolves: sectors attack their neighbours according to the orders of their divisions (yours, if
you're a general), depots feed them, and cut-off sectors wither.

`oob.py` hangs a real order of battle over the sectors: a battalion to a sector, three to a
regiment and so on up to army groups, with historical formations and commanders
(`data/commanders.py`) where the data has them and generated ones where it doesn't. The
general's screens (`G`, `C`, `m`) show and command this structure.

## Sea and air: one man aboard

`skysea.py` is the sea and sky: ships and aircraft with real speeds, armour, guns, torpedoes,
radar, air groups and flak, in a world where one unit is 100 m. Missions (`skysea_missions.py`)
set up a surface action, carrier battle, convoy, submarine patrol, bombardment or air raid,
and the AI fights it: the captain of your own ship (`SkySea._captain`) closes to gun range or
stands a carrier off at strike range, steers round islands, launches strikes, and takes her home.

You aren't the ship. `aboard.py` puts you on her:

- `shipyard.build(ship)` makes every deck of her at 2 m a tile from `SPEC` (length, beam, decks):
  compartments laid out along her length (berthing, messes, galleys, sickbay, magazines, fire and
  engine rooms, repair lockers, CIC, avgas...), guns and AA mounts from her real armament, ladders
  that line up between decks. Every deck is a `GameMap` of the same frame.
- Only the deck you're on is simulated man by man. The others are stored (`_store` / `_load`)
  and repopulated from each deck's slots (battle stations, watch stations, bunks) when you go
  there. Men leave by the ladders and arrive by them.
- `shipboard.py` runs her routine: Condition III with watches of four hours in three sections,
  general quarters, jobs handed to you (ammunition, fires, shoring, casualties, lookouts), and
  `fast_step` for letting hours go by in 30-second steps until something matters.
- Hits in `skysea` land on the deck they'd really hit (`HIT_DECKS`): bombs on the flight deck,
  torpedoes low. On your deck they're real explosions; elsewhere they damage tiles and men
  abstractly and you feel them through the hull.
- Bombers work the same way: the fuselage is a map, the crew are soldiers at stations, flak and
  fighter hits in `skysea` come through the skin onto them.

## Drawing

Everything is drawn into one 120 × 50 text console (`render.py`), map on the left, the panel on
the right, messages below. In ASCII mode that's all. In sprite mode `render_sprites.py` also
builds a stack of layer consoles (ground, objects, figures, overlays) that `gfx.py` draws with
a separate sprite tileset scaled to the zoom, with the text console composited on top.

Sprites are **painted by code** at 64 px (`sprites.py`): terrain textures per biome, objects,
vehicles from their real footprints, and soldier figures built from what each man is actually
wearing and carrying (`figures.py`), so a Soviet sniper in a winter smock looks like one. Nothing
is loaded from image files except the fonts.

## Sound

`audio.py` synthesises every sound at start-up (gunfire by calibre, explosions, engines, the
ambient battle) with NumPy and plays it positionally through SDL, mixed in channels (weapons,
ambience, voices, effects, interface) under the Options menu's mixer. `voice.py` speaks orders,
shouts and radio traffic in each nation's language through the operating system's speech
engine (`say` on macOS, `espeak-ng` on Linux) if there is one, and caches the results.

## Module map

| module | what it does |
|---|---|
| `game.py` | the Game: turn loop, sound and fire, sectors and travel, saves |
| `play.py` | the in-battle state: input, commands, targeting, popups, Enter-to-do-your-orders |
| `ui.py` | App shell, menus, the creator, options and mixer, help, status, war map |
| `render.py`, `render_sprites.py`, `gfx.py` | drawing: text console, sprite layers, compositing |
| `sprites.py`, `figures.py`, `fonts.py` | procedural sprites, soldier figures, font tilesets |
| `audio.py`, `voice.py` | synthesised positional sound, spoken lines |
| `mapgen.py`, `gamemap.py`, `tiles.py` | battlefield generation, map arrays, tile definitions |
| `spawn.py`, `entities.py` | creating soldiers, squads, vehicles; the classes |
| `ai.py`, `brain.py`, `commander.py` | squad/soldier/vehicle AI, Dijkstra maps, side commanders |
| `actions.py`, `combat.py`, `body.py` | verbs, ballistics and blasts, wounds |
| `senses.py`, `stealth.py`, `pace.py`, `thermal.py` | sight and hearing, being noticed, movement and breath, cold and heat |
| `inventory.py`, `ammo.py`, `invui.py`, `loot.py`, `familiar.py` | Tarkov-style grid kit, magazines, the kit screen, what's lying around, knowing your weapon |
| `command.py`, `cmdui.py`, `hierarchy.py`, `oob.py` | orders and how they travel, the command screen, the chain up to heads of state, the order of battle |
| `operations.py`, `opsui.py`, `strategic.py`, `world.py` | the general's war, the theatre, the world beyond |
| `scenarios.py`, `threat.py`, `support.py` | battle types and missions, what the war does to where you are, artillery and air |
| `duty.py`, `medical.py`, `logistics.py`, `qmui.py`, `prisoners.py`, `pow.py` | discipline, medicine, supply, the quartermaster, taking prisoners, being one |
| `crew.py`, `footprint.py` | vehicle crew seats, vehicle sizes |
| `skysea.py`, `skysea_missions.py`, `skyseaui.py`, `skysea_exit.py` | the war at sea and in the air, its missions, the chart/flight view, coming back to earth |
| `aboard.py`, `shipyard.py`, `shipboard.py` | one man aboard; ships built deck by deck; shipboard life |
| `settings.py`, `constants.py` | persistent settings, layout and tuning constants |
| `data/` | nations, ranks, items, vehicles and aircraft, ships, theatres, roles, special units, commanders, phrases, banter |
