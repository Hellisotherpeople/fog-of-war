# Gameplay logic audit — October 2026

This pass concentrated on state crossing system boundaries: objective control,
streaming, orders, medical support, ammunition, inventory transfers and saves.
It also checked historical exception logs and all local Python imports. The old
`contacts.met`, `entities.things_at` and NumPy audio-selection errors were
already corrected in the current source; they are not counted as new fixes.

## Corrections

* Capturing requires twenty uninterrupted seconds by the same side. Enemy
  contest, an empty position or a change of capturing side resets progress.
* Objective references belong to the actual order. Reframing cannot attach an
  earlier objective to a new movement order. Reloaded sectors resolve references
  to the current objective instance, including saves made before this change.
* Incoming-fire locations, registered danger areas and shell-impact history
  retain their world positions when the tactical window moves. Defensive-position
  selection waits for distant targets to enter the frame rather than requesting
  sight lines from outside the terrain array.
* Local medical and ammunition errands survive strategic sector crossings in
  the seamless battlefield. A suppressed assigned helper does not prevent a
  nearer, capable medic from attending an urgent casualty.
* Medics no longer reserve casualties on the assumption that a tourniquet can
  treat a torso wound. Other available treatment can proceed when dressings run
  out. First-aid experience requires an actual treatment action.
* Repeat surgery excludes previous amputations from its duration and limb-saving
  decisions. Hospital recovery clears drug effects and preserves amputations.
  Stretcher safety checks read the soldier's actual recent-hit timestamp.
* Partial stripper-clip reloads preserve every cartridge and the source clip's
  ammunition condition. Overflow goes on the ground instead of disappearing.
  Stripping a magazine also preserves cartridge condition and charges time for
  every round handled, even when those rounds merge into an existing stack.
  Removing a magazine preserves whether its remaining round count is known.
* New inventory additions respect physical stack limits, retaining any unstowed
  remainder. Banknotes retain their defined bundle capacity. Picking up part of
  a stack takes time; the remaining supplies stay on the ground.
* Partly used packets cannot lose or gain contents through merging or splitting.
  Exhausting one packet opens the next instead of discarding the whole stack.
  Empty canteens cannot quench thirst.
* An inventory cannot remove an item from another owner's grid. Automatic trades
  check both inventories before transferring either offer, including oversized
  stacks inherited from older saves.
* Quartermaster purchases require room for the whole paid bundle. Inventory-screen
  transfers cannot move part of an offer while reporting failure and spending no
  time. Grenade resupply debits the actual quantity received; scavenging records
  only supplies physically collected, and ammunition assistants spend time on
  partial handovers as well as complete ones.

Existing carried items in an old save are not silently repacked or discarded.
Normal actions and additions apply the corrected rules.

## Reproduction and verification

The regressions are in `tests/test_logic_audit.py` and `tests/test_streaming.py`.
Two older tests now explicitly establish the equipment or transport state their
assertions require: the fire-support caller has a real radio, and the scout is
on foot before being tested for walking back to the issuer.

```sh
FOW_REQUIRE_GPU=1 .venv/bin/python -m pytest -q tests
FOW_NATIVE=off FOW_NO_NUMBA=1 .venv/bin/python -m pytest -q \
  tests/test_logic_audit.py tests/test_objective_completion.py \
  tests/test_order_compliance.py tests/test_squadcare.py tests/test_streaming.py
.venv/bin/python tools/audit_world.py --seed 73 --steps 360
.venv/bin/python tools/audit_world.py --theatre stalingrad42 --seed 119 --steps 300
.venv/bin/python tools/audit_world.py --save ~/.fogofwar/save.pkl --steps 240
```

The audit harness uses ordinary movement costs, combat and physiology. It checks
item ownership, ammunition bounds, entity IDs and objective references, and
saves and reloads the running game twice. A save supplied to it is copied first;
all writes go to a temporary directory. A natural player death ends the run.

Development soak checks exercised 1,404 world turns: Bocage (444 turns, 18 frame
origins), Stalingrad (325, 14), Guadalcanal (226, 5), and a copy of an existing
Hürtgen save (409, 23). These included seven save/load round trips. The Stalingrad
and Guadalcanal runs ended in normal combat deaths; the other two completed their
action budgets. The Hürtgen replay was repeated after the transfer fixes with
the same checked result. No original save was overwritten.

This is a targeted audit with reproducible regressions and live simulation
checks, not an exhaustive proof that every game system is free of defects.

## Agent demolition follow-up

The preserved Tunisia agent save had a plastic charge seated on a reinforced
concrete wall. Placement was recorded but discarded at detonation: the charge
removed only 396 of that section's 5,000 durability. Placed demolition charges
now apply five times the ordinary structural damage at the contact tile only.
This is game balance in the existing abstract damage model: masonry is
breachable, reinforced concrete still takes repeated work, and surrounding
blast and fragment damage retain their usual rules. Picking up or throwing a
charge removes its placement benefit; duds cause no damage.

The same mission had an impossible completion condition. It counted destroyed
ammunition/fuel tiles, but its headquarters target contained none. Demolition
orders now bind to persistent physical targets. HQ orders identify the radio
or mast; stores and rail orders track their assigned tiles; gun-only orders
track vehicle IDs. New HQs contain real radio equipment, while legacy saves
use the equipment already present. Unavailable terrain cannot count as a
destroyed target. New orders skip empty sites, and disabling HQ communications
also removes that post's services. The route arrow leads to briefed equipment
rather than an arbitrary compound center.

Timed charges previously disappeared when their fuses expired outside the
loaded terrain. Imminent fuses and secondary explosions now activate their
impact neighborhoods, including soldiers and vehicles, for the ordinary blast
simulation. That extra terrain is released after impact. Compression and
save/load preserve the charge's identity, avoiding live-looking duplicate items
after detonation. Attached charges follow a moved or wrecked vehicle, including
where a dud is left. Sabotage progress no longer depends on remaining in the
target's strategic cell, and escape distance is measured from the target.

`tests/test_demolition.py` covers physical damage, accumulated concrete damage,
duds, returned charges, vehicle attachments, real mission results, legacy saves,
and distant detonation across compression and save/load. The order-routing
regression now requires a briefed asset as its destination instead of the old
compound-center coordinate.

Verification: 405 full-suite tests passed with GPU checks required, plus 69
focused tests with native and Numba acceleration disabled. A copy of the agent
save completed 360 movement actions, 1,175 world turns, 19 frame origins, 39
invariant checks and two save/load cycles. The original planted charge reduced
its concrete section from 5,000 to 3,012 durability in the replay; the untouched HQ mast still
needed sabotage. The old save's charge received the placement benefit normally,
without replacing its equipment or awarding an unearned mission completion.

A sequential 60-turn timing pair averaged 10.864 ms before this change and
9.897 ms after, with identical core-state digests. This short sample precedes
detonation and is a regression check, not a general speedup estimate. Raw results
are in `docs/benchmarks/2026-10-12-demolition.json`.
