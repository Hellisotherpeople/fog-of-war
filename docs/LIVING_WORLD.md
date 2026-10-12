# The moving world

The land world uses unbounded integer coordinates. `streaming.Landscape` assembles the nearby
terrain into a NumPy/tcod buffer and moves that buffer with the player. Crossing a generation
cell boundary is an ordinary footstep or vehicle movement, with the same people and vehicle.
There is no sector-transfer loading screen, replacement squad or free travel time.

Full tactical activation follows a circle around the player. The allocation is rectangular
because NumPy, tcod and the existing pathfinding use rectangular arrays; this allocation is
not a square simulation boundary. Engaged soldiers, medical work, vehicle occupants and
incoming artillery retain additional simulation space. Reframing happens between world turns.
Orders, sights, map damage, construction, corpses, items, shells and interface routes retain
their world positions. Artillery missions store canonical world addresses.

Terrain storage reuses padded arrays as the frame moves: the overlapping terrain stays in
place, with newly exposed strips filled from persistent generation cells. Occasional
compaction at a storage edge and full rebuilds after large jumps preserve the same cells.
This storage organization creates no gameplay boundary and does not reduce simulation detail.

Options → Simulation radius sets the radius for new games: 180, 240, 360, 480 or 640 two-metre
tiles. The default is 240. Larger values increase both CPU and memory requirements. Force
density controls the older troop-density/generation-cell presets separately. Python/tcod and
the optional existing numba accelerator are retained. Large navigation fields retain a search
frontier and calculate exact distances on demand; they still explore any detour needed to prove
the shortest distance. Vehicle destinations no longer in use expire from the cache; revisiting
one calculates the same exact route again. Without numba, the full tcod pathfinder remains available.

Beyond the tactical circle, the strategic simulation continues to move forces, resolve battles
and consume supplies. Previously materialized units retain their people when transferred;
coarse casualties are reconciled with dormant units. Dormant bodies continue bleeding. Outside
terrain is compressed, and revisiting restores damage and contents. World coordinates are
unbounded, but memory, saved history and detailed simulation are finite: a longer explored
campaign needs more storage. The game does not simulate an infinite number of individual
soldiers every second.

## Destinations and travel

Known workshop, HQ, port and airfield destinations are generated and validated before an
assignment points to them. A service destination keeps its world coordinate and identity.
A destroyed or captured post, or unavailable staff, produces a lost-destination message;
the same assignment cannot quietly move to another, farther post. Selecting a fresh service
visit in X explicitly requests a new assignment. Headquarters briefings use actual staff.

F7, or the **Go to objective** button below the orders, repeats normal order actions. Walking,
vehicle control, turning, loading, waits and their costs use the same simulation as manual
play. There are no position jumps, fabricated arrivals or skipped world turns. Contact,
wounds, suppression, immediate danger, a combat instruction or a menu stops automation.
Any key or click cancels. A still-hidden threat remains dangerous. `A` retains the separate
full soldier AI mode, including combat decisions.

Mission completion uses physical evidence. Breakout and rear-guard groups must reach the fixed,
staffed rally post with their surviving members accounted for; crossing a generation boundary
alone does nothing. Encircled starts place the group inside the field with actual blocking units.
Patrol reports need observed enemy positions, sniper tasks count the specified kinds of targets,
and holding orders count time actually on the assigned ground. Unloaded or missing targets are
not presumed destroyed. Recovered drop supplies remain real inventory or ground items. Convoy
escorts need arriving merchantmen; cover watches and rescues require work at the assigned place.
Completion records service, while decorations require the separate witnessed-deeds review.

Digging deadlines include the estimated remaining labor, using the same skill, climate, tool
condition and action speed as actual digging. Active progress pauses the deadline. Combat,
incapacitation and higher-priority orders also pause ordinary duty deadlines and allow time to
resume afterward. An absent shovel is a supply problem, not refusal. The orders book explains
why a deadline is paused; a safely ignored, feasible order can still have consequences.

## Personnel, medicine and speech

A reviewed promotion can arrive by working radio, a nearby superior or a physical runner.
The promotion screen opens when the conscious player can respond. Q reopens rank, duty and
support choices anywhere. There is no required hours-long HQ wait or mandatory leadership
course. Reviewed service is banked; taking a commission is explicit. Supplies still come from
finite stocks, and an attached support unit must actually exist. See [rank notes](RANKS.md).

