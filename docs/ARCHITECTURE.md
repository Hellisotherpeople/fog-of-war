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
                landmarks.py        windmills, stations, châteaux, forts, shrines...: the named places
                gamemap.py tiles.py the map arrays (terrain, cover, sight, cost, items, mines, fire)
                going.py            the going in words (the look) and as a tint (X)
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
*away* and round obstacles rather than into corners. The maps are NumPy arrays scanned by
`fastpath.dijkstra2d`: with numba installed, a compiled Dial's algorithm (the costs are small
integers, so a ring of buckets replaces the heap), otherwise `tcod.path.dijkstra2d`, with
identical results either way.

On top of the maps, the small-unit tactics of the manuals, in `ai.py` and `commander.py`:

- **Fire control.** Every few seconds a section leader picks the target that matters, the machine
  gun first, and calls it (`designate`, with the shout). Each man's target choice (`choose_target`)
  weighs that target, the man already in his sights (aim taken counts) and whoever is shooting at
  him.
- **Contact.** Rounds cracking past are contact (`combat.suppress_line` stamps `ai["fired_on"]`
  with where they came from), whether or not the shooter has been seen. The section goes to fire
  and movement, and returns fire at the flash in the hedge, near enough (`return_fire`).
- **Fire and movement.** Bounding teams change over when the movers are down in cover, not by the
  clock (`bound_phase`). The team that isn't moving puts rounds on the known positions. Movers go
  in rushes: up, across, down in cover, never crawling over open ground under fire. An assault
  goes in when the enemy is suppressed, or when the section is close with odds of two to one.
- **Smoke.** Crossing ground a machine gun or anti-tank gun covers, a man with a smoke grenade
  throws it between them (`call_smoke`).
- **Cover.** A man in the open looks for a spot a step away with more cover that still has a line
  of fire (`fire_position`). At the crump of a shell he goes flat. A section holding ground where
  the shells keep falling moves its positions off the beaten zone (`beaten_zone`, from
  `game.impacts`). A rifleman facing a tank he can do nothing to gets out of its machine guns'
  sight first (`hide_from_tanks`).
- **Fire discipline.** Defenders hold their fire at long range until the section opens up. A lull
  is for putting a full magazine on.
- **The approach.** Going for ground the enemy holds, the covered map to the objective charges
  extra for open ground near it (`Brain._open_ground`). Men keep to hedges, walls, woods and dead
  ground whether or not anyone has been seen there yet.
- **Support.** A machine gun, sniper or anti-tank team in the attack takes up a position with a
  field of fire over the objective, where it has got to (`assign_positions`).
- **Falling back.** A section that falls back without orders stops in cover a few hundred yards
  back instead of leaving the field (`rally`), and is back in the fight when its nerve returns.
- **Tanks.** A tank stays with its infantry: more than a hundred yards ahead, it halts until they
  come up (`waits_for_infantry`). Halted, it turns its front armour toward the gun that can kill it
  (`face_the_threat`).
- **Commanders.** An attack goes where the enemy is known to be weakest, with up to three squads
  together (a Schwerpunkt). A lost position is counterattacked at once only if what is left there
  can beat what is known to be in it.

These were checked against the old AI in mirrored battles and small infantry fights (same field,
same seed, each side taking the new AI in turn). The side with the new AI fought at least as well
in every test, and a little better on balance, at no cost in speed.

What keeps a big battle quick:
- `GameMap.refresh()` diffs the tile array against the last one and recomputes only the changed
  rectangle (plus a margin for directional cover), and counts separately whether walking,
  sight or only smoke changed (`walk_version`, `see_version`, `see_base_version`).
- The brain redraws its maps when walking changes, at most every 10 turns; the cost map is cached
  on (map, version, known mines).
- Lines of sight are cached per map (keyed by `see_base_version`); lines through the smoke's
  bounding box skip the cache.
- Concealment is cached per target per turn; binoculars are looked up once a minute.
- A soldier's look round is one compiled call: every line of sight from him to the men he might
  see, drawn in numba (`fastpath.sight_lines`; the same Bresenham line and crest check as
  `senses.los_clear`, which is what runs without numba).
- One distance matrix per side per turn serves every soldier's vision (`game._vis_mat`).

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
- Between missions, `naval.py` decides what the force does next (`after_action`): back to a naval
  base (`nearest_port`, designated on a friendly shore if the side has none; the map generator
  builds the quay, piers and harbour office) or new orders (`skysea_missions.new_orders`, reusing
  the ships you have). In port the condition is "port": a refit on timers, harbour watches, and
  liberty. Going ashore stores the whole ship (`_store` plus the `SkySea`) in `game.ship_ashore`
  and puts you on land; the port director's boat restores it. While you're ashore, `land_tick`
  runs her refit and sails her at her time, with or without you.

