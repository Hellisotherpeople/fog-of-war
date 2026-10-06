# Controls

Every key and click in FOG OF WAR, screen by screen. In the game, **F1** or **?** opens the help:
sections down the left, the keys in bold on the right, and first of all **Right now**, the keys
for where you are this moment (your seat in a tank, your orders, what's beside you, the mode
you're in). Type **/** there to search every key and action. A blue line under your orders gives the keys for
whatever's beside you: a vehicle, a door, a wounded man, someone to talk to, or your seat in a tank.
You can turn it off in Options ("Key hints").

- [Everywhere](#everywhere)
- [On the battlefield](#on-the-battlefield)
- [Aiming, throwing, looking: cursor modes](#aiming-throwing-looking-cursor-modes)
- [The V list: everything around you](#the-v-list-everything-around-you)
- [The mouse on the battlefield](#the-mouse-on-the-battlefield)
- [Pop-up menus](#pop-up-menus)
- [The kit screen](#the-kit-screen)
- [Vehicles](#vehicles)
- [Command: O, C, R, Y](#command-o-c-r-y)
- [The war map (m)](#the-war-map-m)
- [The staff screen (G)](#the-staff-screen-g)
- [Bases](#bases)
- [Aboard ship](#aboard-ship)
- [The chart and the cockpit](#the-chart-and-the-cockpit)
- [Other screens](#other-screens)

## Everywhere

| key | |
|---|---|
| F2 | sprites / ASCII |
| F3 | sound on / off |
| F4 | font: DejaVu Sans Mono / the classic bitmap |

"Ctrl" below also means Cmd or Alt. The number row isn't used anywhere. The numpad works as
direction keys.

## On the battlefield

**Moving**

| key | |
|---|---|
| arrows, numpad, `h j k l y u b n` | move one step; End, PgUp and PgDn are diagonals too |
| Shift + direction, or `H J K L U N` | run until something happens (`Y` and `B` are shout and bandage, not moves) |
| `.` `s` numpad 5, numpad `.` | wait a second |
| `z` | wait a minute, watching |
| `Z` | the wait menu: ordinary waits stop for danger or new orders. **Pass time regardless of events...** runs for 15 minutes, 1, 6 or 12 hours, or a day, through combat, wounds, unconsciousness and orders. Every second is simulated as fast as your machine can manage. Any key cancels; death or succession ends the wait |
| `c` | crouch (again: stand) |
| `p` | prone (again: crouch) |
| `W` | pace: creep / walk / run / sprint |
| `q` | lean out of cover (then a direction); `q` again, or a step, pulls you back |
| `D` | dig in, with a shovel (any key stops) |
| `<` / `>` | on stairs: up a floor / down one (a church tower, a flat roof, a hayloft at the top); on a cellar trapdoor: `>` down into the cellar, `<` up again |
| `o` | shut an open door beside you (walk through a door to open it) |
| Enter | carry out your current order: walk there and do it (the panel says what Enter will do) |
| `T` | the orders book: issuer, authority, priority, deadline and consequences. Enter selects a supporting instruction; a deferred order cannot replace your higher orders |
| `E` | talk to whoever's beside you (a list if there are several; right-click a man for the same). Comrades: where he's from, how he's holding up, what he's seen (he points, and it's marked on your map), the latest rumour, a smoke, ammunition, water, covering fire, a trade. The wounded: where he's hit, keeping him going, his last wishes. Prisoners: name and unit, and - for a cigarette, or when he's frightened enough - where his guns are. |
| `A` | autopilot (on land): your soldier acts on his training and his orders, the same AI as every man on the field; `A` or Esc takes him back (looking, the map, the books and help still work meanwhile). Aboard ship or aircraft there's none: Enter gets on with your orders, `Z` lets the watch go by |
| F6 | optional real time: everyone moves on a shared clock, including while you stand still. F6 again returns to turn based time |
| `!` | safe mode off / on |
| `'` | ignore the dangers you can see now (safe mode won't stop you for them) |
| `X` | read the ground: red where there's no way through, amber where it's slow (for you, or the vehicle you're in); `X` again to stop |

Moving into things:
- **An enemy:** you fight hand to hand - the obvious blow for what's in your hands. Right-click an enemy
  beside you to choose the move (bayonet thrust, rifle butt, slash, knife, grab, disarm, shove; from
  behind and unseen, a silent knife or a strangle), each with the odds as you'd judge them. Locked
  together, moving into him fights on and moving away tries to tear free.
- **A friend:** you swap places.
- **A man at his post** (adjutant, clerk, cook...): you talk to him.
- **A window:** push twice to smash it out and climb through. It's heard.
- **Wire, with wirecutters:** you cut it.
- **The map edge:** you go on into the next sector. If your squad is fighting, you're warned once
  that leaving is desertion.

**Safe mode:** with the enemy in sight, or rounds coming in, a step stops with a warning. Step again
to go anyway.

**Real time:** off by default. Options > Play offers normal (one game second per real second),
deliberate (one per two, the default), and slow (one per four). The HUD shows the pace and whether
you're ready or still finishing an action. Movement, reloads, firing and wounds use their normal
simulation rules for everyone; repeated inputs cannot skip an action's remaining time, and standing
idle cannot bank extra moves. Menus and loss of window focus pause the clock; aiming and looking
across the field keep it running. Actions taken through a menu still charge their full time cost.
Walking and autopilot keep the selected pace; `z` and `Z` deliberately pass time quickly. Aircraft
and ships use the same clock; naval actions retain their usual ten-second cost.

**Order priority:** the scenario briefing governs the HUD, arrow and Enter. A squad leader can direct
you among the mission's objectives, or ask for immediate help beside you, without replacing it.
Conflicting errands are marked **Deferred** in `T`, with deadlines paused and no failure penalty
while higher duty prevents compliance. A newer received order can take precedence only if its issuer
has equal or greater authority. A headquarters recall names the issuer and the battlefield reason.
Return/exfiltration stages point home and authorize leaving the squad; missions with no known single
destination, such as observing enemy positions, do not display an unrelated attack arrow.

**Decorations:** the post-game report shows illustrated medals and ribbons alongside the award's
citation, date, place, supporting deeds and any posthumous status. Left/Right browse additional
awards. Citations also remain in the service record and memorial. Older saves still show their
decorations, with an explicit notice when their original citation was not recorded.

**Fighting and kit**

| key | |
|---|---|
| `f` or Tab | aim and fire: the cursor jumps to a target (see [cursor modes](#aiming-throwing-looking-cursor-modes)); an empty gun reloads instead |
| `F` | fire mode (single, burst, auto), or AP / HE when crewing a tank |
| `r` | reload; clear a jam; on a full gun, count the rounds |
| `t` | throw a grenade (several kinds: choose which) |
| `a` | use something: a medical item, a tool (binoculars, flare gun, wirecutters...), or place a charge beside you |
| `B` | patch up yourself or a wounded man beside you, carry him out, or put down the man you're carrying |
| `i` | the kit screen |
| `g` or `,` | pick up (a body here: search it); several things: choose |
| `d` | drop something |
| `w` | take up a weapon, or put away what you're holding |
| `S` | resupply at an ammunition dump or crate |
| `e` | get into a vehicle beside you, or man a gun ([vehicles](#vehicles)); aboard ship, use what's in front of you |
| `v` | fire your seat's machine gun in a vehicle |

**Looking, command, the view**

| key | |
|---|---|
| `x` or `;` | look: a cursor to move about; or just rest the mouse on something |
| `V` | everything around you in a list ([below](#the-v-list-everything-around-you)) |
| `m` | the war map |
| `@` | yourself: your body in detail; Tab for your skills, then your service record and chain of command |
| `P` | the message log |
| `O` | orders for the squad you lead |
| `C` | command: your chain of command, and every unit whose leader you outrank |
| `R` | the radio; an agent's wireless set: reports, supply drops, the BBC messages |
| `Y` | shout |
| `G` | the general staff (colonels and up) |
| `+` `=` / `-` | zoom in / out, toward the mouse |
| Ctrl + direction | pan the view |
| Home | the view back to you |
| F5 | the minimap (click it to look there) |
| F1 or `?` | help |
| Esc | the menu: resume, save and quit, help, options |

Any key or click stops a walk, a run, a wait, digging, or the hours going by.

## Aiming, throwing, looking: cursor modes

In all of them:
- **Moving the cursor:** direction keys move it one tile; Shift + direction or `HJKLUN` moves it five.
- **Confirming:** Enter, or `.` (except in look mode).
- **Esc** cancels. Home brings the view and the cursor back to you.
- **The view:** zoom, pan and F5 work as usual.
- **The mouse:** it moves the cursor. Left-click confirms at that tile. Right-click cancels and
  opens the context menu.
- **Help:** F1 or `?` opens it at the part for this mode.

| mode | keys |
|---|---|
| **aim & fire** (`f`, Tab) | Tab / Shift+Tab next / previous target; `f`, `t`, `.` or Enter fire; `a` aim longer (snap > aimed > careful > precise); `A` aim all the way, then fire |
| **throw** (`t`) | `t`, `f` or Enter throw; `c` cook the grenade (0, 1, 2, 3 seconds) |
| **look** (`x`) | Enter: walk there (finding a way, as a click does); `x`, `;` or Esc done (the view stays where you looked) |
| **order** (from `O` or `C`) | pick the spot, Enter |
| **fire mission** (`R`) | pick the target, Enter |
| **flare** (a flare gun, `a`) | pick where, Enter |
| **lean out** (`q`), **place a charge** (`a`) | a direction key picks the tile beside you, at once |

## The V list: everything around you

`V` lists the men and vehicles you can see, the sounds you've just heard (placed where you think
they came from), and whatever's lying in sight. Everything is nearest first, over the right-hand
panel.

| key | |
|---|---|
| up / down (`k` / `j`) | pick one; the view goes to it (Shift: five at a time; PgUp / PgDn ten) |
| Tab, left / right (`h` / `l`) | soldiers / items |
| `f` | fire at the enemy picked |
| Enter | fire at an enemy; walk to a friend; walk to an item and pick it up; look toward a sound |
| `x` or `;` | look at it |
| `b` | raise or lower your binoculars (they tell an MG gunner from a rifleman at a distance) |
| Esc, `V` or `q` | close |

## The mouse on the battlefield

| | |
|---|---|
| hover | a tooltip on whatever's there (a friendly vehicle: what it needs, and the keys) |
| left-click | walk there, seen or unseen: the route is planned on what you know, trying ground you haven't seen, and planned again as you see more (a hedge where you hoped for a gap: round it); the tile beside you: step there (or fight, or talk); off the map: to the edge |
| right-click | the context menu: everything you can do with that tile, man or vehicle |
| middle-drag | pan |
| wheel | zoom toward the mouse; over the message log, scroll it |
| Shift + wheel, two fingers sideways | pan |
| click the minimap | look there |

Edge scrolling (the mouse at the edge scrolls the view) is off by default: Options.

The right-click menu, depending on what's there:
- **Always:** Look, Go there (on ground you haven't seen too: "find a way").
- **A spot or an enemy:** Fire at it, Throw a grenade there, Call artillery on it, Fire a flare over it.
- **If you lead a squad:** Order the squad there, Order an assault on it.
- **A friend beside you:** give him ammunition for his gun, a field dressing, a grenade, a cigarette;
  patch him up if he's hurt; his chain of command.
- **A man at his post:** talk to him, trade with the quartermaster, report to intelligence.
- **An enemy who's surrendered, or a wounded one:** take him prisoner; your prisoner (search, send
  back, hand on); patch him up.
- **A vehicle:** get in, or climb onto the hull and ride; get out or jump down; help fix a thrown
  track; hand up the shells you're carrying; take a crate of shells off an ammunition truck.
- **Water near a shore with the fleet offshore:** signal a boat to take you out.
- **Beside you:** lean out this way.

Your own men and vehicles don't get the shooting options, and `f` won't fire on them either ("That's one of
ours!") - though a burst, a grenade or a shell doesn't care whose men are in the way.

## Pop-up menus

| key | |
|---|---|
| up / down | move (greyed lines are skipped: the reason is in brackets) |
| Enter or Space | choose |
| the letter beside a line | choose it at once |
| Esc | close |

With the mouse: hover to pick, click to choose, click outside to close, and the wheel moves.

## The kit screen

`i` opens it. Your webbing and packs are grids, Tarkov-style. On the right are the ground and any
bodies within reach.

| key | |
|---|---|
| arrows, numpad | move the cursor |
| Enter or Space | pick up / put down; on a tab, switch to it |
| `r` | rotate what you're holding |
| Esc | put back what you're holding; otherwise close |
| Tab | between your kit and the other side (the ground, a body) |
| `[` / `]` | the previous / next pile or body |
| PgUp / PgDn | page the side you're on |
| `e` | use, equip, wield or wear (on the other side: take it) |
| `l` / `u` | load / unload |
| `c` | count the rounds |
| `d` | drop |
| `q` | move it across to the other side |
| `x` | look it over |
| `i` | close |

With the mouse: drag and drop. Right-click an item for everything you can do with it: take it,
take it in hand, reload, unload, check or count the rounds, fill a magazine from loose rounds,
empty it, use, wear, move, drop, look it over. Click a tab to switch to that pile or body. Click
outside to close.

## Vehicles

**Getting in and out**
- **`e` beside a vehicle gets you in.** What that means depends on the vehicle and on you:
  - A **seat**, if it has seats: a half-track, a truck.
  - A **crew position**, if you're a tanker, or it's empty or abandoned. Captured vehicles too;
    paint your markings on or your own side may shoot at it.
  - Otherwise a **handhold on a tank's engine deck**, with up to five others. Riders are fast and
    exposed, and can't fire from up there.
  - With several vehicles beside you, choose which.
- **`e` inside** opens the vehicle menu:
  - get out, or jump down;
  - open or shut your hatch (the commander's seat, or the gunner's in a two-man vehicle): head out, you
    see much further and can be shot; buttoned up, you see through the periscopes;
  - take an empty seat, or swap seats;
  - paint your markings on a captured one;
  - from the commander's seat: *crew hold fire* / *fire at will*, *cease fire on that target*,
    *gunner, traverse to the front*.
- Right-click a vehicle for the rest (see [the mouse](#the-mouse-on-the-battlefield)).

**Your seat** decides what you see as well as what you do. The commander sees all round: furthest
with his head out, less through the periscopes. The gunner sees only down his sight, a narrow
magnified cone where the gun points. The driver and bow gunner see forward through the visor and
the ball mount. Up in a vehicle you see over crops, undergrowth and garden hedges, and the side
panel lists your own vehicle's damage. Seats and their keys (the blue hint line shows yours):

| seat | keys |
|---|---|
| driver | direction keys drive; off the map edge, on into the next sector |
| gunner | `f` fires the main gun; `F` picks the round (AP / HE); direction keys traverse the turret (by hand, slowly, if the power's gone; not at all if it's jammed); `v` the coax |
| loader | `r` hurries the next round; `F` changes the round |
| machine gunner | `v` fires your gun (a bow gun points where the hull points) |
| commander | direction keys order the driver; `f` and `v` give the gunners a target; `e` for crew orders |
| passenger | `e` to get out, or take an empty seat |
| rider on the hull | `e` to jump down |

**Keeping them going**
- **Repairs:**
  - A thrown track is half an hour's work for four men. The crew does it, faster with help.
  - A dead engine or a damaged gun needs fitters: the motor pool's, or the two on an ammunition truck.
  - Crews only climb out when nobody's shooting at them.
- **Helping:**
  - Right-click the vehicle: *Help fix*, and time passes while you work (any key stops).
  - Idle infantry nearby help on their own.
  - `O` > *Tasks* > *Give the crew a hand* sends your squad.
- **Shells:**
  - Right-click an ammunition truck: *Take a crate*.
  - Carry the crate to the tank, and right-click the tank: *Hand up the shells*.
  - `R` > *Request an ammunition truck* brings one up (once every 20 minutes).
- **Seeing what one needs:** hover over a friendly vehicle. The tooltip says what it needs and how
  long the work has left.

`e` beside a parked aircraft on your own airfield: take off.

## Fire missions: the gun line and the mortar platoon

On a battery's gun (the *gun line*, as an artilleryman) or with a tube in a battalion's mortar
platoon, missions come down from the battery's command post or the platoon sergeant. Your orders
show the shell, charge, azimuth and elevation (in mils), and how many rounds your gun has to fire.

| key | |
|---|---|
| Enter | lay the gun on the data and fire (or drop a bomb down the tube) |
| `f` | the same, when there's nothing in sight to shoot at directly (otherwise `f` aims as usual) |

The first round takes laying; after that, a touch on the handwheels. The loader has to reload
between rounds. The observer's first correction comes from where your rounds really fell, and at
the end he reports what the mission did. If you don't fire, the section chief (or the platoon
sergeant) fires your rounds himself, and it counts against you.

## Command: O, C, R, Y

- **`O`** gives orders to the squad you lead (if you don't lead one, `O` opens `C`). The orders:
  - movement: Follow me!, Hold here, Advance to..., Assault..., Flank..., Suppress..., Dig in,
    Ambush, Fall back!;
  - fire: fire at will / return fire only / hold your fire;
  - *Give the crew a hand*, when a friendly vehicle close by needs a track or shells;
  - *Command other units...*.

  Orders ending in "..." offer a list of places: the next objective first, then the enemy positions
  your side knows of (a machine gun, an anti-tank gun, a group of men, with how long ago they were
  seen), then the other objectives. Enter takes the first. "Pick a spot on the map..." gives you the
  cursor, and Tab there steps through the same places.
- **Tasks...** (in `O`, and in `C` for any unit): scavenge the dead and the dumps for ammunition,
  for dressings and morphine, for grenades and weapons, or for papers and maps (brought to you);
  carry the wounded back to the aid post; search the men who've surrendered and march them back;
  give the tank crews a hand. Each line says how much there is to do near them, and greyed ones
  have nothing. The men go when no enemy is close, stop to fight when one is, and the leader
  reports what they found. "Stop what you're doing" calls them back.
- **`C`** shows your chain of command, and every friendly unit whose leader you outrank. Pick one
  for its orders:
  - movement: move, attack, assault, flank, suppress, defend, hold, dig in, ambush, come to me,
    regroup, fall back, mount up / dismount;
  - resupply, the rules of engagement, *Report!*, *Carry on*;
  - take them under your command.

  Esc goes back to the list. Picking a distant formation opens the staff screen. Targeted orders offer
  the same list of places as `O`, and Tasks... goes by voice, signal, radio or runner like any other.
- **`R`** is the radio, if you carry one, you're in a tank that has one, or a radioman is near. Fire
  missions go to a real battery that can reach and is free; the popup says how many are in range and
  ready. With none free, the answer is "negative".
  - fire mission (HE), smoke screen;
  - air support (officers);
  - an ammunition truck (from a vehicle, as a tanker, or as an officer);
  - a situation report;
  - medical evacuation, when you're badly hit and out of the enemy's sight and fire (a private
    next to a radioman can ask him for this one).
- **`Y`** is a shout: Medic!, Need ammunition!, Grenade!, Covering fire!, *Hands up!* (with an enemy close), or
  surrender.

Orders travel by voice, hand signal, radio, relay or runner, and take time to arrive.

## The war map (m)

| key | |
|---|---|
| direction keys | move the cursor a sector (Shift, `HJKLUN`: five) |
| Home or `@` | back to your sector |
| `z` | wide view / detail |
| click a sector | select it |
| Esc, Enter, `m`, `q`, or a click off the map | close |

In command of sectors (colonels and up):

| key | |
|---|---|
| `a` | attack a neighbouring sector (pick it, Enter; Esc cancels) |
| `r` | move reserves |
| `d` | dig in and hold |
| `p` | artillery priority |
| `f` | air priority (generals: a division or more) |
| `x` | cancel orders here |
| `o` | the staff screen |

## The staff screen (G)

Colonels and up. You can also open it with `o` on the war map.

| key | |
|---|---|
| up / down | pick a formation |
| `a` | attack (pick the target, Enter; Esc cancels) |
| `m` | move |
| `c` | commit the reserve |
| `v` | go and see: out to the jump-off line, or into the fighting |
| `h` | hold / dig in |
| `r` | into reserve |
| `w` | wait at headquarters: ten minutes, half an hour, an hour, until something happens |
| Esc, `G` or `q` | close |

The numbers on it are real: what's listed is what's on the ground.

## Bases

Behind the line, walk into the men at their posts to talk, or right-click them. Everything they
offer is a pop-up menu.
- **Adjutant:** orders, reporting in, passes to the rear.
- **Clerk:** pay, mail, your record.
- **Military police:** directions, or arrest.
- **Quartermaster:** trades.
- **Armourer:** cleans your weapon, gives out ammunition, swaps captured arms.
- **Cook:** a hot meal, rations.
- **Chaplain** or **political officer**.
- **Surgeon.**
- **Motor sergeant:** signs out a vehicle, or gives you a supply run (a truck of shells to take to
  the tanks).
- **Air operations:** flying orders.
- **Port director:** a ship, and the liberty boat.

Their orders show in your orders, and Enter gets on with them, even across sectors.

## Aboard ship

| key | |
|---|---|
| `<` / `>` | up / down a ladder (or `e` on it) |
| Enter | your job: to your station, the ammunition, a fire, sickbay |
| `Z` | the wait menu, including **Pass time regardless of events...**; **Ship's routine: until needed** is available when quiet (`z` also follows the quiet ship's routine) |
| `e` | whatever's in front of you (below) |

What `e` does, by what you're facing:
- **A bunk:** turn in.
- **A ready locker:** take a load of ammunition. **An AA or gun mount:** feed it, or man it (then
  `f` picks an aircraft).
- **The repair locker:** a hose or shoring. **A fire or a leak:** fight it.
- **A life ring:** take it, or throw it to a man overboard.
- **The rail:** in port, off watch, the liberty boat ashore; at sea, over the side.
- **The helm, the chart table or the periscope:** the chart view (below). Officers get the
  bridge; everyone else, the plot.

The same moving, looking and kit keys work aboard as on land. Be back from liberty by 0500: when
she sails, she sails without you.

## The chart and the cockpit

At a ship's helm or plot, or a bomber's station, the view changes to the chart. These keys work
there (`?` shows them too):

| key | |
|---|---|
| Esc, `e` or `q` | step back onto the deck (at a station aboard) |
| `?` | help |
| `m` | the war map |
| `t` | next target |
| `z` | fly on / steam on until something happens |
| `+` `=` / `-` | zoom |

**Flying** (each key is a second)

| key | |
|---|---|
| left / right, `a` / `d` | turn (Shift + arrow: hard turn, which bleeds speed) |
| up / `w`, down / `s` | climb, dive |
| Space or `.` | straight and level |
| `[` / `]` | throttle |
| `f` | the guns along your nose |
| `b` | bombs away / drop the torpedo |
| `h` | turn for home |
| Tab | the next crew station (bombers: pilot, bombardier, the gunners) |
| `e` | bail out (above 120 m) |

At the bombsight: left / right correct the aim, `b` releases, Space waits. At a gun: `f` fires,
Space waits.

**At sea** (each key is ten seconds)

| key | |
|---|---|
| left / right | helm fifteen degrees |
| up / down | ring for more or less speed |
| `f` | main battery salvo (or the shore bombardment); at the AA gun, the nearest aircraft |
| `g` | torpedoes |
| `c` | depth charges |
| `d` | dive / periscope / surface (submarines) |
| `l` | launch an air strike (carriers) |
| `o` | signal your force (captains and admirals) |
| Tab | bridge / main battery / AA gun / damage control |
| Space or `.` | wait ten seconds |

At damage control, `f` or Space fights the fire or the flooding. At the plot (if you're not an
officer), you watch: `t`, zoom, Space and `z` work, and the orders aren't yours to give. Adrift on
a raft or under a parachute, Space or `.` lets time pass.

The force signalling menu (`o`) can ask an accompanying oiler or repair ship to stop. Steer
within 300 metres at six knots or less to transfer its finite fuel or repair stores. Rough seas
prevent transfers. Another fleet order releases the support ship.

## Weather, civilians and supplies

In `V` → Items, **green [P]** means ammunition or magazines compatible with your primary,
**blue [S]** your secondary or holstered weapon, and **violet [P/S]** both. Empty compatible
magazines count. Mixed piles show a compatible item first; live explosives retain their red warning.

Rain and snow accumulate: mud, flooded trenches and drifts slow movement after a front passes.
Wind, visibility and sea state affect spotting, hearing, shooting, flying, sailing and deliveries.
Wear a rain cape; use a blanket while resting; get under a roof to dry out. Storms have rain,
wind and thunder audio, muffled by shelter.

Further behind either army are inhabited towns, food warehouses, workshops, hospitals,
power stations and railway goods yards. Undamaged facilities survive capture. Civilians
flee gunfire from either side and can be caught in it. Use `E` beside one to talk, share supplies,
treat wounds or ask them to follow you to an aid post or hospital.

Quartermasters show finite stocks of ammunition, fuel, food, medical supplies and parts.
Road connections, convoys, aircraft deliveries and intact facilities sustain them; isolation
and destroyed stores deplete them. Ammunition draws, treatment and repairs consume stock.
Use antiseptic for infection, splints for injured limbs, a tool roll plus spare parts beside a
damaged vehicle, and a fuel can beside a vehicle with a low tank. Fitters are still needed for
skilled repairs. Hunger, thirst and infected wounds slow recovery.

Intelligence officers offer **Counterintelligence reports and security patrols**. An intercept
frequency log opens the same menu when applied. Patrols investigate coarse witness reports and
wireless bearings, check papers and can detain enemy saboteurs. Local alerts and circulated
identities make an agent's papers less convincing.

**Air supply** is available among bomber flying scenarios/orders where a transport is available.
Use `b` at the dropping zone, within 800 metres, at 80–600 metres altitude and below 300 km/h.
The load comes from the departure sector's stores; wind and visibility affect how much is recovered.

## Other screens

| screen | keys |
|---|---|
| main menu and lists | up / down, Enter or Space, the letter beside a line; Esc back (on the main menu, Esc quits) |
| new game | up / down (or Tab) the rows, left / right change a value, Enter open or start, Esc back; on the name row type it (Backspace deletes) |
| briefing | Enter, Space, Esc or a click to start; `?` help |
| options | up / down, left / right change, Enter or Space toggle; the mouse: click raises a value, right-click lowers it |
| the Esc menu | up / down, Enter; Esc resumes |
| yourself (`@`) | Tab or left / right: body / skills / service record (Shift+Tab back); on the record, up / down / PgUp / PgDn scroll; Esc closes |
| help | up / down (or Tab, or a click) the sections; a letter jumps to the next section starting with it; PgUp / PgDn or the wheel scroll; `/` search (type, Enter keeps it, Esc clears); Esc, `?` or `q` close |
| the log, chain of command | up / down, PgUp / PgDn, the wheel; Esc, Enter or `q` close |
| prison camp | Enter or Space a day, `w` a week, `e` try to escape, Esc the menu |
| game over | Enter, Space, Esc or a click: back to the main menu |

## Papers checks, body searches and damaged kit

A sentry's papers check opens a conversation. Choose answers with the arrows/Enter or the listed
letters. **Review your legend and documents** opens scrollable notes; Esc returns to the same check.
Documents may disagree with your intended cover. Observant guards compare details, remember answers
and ask follow-up questions. Explaining a discrepancy, submitting to a search, offering money or breaking
away has consequences; ordinary answers take three seconds and a bag search takes eight.
The `@` cover page also carries your legend and the printed details of your documents.

Intelligence mission orders in `T`, the direction marker and Enter navigation include the briefing's
search area or lead. **Last reported area** means search around that point, not that the target is standing
on it now. Photography advances between unphotographed installations; rescue/exfiltration points home.

`V` → Items includes visible weapons and equipment on bodies, with the same ammo compatibility colours.
Select a body item and Enter to approach its inventory. In the inventory, **s** searches pockets and
opens the closed pack; this takes six seconds. Obvious worn kit and webbing need no full search first.
The footer lists every key; `Tab` changes sides, `[`/`]` changes sources, and `PgUp`/`PgDn` changes sections.

Inspect an item with **x** to see its condition and how damage affects it. Blasts can scatter equipment,
fire can destroy supplies, and torn bags lose usable storage. The armourer repairs damaged equipment
using parts and time. Cleaning a weapon does not replace broken parts; destroyed items need replacement.
