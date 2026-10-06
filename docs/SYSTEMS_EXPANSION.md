# Weather and the home front

The [controls guide](CONTROLS.md#weather-civilians-and-supplies) explains how to use these systems.

## Weather

Clear skies, overcast, rain, storms, snow, blizzards, fog and sandstorms follow the theatre's
climate. Fronts vary in intensity and wind. Precipitation accumulates as wet ground and snow;
drying and thawing take time. Terrain changes survive sector visits and saves, and never restore
a tile that has since been destroyed or built over.

Conditions influence visibility, hearing, shot dispersion, temperature and wet clothes. Wind
drifts aircraft, storms cause turbulence, poor visibility restricts flying operations, and rough
seas reduce speed, gunnery and sonar effectiveness. Bad going slows supply traffic. Rain and snow
are visible in both renderers; rain, wind and thunder have audio, attenuated by shelter.

## Civilians and rear districts

Initial distance from the fighting controls damage and prosperity on both sides. At greater
depths, districts acquire more intact workshops, food warehouses, hospitals, power stations
and goods yards. Facilities occupy physical buildings with destructible stores; dense towns
reuse existing buildings. Bombing and ground destruction remove their supply benefits. Capturing
an intact facility changes its ownership and transfers part of the district's remaining stocks.

Residents have bodies, wounds, clothing, homes and occupations. They seek shelter from gunfire
from either army, can follow the player to medical care, and remember deaths and relief through
district goodwill. They are excluded from military targeting and kill credit, but remain
vulnerable to crossfire and explosions. Residents and their casualties persist across visits.

## Counterintelligence

District security maintains alert levels, witness reports, coarse radio bearings and circulated
cover identities. MPs and intelligence personnel guard rear facilities and investigate fresh
reports. Witnesses need line of sight; papers checks require proximity and line of sight.
Language, cover documents and local alert affect the chance of passing.

The other side can infiltrate a real saboteur in civilian cover. The saboteur travels toward an
installation, carries papers and sabotage stores, and can damage supply infrastructure unless
located and detained. An innocent resident does not become a spy because their papers are checked.
The player can review reports and dispatch patrols through intelligence officers or an intercept log.

## Supply and recovery

Each side has finite ammunition, fuel, food, medical and parts stocks in each district. These are
abstract supply units. A connected rear route imports supplies; an encircled depot cannot manufacture
imports. Working factories produce parts, food warehouses sustain food stocks, and goods yards
increase transport capacity. Road convoys carry deducted loads to adjacent friendly districts;
destroying the load prevents its delivery. Transport aircraft carry deducted loads from their base.

Ammunition draws, vehicle rearming, surgery, supplied convalescence, refuelling and repair work
consume stores. Hunger, thirst and infection matter over hours; medical care and proper provisions
improve recovery. A rain cape, blanket, antiseptic, splint, tool roll, spare parts, gun oil and fuel
can provide field options. These use the existing inventory/apply interactions and take time.

Oil and repair ships hold finite onboard stores. Transfers require nearby friendly ships moving
at six knots or less in moderate seas. A captain can signal a support ship to stop, then steer
alongside. Existing shipboard damage control and port refits remain available.

## New equipment

| Aircraft | Role |
|---|---|
| A-20 Havoc, A-26 Invader | Attack |
| B-26 Marauder, Ju 188 | Bombing |
| P-61 Black Widow | Radar-equipped night fighter |
| C-47 Skytrain, C-46 Commando | Transport and supply drops |
| PBY Catalina | Maritime patrol bomber |
| Beaufort, Barracuda, B6N Tenzan | Torpedo bombing |
| D4Y Suisei | Dive bombing |

| Ships | Role |
|---|---|
| Cannon, Evarts, River, Matsu | Escort and anti-submarine work |
| Independence, Sangamon | Light/escort carrier operations |
| Cimarron | Fuel replenishment |
| Vestal | Repairs alongside |

Equipment uses nationality and date availability and the game's existing combat and interior
systems. Performance and stores are gameplay abstractions. Historical references include the
[USAF aircraft catalogue](https://www.afhistory.af.mil/FAQs/Fact-Sheets/Article/459025/army-air-forces-aircraft-a-definitive-moment/),
the Navy's [Cimarron history](https://www.history.navy.mil/research/histories/ship-histories/danfs/c/cimarron-ii.html)
and [Sangamon history](https://www.history.navy.mil/research/histories/ship-histories/danfs/s/sangamon-ii.html).

The new items are the rain cape, blanket, drinking-water tin, large field dressing, saline,
antiseptic, splint, tool roll, repair spares, fuel can, gun oil, movement permit and intercept log.
The eleven new tiles cover wet/snowy ground, stores, hospital beds, markets, checkpoints and shelters.

## Save compatibility and time

New terrain IDs are appended. Weather, ground accumulation, civilian residents, district security
and supply stores are saved; missing state in older saves initializes when first used. Previously
generated districts retain their existing map layouts.

The event-ignoring wait still simulates every second. It batches rendering instead of skipping
combat, needs, orders or the strategic war. It can run through unconsciousness but stops on death,
succession, a change of game screen, or player cancellation. Its speed depends on the active simulation.

## Identity, physical equipment and search leads

Checkpoint conversations replace the automatic player papers roll. A cover includes a persistent legend;
each physical document can contain a printing defect or an inconsistent field. Review the legend and the
actual papers, answer questions, and explain discrepancies. Sentries vary in observation, language skill
and diligence; security specialists ask more questions and consult local records. A weak sentry may do
little beyond checking a name. Reopening a dialogue does not reroll its papers, evidence or observer.
Answers take simulation time. A failed explanation can lead to a bag search, a demand for surrender or
an alarm if the player refuses. Existing captivity rules still apply. Forced waits keep running; a guard
will eventually raise the alarm if ignored. Counterintelligence interviews record questions, contradictions,
physical searches and evidence before offering detention.

Intelligence orders retain briefing leads: the airman's or target's last reported area, reconnaissance
installations, suggested wireless concealment, dropping/collection zones and the return route. Search
markers identify an area with an approximate radius. They do not follow hidden people as they move.

Fresh sectors stock armoury racks, depot stores, service areas, ammunition positions and sheltered reserve
caches. Quiet empty ground has no random military litter. Household belongings cluster around furniture;
fought-over ground can hold kit at abandoned firing positions, wrecks and shell holes. Stocks are generated
once with a sector and persist when it is revisited. Already saved sectors keep their existing loot.

`V` lists weapons, worn kit and accessible webbing on visible bodies, retaining primary/secondary ammo
colours. At a distance it shows less detail. Closed packs and pockets become known after a six-second
search in the inventory (`s`). Enter on a body item approaches that body's kit. The inventory footer shows
all controls on separate lines rather than truncating the action list.

Condition is saved on individual items; old items default to intact. Blasts damage exposed kit and scatter
loose equipment, with walls blocking both blast and movement. Bags protect contents, lose storage space
as they tear and spill items that no longer fit. Fire and hits on carried equipment can damage it too.
Damaged weapons disperse shots more and jam more; magazines and cartridges affect reliability; helmets,
clothes, medical supplies, blades, digging tools and wireless sets lose relevant performance. Damaged
fuses may fail. Zero condition makes equipment unusable; durable wreckage can remain as scrap. Repairable
survivors can be restored by an armourer using finite parts and workshop time; destroyed items need replacement.

Small-arms terrain impacts use remaining energy, penetration, surface angle and material resistance.
Glass loses much less energy than a wall; repeated barriers consume the remaining energy. Hard surfaces
can deflect shallow hits into a real, weaker projectile path, including friendly-fire risk. Earth, sandbags
and vegetation do not behave like steel. Ricochet recursion is bounded. These are game-scale material
rules, not an engineering-grade ballistics model.

Survivability proposals are recorded separately in `docs/SURVIVABILITY_DESIGN.md`; no health or accuracy
bonus was added to extend a player's life.

## Soldiers helping soldiers

Nearby leaders can send one available member of their own squad to give first aid or carry compatible
ammunition to an observed friendly, including someone in another squad. Leaders remember effective fire
they personally witnessed for several minutes and give those fighters more priority when needs compete.
Life-threatening casualties take priority over routine wounds and ammunition regardless of reputation.
Basic buddy aid no longer involves a random refusal for a player in ordinary good standing.

Runners use their actual dressings and ammunition, keep their own last two spare magazines or packets, and
spend normal movement and treatment time. Empty or broken magazines are not donations. If your inventory
is full, delivered ammunition is placed at your feet. You still need to reload. The leader announces who
is coming and why; visible helpers are labelled in `V`. `Y` > **Need ammunition!** provides a nearby
leader with a cue when you're farther away than he could inspect your pouches.

Assignments do not replace squad orders or take control of the player. Helpers respond to immediate
danger, respect withdrawal and assault manoeuvres, and can lose sight of a moving recipient. They go to
the last observed position, abandon unreachable errands, and stop when help is no longer needed. Leaders
avoid sending several helpers for the same need. These rules apply to both sides and save with the soldiers.

## Visible vehicle occupants and gun crews

Open half-tracks, carriers, jeeps and landing craft show the soldiers actually aboard. Artillery,
anti-tank guns and AA positions show their remaining crews at the sights, breech and ammunition
positions, with loading poses while reloading. Open fighting compartments, tank-deck riders and
unbuttoned tank commanders are visible too. Covered truck beds and enclosed armour conceal their occupants.

Figures follow boarding, dismounting, casualties, crew abandonment and gun traverse. Named crewmen,
including the player, replace an existing crew figure and wear their own headgear; the display does
not add soldiers to the simulation. Gun carriages stay fixed while the barrel traverses. Fog of war
clips occupant sprites to visible tiles, and smoke draws over them. Text mode marks occupied areas
with `@` where there is room while retaining the vehicle's type letter.
