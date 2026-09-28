"""The in-game help, section by section (drawn by ui.HelpState; docs/CONTROLS.md is the long form).

A section is (title, rows).  A row is one of:
    ("k", "key|key", "what it does")     keys drawn as bold keycaps, the words beside them
    ("l", "label", "what it means")      the same, for something that isn't a key (a seat, a thing you walk into)
    {key} inside any text draws that key in bold
    ("h", "a subheading")
    ("t", "a line of plain explanation")
The "Right now" section is built by PlayState.help_now() from where you are.
"""
from __future__ import annotations

SECTIONS = [
    ("Essentials", [
        ("t", "The dozen keys to know first. Everything else is in the other sections - or type {/} to search."),
        ("k", "arrows|numpad|hjklyubn", "move; into an enemy: fight hand to hand"),
        ("k", "left-click", "walk there"),
        ("k", "Enter", "carry out your orders (the panel says what Enter will do)"),
        ("k", "c|p", "crouch / go prone - get down behind something that stops bullets"),
        ("k", "f|Tab", "aim and fire ({Tab} again: the next target; {f} again: fire)"),
        ("k", "r", "reload, or clear a jam"),
        ("k", "B", "patch up yourself or the wounded man beside you"),
        ("k", "Y", "shout: Medic! Grenade! - or surrender"),
        ("k", "e", "get into (or onto) a vehicle beside you, and out again"),
        ("k", "right-click", "everything you can do with that spot, man or vehicle"),
        ("k", "i", "your kit"),
        ("k", "V", "everything you can see and hear, in a list"),
        ("k", "x", "look (or just rest the mouse on something)"),
        ("k", ".|z", "wait a second / wait until something happens"),
        ("k", "?|F1", "this help;  {Esc}: the menu (save and quit, options)"),
    ]),
    ("Moving", [
        ("k", "arrows|numpad|hjklyubn", "one step; {End}, {PgUp} and {PgDn} are diagonals too"),
        ("k", "Shift+dir|HJKLUN", "run until something happens ({Y} and {B} are shout and bandage, not moves)"),
        ("k", "left-click", "walk to a spot; any key stops you"),
        ("k", ".|s|numpad 5", "wait a second"),
        ("k", "z|Z", "wait until something happens (up to a minute)"),
        ("k", "c", "crouch (again: stand)"),
        ("k", "p", "go prone (again: crouch)"),
        ("k", "W", "pace: creep / walk / run / sprint - creeping is all but silent; running spoils your aim"),
        ("k", "q", "lean out of cover, then a direction; {q} or a step pulls you back"),
        ("k", "D", "dig in (with a shovel; any key stops)"),
        ("k", "o", "shut an open door beside you (walk through a door to open it)"),
        ("k", "Enter", "carry out your current order: walk there and do it"),
        ("h", "Walking into things"),
        ("l", "enemy", "fight hand to hand"),
        ("l", "friend", "swap places;  a man at his post: talk to him"),
        ("l", "window", "push twice to smash it out and climb through (it's heard)"),
        ("l", "wire", "cut it, if you carry wirecutters"),
        ("l", "map edge", "on into the next stretch of ground - the world never ends"),
        ("h", "Safe mode"),
        ("t", "With the enemy in sight or rounds coming in, a step stops with a warning. Step again to go anyway."),
        ("k", "!", "safe mode off / on"),
        ("k", "'", "ignore the dangers you can see now"),
    ]),
    ("Fighting", [
        ("k", "f|Tab", "aim and fire: the cursor jumps to a target (an empty gun reloads instead)"),
        ("h", "While aiming"),
        ("k", "Tab|Shift+Tab", "next / previous target"),
        ("k", "f|t|.|Enter", "fire now"),
        ("k", "a", "aim longer: snap > aimed > careful > precise"),
        ("k", "A", "aim all the way, then fire"),
        ("k", "move keys", "move the cursor ({Shift}: five at a time)"),
        ("k", "left-click", "fire at that spot"),
        ("k", "Esc", "cancel"),
        ("t", "Aim takes time; moving, flinching or a new target loses it. Every shot kicks: fire again too soon"),
        ("t", "and you'll miss. Prone, a wall or a bipod steadies you."),
        ("h", "The rest"),
        ("k", "F", "fire mode (single / burst / auto), or AP / HE in a tank"),
        ("k", "r", "reload; clear a jam; on a full gun, count the rounds"),
        ("k", "t", "throw a grenade: pick the spot; {t}, {f} or {Enter} throws; {c} cooks it (0-3 s)"),
        ("k", "a", "use something: a medical item, a tool, or place a charge beside you"),
        ("k", "right-click", "fire at it, throw there, call artillery, fire a flare, order the squad there"),
    ]),
    ("Your kit", [
        ("k", "i", "the kit screen: your webbing and packs are grids; the ground and bodies within reach beside them"),
        ("k", "g|,", "pick up (a body here: search it)"),
        ("k", "d", "drop something"),
        ("k", "w", "take up a weapon, or put away what you're holding"),
        ("k", "B", "patch up yourself or a wounded man; carry him; put him down"),
        ("k", "S", "resupply at an ammunition dump or crate"),
        ("h", "In the kit screen"),
        ("k", "arrows", "move the cursor"),
        ("k", "Enter|Space", "pick up / put down (or drag with the mouse)"),
        ("k", "r", "rotate what you're holding"),
        ("k", "Tab", "your kit / the ground or the body"),
        ("k", "[|]", "the previous / next pile or body within reach"),
        ("k", "e", "use, equip, wield or wear"),
        ("k", "l|u", "load / unload"),
        ("k", "c", "count the rounds"),
        ("k", "d|q|x", "drop / move it across / look it over"),
        ("k", "right-click", "everything you can do with that item"),
        ("k", "i|Esc", "close ({Esc} first puts back what you're holding)"),
    ]),
    ("Vehicles", [
        ("k", "e", "beside a vehicle: get in - a seat, a crew position, or a handhold on a tank's hull"),
        ("k", "e", "inside: get out, change seats, open or shut your hatch, paint markings on a captured one"),
        ("k", "right-click", "get in or ride, help fix a thrown track, hand up shells, take a crate off a truck"),
        ("k", "hover", "what it needs, what's broken (the enemy's: only what shows from outside)"),
        ("h", "Your seat: what you do, and what you see"),
        ("l", "driver", "{move keys} drive; you see through the visor, forward"),
        ("l", "gunner", "{f} main gun, {F} the round, {move keys} traverse, {v} the coax; you see down the sight only"),
        ("l", "loader", "{r} hurries the next round, {F} changes it"),
        ("l", "bow gunner", "{v} fires your gun (it points where the hull points)"),
        ("l", "commander", "{move keys} order the driver; {f} and {v} give the gunners a target; {e} for crew orders and your hatch"),
        ("t", "The commander with his head out of the hatch sees furthest - and can be shot. Buttoned up, it's the"),
        ("t", "periscopes. Up in a vehicle you see over crops, undergrowth and garden hedges."),
        ("h", "Parts, not hit points"),
        ("t", "A broken track stops it moving, not shooting. A dead engine: the turret is cranked by hand. A jammed"),
        ("t", "turret: swing the hull to aim. Smashed sights: open sights. A dead radio: no calls. A crewman hit"),
        ("t", "leaves his seat empty until another climbs across. Crews fix tracks themselves; the rest needs fitters."),
        ("k", "O", "(leading a squad) give a tank crew a hand with a track or the shells"),
        ("k", "R", "request an ammunition truck"),
        ("k", "e", "beside a parked aircraft on your own airfield: take off"),
    ]),
    ("The guns", [
        ("t", "Every shell and aircraft comes from a real unit: named batteries at the artillery positions, a mortar"),
        ("t", "platoon with each battalion, warships off a landing beach, squadrons at their airfields."),
        ("k", "R", "radio: fire mission, smoke, air, an ammunition truck - the battery that answers must reach and have"),
        ("k", "", "rounds; if none can, the answer is no. The radio tells you how many are in range and ready."),
        ("t", "On your map you'll find their guns and tubes, and can silence them; off it you hear them from their"),
        ("t", "direction. Guns that fire draw counter-battery fire from the enemy's guns; mortars, when they're found"),
        ("t", "(harder, before the counter-mortar radars of 1944), counter-mortar fire from guns and mortars. Aircraft need an hour"),
        ("t", "between sorties, and flak brings them down."),
        ("h", "On a gun, or a tube in the mortar platoon"),
        ("k", "Enter", "a FIRE MISSION in your orders: lay on the charge, azimuth and elevation, and fire"),
        ("k", "f", "the same, when there's nothing in sight to shoot at directly"),
        ("t", "The observer corrects from where your rounds fell, and reports what the mission did. Don't fire,"),
        ("t", "and the section chief does it himself - and remembers."),
    ]),
    ("Command", [
        ("k", "O", "orders for the squad you lead: follow, hold, advance, assault, flank, suppress, dig in, ambush,"),
        ("k", "", "fall back, the rules of engagement, tasks (not leading one? {O} opens {C})"),
        ("t", "An order that needs a place offers a short list: the next objective first, then the enemy positions your"),
        ("t", "side knows of and the other objectives. {Enter} takes the first; or pick a spot on the map yourself, where"),
        ("t", "{Tab} steps through the same places."),
        ("h", "Tasks (in O and C)"),
        ("t", "Scavenge the dead and the dumps for ammunition, dressings and morphine, grenades and weapons, or"),
        ("t", "papers and maps (brought to you); carry the wounded back to the aid post; search the men who've"),
        ("t", "surrendered and march them back; give the tank crews a hand. Each says how much there is to do."),
        ("t", "The men go when no enemy is close, stop to fight when one is, and report what they found."),
        ("h", "The rest"),
        ("k", "C", "your chain of command, and every unit whose leader you outrank: pick one for its orders"),
        ("k", "R", "the radio (yours, a tank's, or a radioman beside you) - and, badly hit, out of the enemy's"),
        ("k", "", "sight and fire, stretcher-bearers: they come on foot, carry you back, and after weeks in"),
        ("k", "", "hospital you're back at the front (a lost limb, and you're sent home)"),
        ("k", "Y", "shout: Medic! Grenade! Covering fire! Hands up! - or surrender"),
        ("k", "G", "(colonel and up) the staff screen: {a} attack, {m} move, {c} reserve, {h} hold, {r} into reserve,"),
        ("k", "", "{v} go and see, {w} wait at headquarters"),
        ("k", "right-click", "a surrendered man: take him prisoner; again: search him, send him back"),
        ("t", "Orders travel by voice, hand signal, radio, relay or runner, and take time to arrive. The arrow at"),
        ("t", "the edge of the map, or the X on the ground, is where your orders send you."),
    ]),
    ("Looking around", [
        ("k", "x|;", "look: move the cursor; {Esc} done - or just rest the mouse on something"),
        ("k", "V", "everything around you in a list, nearest first: the men and vehicles you can see, the sounds"),
        ("k", "", "you've heard, what's lying in sight"),
        ("h", "In the V list"),
        ("k", "up|down", "pick one - the view goes to it ({Shift}: five; {PgUp} / {PgDn}: ten)"),
        ("k", "Tab|left|right", "soldiers / items"),
        ("k", "f|Enter", "fire at an enemy; go to a friend or a pile; look toward a sound"),
        ("k", "x|b", "look at it / raise your binoculars"),
        ("k", "Esc|V|q", "close"),
        ("h", "The rest"),
        ("k", "m", "the war map: {Home} or {@} back to you, {z} wide view; in command: {a} attack, {r} reserves, {d} dig in, {p} and {f} artillery or air priority, {x} cancel, {o} staff screen"),
        ("k", "@", "yourself: your body in detail; {Tab} for your service record and chain of command"),
        ("k", "P", "the message log"),
    ]),
    ("Screen & mouse", [
        ("k", "F2|F3|F4", "sprites or ASCII / sound on or off / the font (these work everywhere)"),
        ("k", "wheel|+|-", "zoom toward the mouse"),
        ("k", "middle-drag", "pan the view (or {Ctrl}+move keys, {Shift}+wheel, two fingers sideways)"),
        ("k", "Home", "the view back to you"),
        ("k", "F5", "the minimap - click it to look there"),
        ("k", "right-click", "everything you can do with that spot"),
        ("k", "hover", "a description of whatever's there"),
        ("k", "Esc", "the menu: Options has the sound mixer, key hints, safe mode, animation speed..."),
        ("t", "{Ctrl} also means {Cmd} or {Alt}. The number row isn't used anywhere."),
    ]),
    ("Menus & screens", [
        ("k", "up|down", "move in any pop-up menu (greyed lines can't be chosen: the reason is in brackets)"),
        ("k", "Enter|Space", "choose"),
        ("k", "a b c ...", "the letter beside a line chooses it at once"),
        ("k", "Esc", "close; the mouse works too: hover, click, the wheel"),
        ("h", "This help"),
        ("k", "up|down", "sections (or click one)"),
        ("k", "PgUp|PgDn", "scroll a long section (or the wheel)"),
        ("k", "/", "search every key and action: type, then {Enter} to keep it or {Esc} to clear"),
        ("k", "Esc|?|q", "close"),
        ("h", "Elsewhere"),
        ("l", "log, chain", "up / down, {PgUp} / {PgDn}, the wheel; {Esc}, {Enter} or {q} close"),
        ("l", "prison camp", "{Enter} a day, {w} a week, {e} try to escape"),
    ]),
    ("Bases", [
        ("k", "walk into", "a man at his post to talk to him (or right-click him)"),
        ("t", "adjutant (orders, reporting in, passes), clerk (pay, mail, your record), military police (directions,"),
        ("t", "or arrest), quartermaster, armourer, cook, chaplain or political officer, surgeon, motor sergeant (a"),
        ("t", "vehicle; a supply run), air operations (flying orders), port director (a ship; the liberty boat)."),
        ("k", "Enter", "gets on with the orders they give you, even across sectors - then report back"),
    ]),
    ("Aboard ship", [
        ("k", "<|>", "up / down a ladder (or {e} on it)"),
        ("k", "Enter", "your job: to your station, the ammunition, a fire, sickbay"),
        ("k", "Z", "let the hours go by, until something matters ({z} too, when all's quiet)"),
        ("k", "e", "what's in front of you: a bunk, a ready locker or a mount, the repair locker, a fire or a leak,"),
        ("k", "", "a life ring, the rail (the liberty boat in port), the helm and the plot"),
        ("t", "Condition III: a 4-hour watch in three. General quarters: to your battle station, at the double."),
        ("t", "In port, off watch, the liberty boat takes you ashore. Be back by 0500: she sails without you."),
    ]),
    ("Chart & cockpit", [
        ("k", "Esc|e|q", "step back onto the deck (at a station aboard)"),
        ("k", "t|z", "next target / fly or steam on until something happens"),
        ("k", "+|-|m", "zoom / the war map"),
        ("h", "Flying (a key is a second)"),
        ("k", "left|right|a|d", "turn ({Shift}+arrow: hard turn)"),
        ("k", "up|w|down|s", "climb / dive"),
        ("k", "Space|.", "straight and level"),
        ("k", "[|]", "throttle"),
        ("k", "f|b|h", "guns / bombs or torpedo / turn for home"),
        ("k", "Tab|e", "next crew station / bail out"),
        ("h", "At sea (a key is ten seconds)"),
        ("k", "left|right", "helm fifteen degrees"),
        ("k", "up|down", "more or less speed"),
        ("k", "f|g|c", "main battery / torpedoes / depth charges"),
        ("k", "d|l|o", "dive or surface / launch a strike / signal the force"),
        ("k", "Tab", "bridge, main battery, AA gun, damage control"),
        ("k", "Space|.", "wait ten seconds"),
    ]),
    ("What you know", [
        ("t", "There are no hit points. Your body is on the right: watch the colours and the bleeding marks (~)."),
        ("t", "A watch tells you the time; a compass or map, which way a sound came from; a map, the objectives."),
        ("t", "You only know how many rounds are left if you count them ({r} on a full gun, or the kit screen)."),
        ("t", "Suppression narrows your vision. Blood loss drains the colour from the world."),
        ("t", "Crawling and heavy loads wind you; winded men move slowly and shoot badly. Everyone tires, freezes"),
        ("t", "and overheats just as you do - both sides."),
        ("t", "Captured weapons are clumsy until you learn them; a captured tank can draw your own side's fire."),
        ("t", "Sounds you can't see appear on the map where you think they came from - a guess."),
        ("t", "Being seen takes a moment: lie still in cover and they may look straight at you."),
        ("t", "The sun and moon are real: a dawn attack starts in the half-light; the moon lights the night."),
    ]),
    ("Lessons", [
        ("t", "Lie down behind something that stops bullets. Straw, hedges and doors hide you; they don't stop rounds."),
        ("t", "Bleeding kills slowly, then all at once. Bandage ({B}). Shout for a medic ({Y})."),
        ("t", "Machine guns own open ground. Crawl, use dead ground and smoke, flank them, or call the guns."),
        ("t", "When the shells whistle, you have a second. Get flat, or get in a hole."),
        ("t", "Heavy kit in deep water drowns you. Drop it."),
    ]),
]


def merged(rows):
    """Rows written across several lines become one paragraph again: a plain line that doesn't end a sentence
    runs on into the next, and a key row with no keys continues the one above."""
    out = []
    for r in rows:
        if out and r[0] == "t" and out[-1][0] == "t" and not out[-1][1].rstrip().endswith((".", "!", "?", ":", ")")):
            out[-1] = ("t", out[-1][1] + " " + r[1])
        elif out and r[0] == "k" and not r[1] and out[-1][0] in ("k", "l"):
            out[-1] = (out[-1][0], out[-1][1], out[-1][2] + " " + r[2])
        else:
            out.append(r)
    return out


def search(query: str, now=None):
    """Every row, in every section, that mentions the words (whole paragraphs, not the halves of them)."""
    q = query.lower().split()
    out = []
    for title, rows in ([("Right now", now)] if now else []) + SECTIONS:
        hits = [r for r in merged(rows) if r[0] != "h" and
                all(w in " ".join(str(x) for x in r[1:]).lower().replace("{", "").replace("}", "") for w in q)]
        if hits:
            out.append(("h", title))
            out += hits
    return out