## Bases

Installations on the war map (`Sector.installations`) become places on the battlefield
(`mapgen.installation` records in `m.gen_positions`), and `base.spawn_staff` puts the people who
run them at their posts, each marked `ai["post"]` (the AI walks them back to it when things are
quiet) in a squad of kind `staff` that the side commander leaves alone. The records are saved with
the sector's map; on a revisit `populate` puts the people and vehicles back (neither is saved with
the map) but not the stores, which are, and skips installations that have been taken since. Walking into one, or right-clicking, is `base.talk`. The adjutant's orders
live in `game.base_order` and are checked in `base.update`; `order_point` and `order_plan` give
the arrow and the Enter action, pathing through friendly sectors to the edge when the job is
somewhere else.

## Fire support: fires.py

`Fires` (on `game.fires`, reached through `game.support.fires`) holds `Battery` and `Squadron`
objects: gun batteries from each "artillery" installation, a mortar platoon per battalion in the
line and in your sector, ships for the attacker of a landing, squadrons at airfields (or in the rear
when there are none). Each has a sector, guns or aircraft, ammunition or readiness, and a name.
`Support.request_fire` / `barrage` / `launch_sortie` keep their signatures and delegate. A mission
is `battery.mission`: a target on your map (`("map", sector, (x, y))`) or another sector
(`("sector", ...)`). `Fires.update` fires it gun by gun at the gun's rate: the battery's guns on
your map (placed by `place_guns` from the installation record, one piece per gun, `v.ai["battery"]`),
the mortarmen of its squad (`link_mortars`: their own weapons and bombs), or numbers when it's
elsewhere, with a distant report from its bearing. Rounds on another sector are added up and taken
off the enemy there, with `Strategic._attrit`, when the mission ends, so the observer's report is
what happened. `strategic_tick` resupplies, loses overrun batteries, and gives each free battery a
mission at the fighting in its reach. The player's battery (`player_battery`) keeps a share of each
mission for the player's gun (`player_left`), with `firing_data` for the orders and
`fire_player_round` for Enter.

## Skills

`skills.py`: `a.skills` maps twelve keys to 0-10. `roll(rng, a)` (called by `spawn.make_soldier`) draws
each around `0.55 * a.skill` with a spread, then raises the ones in `ROLE_SKILLS[a.role]` and
`UNIT_SKILLS[unit_type]` to their floors (plus a little noise), then applies `TRAIT_SKILLS`;
`spawn.apply_special` re-floors for special units. `level(a, k)` reads one (old saves without skills
get a value worked out from `a.skill` and the role). `use(game, a, k, amount)` is practice: a gain that
shrinks as the skill rises, and a message when the word for it changes. The skills act where the work
is done, not through a central modifier:

- marksmanship in `combat` (recoil, aim time, dispersion);
- gunnery in `vehicle_fire_main`, `fires` and the mortar;
- `stealth_mult` in `stealth.fieldcraft`, `observe_mult` in `stealth.notice`;
- first aid in `medical.skill`, demolitions in `actions.place_charge`;
- driving in `play.drive`, radio in `fires.start` (the observer's error);
- leadership in `game._leadership`, `fitness_mult` in the fatigue drain;
- languages in `prisoners.demand_surrender`.

`StatusState` (`@`) shows them on its second page.

## Vehicles: parts

`vdamage.py`: every vehicle has `parts` (tracks, engine, transmission, fuel, gun, turret, optics,
radio, one per machine gun, ammo), each 2 working / 1 damaged / 0 knocked out. The old flags
`engine`, `tracks` and `gun_ok` are properties over them (and `__setstate__` migrates saves). A
penetration picks one to three locations from a table for the face it came through; a location is
a part or a crew seat. Crew seats: `crew_hit` puts the seat in `ai["seat_out"]` for 20-60 s, and
`crew.manned` skips it until the crew has shifted across. The effects live where the work is done:
`can_move` / `move_mult` in movement, `traverse` (power / hand / jammed / hull) in the gunnery,
`gun_disp` and `reload_mult` in `vehicle_fire_main`, `mg_ok` in `vehicle_fire_mg`, `has_radio` via
`command.vehicle_has_radio`, `optics_mult` in `senses.vehicle_eye`. Hatches: `v.buttoned`, set by
`hatch_ai` (or the player commander); `exposed_hit` gives bullets and splinters a chance at an
open-hatched commander.

## Seeing

`senses.daylight` works the sun's elevation from each battle's latitude, longitude and clock
(`theatres.SUN`) and the date, with civil and nautical twilight; `moonlight` adds the moon's phase
and height under the cloud. `base_view_range` blends night and day continuously, and the dark only
adds flashes and lit ground on top of it. A vehicle's eye is `vehicle_eye` (commander head-out,
buttoned, or none); the player's is `player_eye`, per seat, with cones for the gunner's sight and
the driver's visor. Anyone up in a vehicle, or looking at one, uses `GameMap.high()`, which sees
over crops and undergrowth (`tiles.SEE_HIGH`), with its own line-of-sight cache.

