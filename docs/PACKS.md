# Content packs

A pack adds content without touching the game's code. Packs live in `assets/packs/` (shipped) or
`~/.fogofwar/packs/` (yours); each is a `.json` file. Malformed entries are reported and skipped; nothing
else fails to load.

## Shape

```json
{
  "name": "Example pack",
  "author": "you",
  "version": 1,
  "theatres": {
    "my_battle45": {
      "name": "My Front", "battle": "The fight for the crossroads",
      "date": [1945, 2, 14, 6, 0], "climate": "winter",
      "sides": {"allies": [["usa", 1]], "axis": [["germany", 1]]},
      "weather": {"clear": 3, "snow": 2, "overcast": 1}
    }
  },
  "items": {"pack_pistol": {"name": "Pack pistol", "kind": "gun", "cal": "9mm", "mag": 8,
                            "dmg": 22, "disp": 2.0, "rng": 18, "nations": ["usa"], "years": [1944, 1950]}},
  "vehicles": {"pack_wagon": {"name": "Pack wagon", "vtype": "truck", "nations": ["usa"],
                              "years": [1940, 1950], "hp": 90, "speed": 80}},
  "roles": {"pack_role": {"name": "Pack role", "desc": "What the job does."}},
  "missions": {"pack_mission": {"name": "Pack mission", "w": 1, "desc": "What the battle is for.",
                                "role": null}},
  "quotes": [[["general", "caution"], "Quote text.", "Who said it", "A short, factual bio."]],
  "phrases": {"t_wire": {"en": ["Cut that wire, now!"]}}
}
```

- **theatres** takes the same fields as `fow/data/theatres.py`. A theatre id that already exists is skipped.
  `sides` maps each side to `[nation, weight]` pairs. See a real record for the full set (objectives, armour,
  artillery, weather, title, etc.).
- **quotes** are `[tags, quote, attribution, bio]`; tags are the ones used by `fow/quotes.py` (`general`,
  `artillery`, `tank`, `bleed`, role and nation keys, and so on). Keep the bio to one short factual line.
- **phrases** merges lines into an existing speech key (`fow/data/phrases.py`), by language code.
- **items** uses the fields of `fow/data/defs.py`'s `ItemType` (`name` and `kind` are required; `kind` is one
  of `gun`, `melee`, `gear`, `ammo`, `grenade`, `explosive`, `armor`, `medical`, `misc`). A gun needs a `cal`
  from `fow/data/items.py` so ammunition exists for it. Ids already present are skipped.
- **vehicles** uses `VehicleType` fields (`name` required; `vtype` is `tank`, `td`, `ht`, `truck`, `car`,
  `armoured_car`, `spg`...). A vehicle with no main gun still works as transport.
- **roles** is a partial `fow/data/roles.py` record. The role will use the rifleman's kit unless the player is
  given one in the creator; add skill floors separately if you need them.
- **missions** is a partial `fow/scenarios.py` record. `w` is the random-pick weight (0 keeps it out of the
  random pool) and `desc` is the briefing line; the battle type's own setup still applies.

Turn a pack off in Options > Content packs (it takes effect next start). Test a pack before shipping with
`python tools/packcheck.py my_pack.json`.

## Rules

- Prefer new theatre ids with a `_YY` or place suffix; don't overwrite the shipped battles.
- Quotes must be real and attributed. If a quotation is a misquote, say so in the bio.
- Phrase lines are spoken; keep them short and in the army's voice.
- No code in packs, so a pack can't break a save - but a pack removed from under a run that uses its item or
  vehicle id will leave that thing unnamed. Keep packs you have started runs on.
- Items and vehicles are plain data: balance them against their neighbours in `fow/data/items.py` and
  `fow/data/vehicles.py`, and give them years that match when they should appear.