Medics search farther, remember recently observed casualties through obscuration, and prioritize
urgent reachable patients. Nearby helpers can take over from an overly distant responder.
Litter teams stabilize bleeding before lifting, and a radio request need not wait for total
safety. Helpers still move physically, need dressings, can be pinned or killed, and cannot
reverse fatal injuries.

Local speech retains the existing asynchronous synthesizer. Small cached NumPy transformations
add restrained variation in pace, pitch, tremor, breath and emphasis. Pain, fear and exhaustion
can affect delivery while radio filtering remains separate. This is an inexpensive improvement
to a neutral voice model, not the emotional range of an actor or an emotion-trained model.
No cloud service or new runtime dependency is required.

Audible dialogue also appears as readable captions, including with sound disabled. Visible
soldiers have map bubbles; crew, radio and unseen voices use a strip inside the map. Unseen
speakers do not reveal an identity or position. Reading time uses the screen clock, and actual
TTS playback restores or extends the caption. Pending audio retains its world coordinates when
the tactical buffer moves; distant chatter cannot displace the nearest audible voices.

## Verification

`tests/test_streaming.py` exercises coordinate changes, physical sector crossings, actor/save
identity, terrain damage, floors, destinations, shells, artillery, coarse transfers, ship and
hospital returns, spatial queries and rendering. `tests/test_field_experience.py` covers field
promotion choices/delivery, rank branches, real-time objective travel, casualty care and voice
processing. The existing game suite and UI fuzzer cover the other systems.

Validation on 12 October 2026: all 288 game tests passed. The headless interface fuzzer ran all
26 theatres without crashes, exercising 4,061 real inputs, 2,983 world turns and rendering.
The mission, order-compliance and speech-caption regressions cover the follow-up fixes. The
earlier streaming release also passed 38 service/navigation and command checks with `FOW_NO_NUMBA=1`.
Tests isolate entity-ID counters, which affect AI scheduling, so their seeds remain reproducible
regardless of test collection order.

Run `tools/benchmark_world.py` in a fresh process per radius, without concurrent tests, to measure
actual full world turns. Radius 0 is the old bounded-map comparison. `FOW_CODE_ROOT` can point
at an archived revision for a baseline. Initialization, mean/p95 turn cost, actor count, terrain
and peak memory are reported separately. Rendering speed and map regeneration are separate from
world-turn cost; larger presets are optional rather than a promise of identical performance.


### Measured radius costs

These measurements are from the initial moving-world release. The latest measurements, profiles
and estimates for a Rust core and GPU work are in [performance notes](PERFORMANCE.md).

A reproducible sample on an Apple M4 Pro with 48 GiB RAM, Python 3.12.11 and Numba enabled:
Bocage 1944, US forces, `large` density, seed 42. Each radius ran in its own process, with a
stationary player, five warm-up turns and 180 timed full world turns. The battle and its
casualties continued normally. These are simulation timings, not rendering FPS or guaranteed
performance for every theatre. The bounded row is the current code with streaming disabled.

| Radius (tiles) | People at start | Mean turn (ms) | p95 turn (ms) | Peak memory (MiB) |
|---|---:|---:|---:|---:|
| Bounded reference | 251 | 17.3 | 28.7 | 147 |
| 180 | 404 | 34.9 | 76.4 | 348 |
| 240 (default) | 539 | 49.9 | 110.2 | 436 |
| 360 | 1,170 | 112.9 | 252.9 | 668 |
| 480 | 1,866 | 207.3 | 476.2 | 1,476 |
| 640 | 2,965 | 368.3 | 1027.5 | 2,391 |

The 640-tile setting covers a nominal 2.56 km diameter and started with almost 3,000 people;
its slowest measured turn took 1.74 seconds. It is a heavy simulation setting. The default
240-tile radius covers a 960 m diameter; its slowest measured turn took 139 ms. Initialization
was 1.47 seconds at the default and 4.85 seconds at maximum, before warm-up. Detailed simulation
has a real cost: the default favors responsive play, while the larger settings make the tradeoff
explicit. Longer exploration also accumulates persistent world history.