## Vehicles: riders and maintenance

`maintenance.tick` runs every five turns on land. A vehicle's needs are plain state: `tracks`,
`engine`, `gun_ok`, the racks against `full_load`. `quiet` says whether the crew can climb out
(no squad contact for a minute, not fired for 30 s, not hit for a minute, no enemy it can see
within 40 tiles); `combat.hit_vehicle` stamps `ai["hit_turn"]`. Work is man-seconds: the crew plus
`helpers` (friendly soldiers beside the hull who aren't fighting; the player only when he's chosen
to help). Rearming comes from a `source`: an ammunition truck (`ai["cargo"]`) within eight tiles,
a dump on our own ground, or a crate of shells on the ground. `call_truck` sends a truck from the
home edge in a squad of kind `supply`, which the side commander leaves to its run; `_trucks` keeps
it with the vehicles and takes it home when it's empty. The player's side of it (`help_with`,
`take_crate`, `hand_up`) is on the right-click menu, and `duty.py` issues the "track" and "shells"
tasks; `base.supply_run_order` is the motor sergeant's job. A tank with no seats carries up to
`RIDERS` on its hull (`ai["rider"]` on the man); `combat._riders_hit` shares out what hits it.

## Drawing

Everything is drawn into one 120 × 50 text console (`render.py`), map on the left, the panel on
the right, messages below. In ASCII mode that's all. In sprite mode `render_sprites.py` also
builds a stack of layer consoles (ground, objects, figures, overlays) that `gfx.py` draws with
a separate sprite tileset scaled to the zoom, with the text console composited on top.

Sprites are **painted by code** at 64 px (`sprites.py`): terrain textures per biome, objects,
vehicles from their real footprints, and soldier figures built from what each man is actually
wearing and carrying (`figures.py`), so a Soviet sniper in a winter smock looks like one. Nothing
is loaded from image files except the fonts.

Terrain follows one rule so the going can be read at a glance: a tile you can't walk through
(`T.WALK` false) is painted on its own layer and stood on its ground by `Canvas.stand` - a dark rim
round its solid shape and a cast shadow - and full-tile obstacles like hedgerows get `Canvas.bevel`,
lit top-left and shadowed bottom-right like a wall. Walkable tiles are painted flat, with no rim or
shadow. New tiles go on the end of `tiles.py` (saves store tile ids); `paint_place` paints the
landmark tiles.

`landmarks.py` runs inside `mapgen.Gen.run` after the ground, villages and rivers and before the
defences. `menu()` weights about two dozen builders by biome, climate and language; `place()` builds
`1 + 0.9 k` of them (k: how much bigger than the standard field) with `gen.rng` swapped for a private
stream, so the rest of a sector's making is what it always was for its seed. Each builder finds a
free rectangle (`spot`), builds with `gen.building` and the tile helpers, lays a cart track to the
nearest road (`track`, around buildings and water), protects its ground and adds a POI. Landmarks on a
rise or in a hole register `gen.rises`, which `relief.make` adds to the heightmap. `dress()` adds the
calvaries, memorials, named buildings, poplars and telegraph poles; `fortify()` runs after the
defences (Tobruk pits, sangars).

The interface's pictures (`icons.py`) are painted by code too. Any screen asks for a picture over a
rectangle of text cells with `icons.pic(x, y, w, h, key)`: a key such as `gun:rifle`,
`doll|head:96c88c:,...`, `rounds|4|8|8` (sure of 4 of 8) or `terrain|bocage|ours|0|12,7`.
`gfx.present` paints it at exactly that rectangle's pixel size and caches it as a texture. Painters
work in unit coordinates at 3× and are scaled down, so a picture is crisp at any window size.
Translucent ink goes on a clear sheet and is composited, because PIL would overwrite rather than
blend.

There are three layers:
- `under`, beneath the text console: its cells are made see-through by `icons.under`, which leaves
  a dark label behind each letter. The war map's squares use this.
- `ui`, over the text console.
- `over`, over the overlay console (the kit screen).

Popups, lists and tooltips call `icons.erase` over their boxes so nothing painted earlier shows
through. The text under a picture stays: it's what shows without a renderer, and with Options >
Pictures in the interface off.

## Sound

