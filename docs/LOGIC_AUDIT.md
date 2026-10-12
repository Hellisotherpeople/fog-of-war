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
