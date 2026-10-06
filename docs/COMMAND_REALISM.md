# Command, engineering and information

The ground campaign separates what happened from what headquarters knows. These systems apply to both armies; the player also has personnel records, service destinations and a carried map.

## Using the systems

- **New game → Vehicle → Position:** select an exact ground vehicle or emplaced gun and a modeled crew station, or a passenger seat where available. Lists use the battle date. Normal issue automatically chooses a listed operating army and its side; a compatible chosen army is preserved. A Tiger II therefore selects Germany / Axis, including when the battle is random. To create an American crew in a German tank, explicitly select **Vehicle use → Captured equipment**, then your nation and model. Foreign captured starts use the existing unfamiliar-controls and recognition rules. Changing the model clears an incompatible seat. The assignment takes precedence over random solo, evasion and prisoner openings. Tank-crew roles also receive a tank when the random battlefield contains none. Aircraft, ships and water-only landing craft still use their existing service/scenario setup.
- **C → unit or formation:** appoint an acting commander, transfer subordinate units between commands, or give a standing mission. Appointments change command responsibility without giving out ranks. Rank, national command authority and communications are checked again when the instruction arrives.
- **Standing mission:** seize and consolidate, defend, screen/report, or reserve/support. Choose a maneuver radius and a loss threshold. Subordinates can reorganize, fetch ammunition locally, choose an approach, support a neighboring unit and dig in on arrival. Explicit orders remain in force until replaced or released. Men can still break under fire.
- **C → engineers → Engineer works:** select a project and its site. Eligible workers need tools, a clear site, finite materials and time. Basic cover can be built by equipped infantry; skilled works need engineers, Seabees or fitters. The work party carries materials from a nearby depot, workshop or stocked truck. Fighting, suppression, casualties, exhaustion and blocked sites interrupt work. Delivered material stays at the site; dead carriers do not deliver their loads.
- **C → Staff, supply and engineer works:** inspect local work parties, request a truck, and, at HQ, inspect stores and civilian ration provision.
- **T / Enter:** inspect and follow workshop instructions or a higher-headquarters conference order. Hull damage needs a workshop. Fitters can service components in a quiet location with physical spares, including damaged radios. Nearby friendlies can report a disabled tank even when its own set is out. Personal damaged kit can be serviced near a quartermaster, armourer or mechanic while parts last.
- **m / G:** use a dated map sheet and situation reports. Visit a friendly HQ to copy the latest received reports. A working HQ refreshes the sheet once a minute; that does not make the underlying reports instantaneous. Captured maps contain information from when their bearer received them.

## What changes the simulation

### Orders and national doctrine

The standing mission sits above a unit's immediate movement/fire order. Local sightings inform the leader only within voice distance or over a working net. A reserve needs nearby contact or connected radios to respond to another unit. National profiles supply terminology, preferred maneuver and the default latitude: US fire and maneuver; German Schwerpunkt/mission direction; Commonwealth fire and movement; Japanese envelopment; Soviet successive objectives; and generic fire/movement or local-initiative profiles for other armies. Heavy weapons supply fire; flanking profiles select the existing flank behavior.

These are deliberately small profiles, not a claim that every army used a single doctrine for the whole war. The Soviet, French, Italian and Finnish labels are descriptive translations, not quotations from authenticated national manuals. Profiles share much of the underlying squad AI. They are centralized in `fow/intent.py` for further battle/year-specific research.

Available HQ parties keep their officers and radios within reach of a senior commander when they can hear or contact him. Explicit player orders take precedence. Senior commanders who stop in a quiet area can cause nearby uncommitted engineers to establish a field command post. They need the same tools, supplies and working time as a player-directed work party. Rank does not conjure a building or personnel.

### Evidence and personnel

Practical skill improves from doing the job even without a witness. Official credit needs a surviving witness who saw the soldier and the action, or surviving fellow vehicle crew, and a communication route. A report is frozen when sent: a witness killed before transmission cannot send it; killing the witness afterward does not erase a report already sent.

Reports take time to process. Promotion needs reviewed evidence, time since the last promotion, a suitable vacancy and delivered personnel orders. Acting command and substantive rank are separate. Automatic kill-count rank jumps and captures erasing unrelated disciplinary penalties are removed. Decoration recommendations also wait for delivery. The character sheet explains the outstanding administrative requirement.