`audio.py` synthesises every sound at start-up (gunfire by calibre, explosions, engines, the
ambient battle) with NumPy and plays it positionally through SDL, mixed in channels (weapons,
ambience, voices, effects, interface) under the Options menu's mixer. `voice.py` speaks orders,
shouts and radio traffic in each nation's language through the operating system's speech
engine (`say` on macOS, `espeak-ng` on Linux) if there is one, and caches the results. With
`piper-tts` installed and the "neural" engine chosen, `neural_voice.Piper` renders them instead:
per-locale model lists (`MODELS`), fetched in the background by `Downloader`; many-speaker models
are split into men and women by measuring each speaker's pitch once (`speakers.json`). Any locale
without a model ready falls back to the system engine line by line.

## Module map

| module | what it does |
|---|---|
| `game.py` | the Game: turn loop, sound and fire, sectors and travel, saves |
| `play.py` | the in-battle state: input, commands, targeting, popups, Enter-to-do-your-orders |
| `ui.py` | App shell, menus, the creator, options and mixer, help, status, war map |
| `helpdata.py` | the help's sections (keys, labels, text; `{key}` marks bold); "Right now" comes from `PlayState.help_now` |
| `render.py`, `render_sprites.py`, `gfx.py` | drawing: text console, sprite layers, compositing |
| `sprites.py`, `figures.py`, `fonts.py` | procedural sprites, soldier figures, font tilesets |
| `audio.py`, `voice.py`, `neural_voice.py` | synthesised positional sound, spoken lines (system speech, or Piper neural voices) |
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
| `maintenance.py` | field repairs, rearming, ammunition trucks, riders on the hull |
| `vdamage.py` | vehicle parts, what breaking each costs, hatches, crew seats hit |
| `fires.py` | real batteries, mortar platoons, ships and squadrons; fire missions; the gun line |
| `tasks.py` | squad tasks: scavenging, the wounded, prisoners, a hand for the tanks |
| `medevac.py` | calling stretcher-bearers, the evacuation chain, hospital time, back to duty |
| `agents.py`, `data/agents.py`, `data/items_special.py` | the secret war: careers, covers, agent and resistance missions, the wireless and direction-finding, supply drops from special-duties squadrons, the special weapons and gadgets |
| `relief.py`, `floors.py` | the heightmap (generation, viewsheds, crest checks, slope costs, hillshade) and building floors (stairs, cellars, open tops, falls, AI use) |
| `icons.py` | pictures in the interface: painters (kit, body, stance, rounds, sky, map sheet, sight picture...), keys, and the per-frame picture list that `gfx.present` paints, caches and draws under, over and above the consoles |
| `rear.py` | the living rear: convoys, columns and posts on the supply roads; destroying them cuts the road on the war map (`Strategic.interdict`, supply parents and traffic in `compute_supply`) |
| `orders.py` | the orders book (all the orders you hold, who gave them, rewards and punishments, carried out) |
| `people.py` | every soldier's life (home, trade, family, temper, vices), his opinion of you, his buddy, and what things are worth to him (`worth`, `deal`: the same rules for his trades with you and with his mates) |
| `talk.py` | talking to anyone (E): comrades, the wounded, prisoners; favours, intelligence, trading, gifts |
| `social.py` | the noise of a fight (cries by wound and part, buddies, calls, panic, NCOs) and the life of a quiet hour (smokes, trades, photos, letters, prayers, songs, mourning, souvenirs) - lines in `data/chatter.py`, every army's own language |
| `data/notable.py` | the famous regular divisions, brigades and battalions of each battle, with their real regiments (designations, the chain of command, the new-game Unit list) |
| `succession.py` | autopilot, and carrying on as another soldier when you die |
| `melee.py` | hand to hand: moves, parries, where blows land, clinches, silent kills |
| `skills.py` | twelve skills per soldier: rolled at birth, floors from role and unit, practice, the helpers the systems use |
| `fastpath.py` | Dijkstra maps: numba Dial's algorithm, or tcod |
| `skysea.py`, `skysea_missions.py`, `skyseaui.py`, `skysea_exit.py` | the war at sea and in the air, its missions, the chart/flight view, coming back to earth |
| `aboard.py`, `shipyard.py`, `shipboard.py` | one man aboard; ships built deck by deck; shipboard life |
| `naval.py` | the navy between battles: new orders or back to base, the refit, liberty ashore, sailing orders |
| `base.py` | friendly bases: the staff at their posts, what they do for you, the adjutant's orders |
| `nearby.py` | `V`: everything around you in a list |
| `settings.py`, `constants.py` | persistent settings, layout and tuning constants |
| `data/` | nations, ranks, items, vehicles and aircraft, ships, theatres, roles, special units, commanders, phrases, banter |