The one-day enlisted and seven-day officer minimums, five/thirty-minute report processing, and later review/delivery delays are **game parameters**, not historical promotion regulations. Witnesses and reporting parties outside the loaded battlefield, commissioning boards, documentary medical evidence and each country's entire personnel bureaucracy are not individually simulated. Existing quest/reputation systems remain abstractions.

### Construction, supply and the home front

Projects include foxholes, trenches, sandbags, wire, gun pits, concrete fighting positions, anti-tank obstacles and ditches, camouflage, road and bridge repairs, command/observation posts, supply and aid points, workshops, landing-strip and railhead works, food stores, generators, shelters and water points. Completion alters physical terrain and registers operating installations; destruction of a constructed installation's critical tile disables it.

Labor is measured in man-seconds. A basic foxhole takes approximately two man-hours before skill adjustments, rather than appearing after thirty seconds. Large infrastructure represents a local working/service area, with its strategic effect abstracted; the few runway tiles are not a literal full-length airstrip. Material “crates” are normalized supply units, including stores/equipment delivery, not identical hand-portable boxes. These costs are tuning values, not historical bills of materials.

Factories consume material and fuel. Their output depends on power, surviving local labor, damage and food provision. Civilian relief consumes finite food; disconnected food depots cannot create food. Ordinary troops need carried rations or access to a local distribution point. Supply trucks bring finite ammunition, spares and engineer stores. Fitters can repair a radio in the rear without repairing the hull in the field.

### Intelligence and artillery

On the loaded battlefield, radio sightings reach the shared command picture after a transmission delay. Reports preserve the observed coordinates and time; they do not follow hidden enemies or learn that an unseen enemy died. Both sides use this path. Strategic reports abstract distant friendly units and patrols, with a ten-minute friendly reporting delay and twenty-minute reconnaissance delay, estimates of enemy strength, and a dependency on supply/communication routes. Carried sheets retain older reports until copied at HQ.

Automatic exact retaliation against a firing battery is removed. A loaded battery can be located by an actual radio-equipped observer with recent visual contact, or by two occupied, separated observation posts after repeated firing. The visual path adds at least ninety seconds; surveyed sound ranging adds at least ten minutes and substantial position error. A single sound mark is not a surveyed grid reference. Off-map counterbattery requires prepared observation installations and supply. There must still be a usable gun/battery and ammunition to answer; a player's rank no longer halves response time.

The specified delays, baseline lengths and errors are simulation settings. Two posts are a simplified representation of a surveyed sound/flash-ranging organization, not a claim that two riflemen could reproduce a complete observation battalion. Previously scheduled or prepared barrages may still arrive quickly because they do not need a new target-location cycle.

## Historical grounding

These sources informed the mechanisms and terminology, rather than certifying every tuning value:

- [US War Department, FM 100-5, Operations (22 May 1941)](https://www.ibiblio.org/hyperwar/USA/ref/FM/FM100-5/index.html): command, task organization, initiative and flexible application of principles.
- [US War Department, TM-E 30-451, Handbook on German Military Forces, Chapter IV](https://www.ibiblio.org/hyperwar/Germany/HB/HB-4.html): subordinate responsibility, reconnaissance instructions, concentration and artillery observation. This is a wartime US assessment, not an original German regulation.
- [US War Department, TM-E 30-480, Handbook on Japanese Military Forces (1944)](https://www.ibiblio.org/hyperwar/Japan/IJA/HB/): wartime assessment of Japanese tactical methods, likewise an external assessment.
- [The Field Artillery Journal, September 1944](https://tradocfcoeccafcoepfwprod.blob.core.usgovcloudapi.net/fires-bulletin-archive/1944/SEP_1944/SEP_1944_FULL_EDITION.pdf): counterbattery intelligence from sound/flash ranging, photography, shell reports and observers.
- [US Navy Bureau of Yards and Docks, Building the Navy's Bases in World War II](https://www.ibiblio.org/hyperwar/USN/Building_Bases/index.html): the construction organizations, work and supporting resources behind naval bases.

## Verification and compatibility

`tests/test_command_realism.py` covers authority at delivery, actual reassignments, loss thresholds, witness survival, broken radios, stale reports, copied maps, material consumption, interrupted works, destroyed HQs, counterbattery observation and repair destinations. `tests/test_vehicle_start.py` covers exact model/seat starts, creator filtering, passenger behavior and save/load.

New records are ordinary saved dictionaries with defaults for older saves. Existing maps acquire new intelligence records on the next reporting cycle. Existing earned ranks and medals are retained; unsupported automatic counterbattery events from old saves are discarded. Returning to an older executable after saving new construction/personnel state is not supported.
