# FOG OF WAR - the manual

Everything the game does, in more detail than the [README](../README.md). For how the code fits
together see [ARCHITECTURE.md](ARCHITECTURE.md); for running tests and making the GIFs,
[DEVELOPMENT.md](DEVELOPMENT.md).

## What's in it

**26 battles** from 1939 to 1945: Bzura, Sedan, Crete, Smolensk, Moscow, El Alamein,
Stalingrad (the factory district and Operation Uranus), Guadalcanal, Kasserine, Kursk, Sicily,
Monte Cassino, Sainte-Mère-Église (night airborne drop), Omaha Beach, the Normandy bocage,
Arnhem, the Hürtgen Forest, Bastogne, Iwo Jima, Okinawa, Berlin, Changsha, Kohima, Tali-Ihantala
and the Don. You can play either side.

**16 nations**, each with its own full rank ladder (private to five-star), names, unit designations,
decorations, radio callsigns, doctrine (morale, training,
aggression, willingness to surrender, banzai) and battle cries in their own language: the USA,
Britain, Canada, Australia, New Zealand, British India, the USSR, France, Poland and China
against Germany, Italy, Japan, Finland, Hungary and Romania.

**Period equipment, filtered by nation and date.** 130 small arms (a Garand pings when the clip
ejects, Stens jam, MG 42s overheat, Type 97 grenades are often duds). Also:
- AT rifles, bazookas, Panzerschrecks, PIATs and Panzerfausts
- flamethrowers, mortars, satchel charges, magnetic mines, Molotovs
- 135 vehicles and emplaced guns, each with real armour per facing and penetration values
- 56 aircraft types and 30+ off-map artillery batteries, including naval gunfire and Katyushas

**The world never ends.** Each battle starts on a strategic map of sectors, and each sector is a
full battlefield (270×180 tiles, about 540 × 360 m, by default). The world goes on beyond it in every direction, made as you first
need it:
- the front runs on to either side, with its own bulges and salients;
- each army's rear goes back and back: reserves, garrisons, depots, headquarters, airfields;
- far enough out, the country itself changes. Walk east from Saint-Lô and you reach Germany,
  with its own terrain and its own town names. Coasts and islands end at the sea.

Walk off the edge of the ground you're on and you're straight into the next sector, with no
prompt and no time skipped. The front moves, reserves march to the fighting, and reinforcements
flow into your battle from neighbouring sectors. The war is simulated in a wide bubble around you.
Destroying a depot, battery or flak site has consequences beyond your own map.

**Lots lying around.** Houses still hold what their people left: food, coats, bottles, maps,
now and then a rifle under the floorboards. Barns have tools and wire, and churches have
dressings. Fought-over ground is littered with helmets, dropped rifles, magazines, bandoliers
and ration tins. Behind the lines there are supply dumps.

**Fortifications and bases.** You'll meet:
- trench lines, foxholes, sandbagged MG nests, concrete bunkers with embrasures, casemated AT guns
- wire belts and minefields (including S-mines that click before they jump), dragon's teeth,
  hedgehogs and anti-tank ditches
- supply depots, artillery batteries, flak sites, command posts, aid stations, motor pools and
  airfields

Ammo stacks and fuel dumps cook off when hit.

**Terrain** is generated per biome: bocage, farmland and villages, towns, ruined cities, factory
districts, steppe, desert, forests, jungle, marsh, mountains (with a ruined abbey), volcanic ash,
and beaches with a sea, surf, obstacles and bluffs. Rivers get bridges. Weather and day/night
follow the real date.

**Everything breaks.**
- Shells crater the ground and knock down walls, and buildings turn to rubble.
- Bridges collapse, trees become stumps, and tanks crush hedgerows and walls.
- Glass shatters, fires spread with the wind, and smoke and dust block sight.

## Command

Every army on the field is organised the way it really was: squads (sections, Gruppen) in
platoons, platoons in companies, companies in a battalion, with weapons platoons, tank troops and
AT guns attached, and commanders at every level. Ranks run on one 19-grade scale from private to
five-star, with each nation's own titles (Gefreiter, Starshina, Heichō, Maresciallo d'Italia,
General of the Army, Marshal of the Soviet Union...).

**Who you can order.** Anyone in your own chain of command, and any other friendly unit whose
leader you outrank. Below general rank, only men of your own army: a British lieutenant can't
order Americans about. Giving orders to a unit outside your chain takes it under your command.

**How the order gets there.**
- By voice, if they can hear you. The louder the battle, the shorter the range.
- By hand signal, if they can see you (simple orders only).
- By radio, if you have one (or your radioman is beside you) and so do they. American platoons
  have SCR-536 handie-talkies from 1943; Commonwealth platoons the No. 38 set; most tanks have
  sets; most rifle squads have nothing.
- By relay, through their platoon commander.
- By runner: one of your men carries the order on foot, and runners get shot.
Orders take time to arrive, radios fail, and broken men refuse suicidal orders (once).

**Orders:** move, attack, assault, flank, suppress, defend, hold, dig in, ambush (hold fire until
they're close), come to me, regroup, fall back, mount up / dismount, resupply at an ammunition
dump, rules of engagement (fire at will / return fire / hold fire), report, and release to use
their own judgement. You can order a single squad or a whole platoon or company. Units you don't
give orders to carry on with the battalion's plan.

**Where your orders point.** An arrow at the edge of your view, or a grease-pencil X on the ground,
shows where your orders send you and how far (in yards if you have a map or compass, "that way" if
not). The orders you give stay pencilled on the map for a couple of minutes.

**Fog of command.** Units report back by radio or shout: position, strength, what they're doing,
the enemy they can see, and whether they're low on ammunition. The command screen marks where
each unit last said it was, and when. Radio chatter on the net tells you how the rest of the fight
is going.

**Succession, promotion, medals.** When a leader falls the next man takes over, and sometimes
that's you: a private can end the day commanding a platoon. Merit (kills, objectives, acting
command, wounds) brings promotion, including battlefield commissions, and each nation's
decorations (Purple Heart to Medal of Honor, Iron Cross to Knight's Cross, Hero of the Soviet
Union...), posthumously if need be.

**The war map.** From colonel up, the front map (`m`) becomes a war map. Sectors within your
reach (one for a colonel, the whole theatre for a five-star) can be ordered to attack a
neighbour, dig in, send half their forces to another sector, or get artillery or air priority.
Orders go out at the next strategic tick (about ten minutes). Senior officers also get more guns,
faster, when they call fire missions.

## Kinds of war

**Battle types.** A front-line fight is only one of them. The others:
- **The big push**, over the top against a prepared line.
- **Holding the line** against wave after wave.
- **A tank battle** with dozens of tanks.
- **A night patrol** to find the enemy and get home unseen.
- **A commando raid** on a depot or battery far behind the line.
- **An agent behind the lines** in civilian clothes, with forged papers and papers checks, stealing
  the enemy's operation orders and carrying them home across the front.
- **A partisan ambush** on a convoy.
- **Encircled**, breaking out to your own lines.
- **Rearguard**, holding until the army gets away.
- **A sniper's hunt.**
- **Shot down** deep in enemy country.
- **Prisoner of war.**

**The character and battle creator.** Choose side, battle, nation, service (army, navy, air force),
battle type, role, unit, rank (only the ranks that fit the role: NCOs, officers, generals and
admirals), name, traits, weapon, extra kit, and whether the war deals you a fair opening. Any of it
can be left to chance.

**Special units, as rare as they were:** SAS, Commandos, the LRDG, Gurkhas, Chindits, US Rangers,
Marine Raiders, OSS and SOE agents, the Cichociemni, the First Special Service Force, Navajo code
talkers, Soviet penal battalions, NKVD troops, naval infantry, the Night Witches, women snipers, the
Maquis, the Waffen-SS (with their own ranks), Brandenburgers, Fallschirmjäger, Gebirgsjäger, the
Decima MAS, Alpini, the Folgore, Finnish sissi, Teishin paratroopers and the Tokkōtai. Each has its
own kit, training and doctrine (fanatics rarely surrender; some units shoot prisoners). Enemy
squads are drawn from them too, where they really fought.

**Aboard: one man on a ship, or in a bomber.** At sea you aren't the ship. You're one man in her
company, and she's under way in the same war as every other ship and aircraft in this part of it.
- **Ships are full size.** Every class is built 1:1 from its real dimensions (a tile is two metres):
  a Fletcher-class destroyer is 116 m of three decks and 330 men; an Essex-class carrier is 270 m
  of island, flight deck, hangar and two decks below, with 2,600 men aboard. Up and down the ladders
  (`<` `>`, or `e` on one) are berthing compartments with racks four high, messes, galleys, the
  sickbay, magazines, fire rooms and engine rooms, repair lockers, the radio room and CIC, avgas
  stowage on a carrier, torpedo rooms on a submarine. Only the deck you're on is simulated man by
  man; the rest of the ship carries on around you.
- **The ship's routine.** In Condition III you stand one four-hour watch in three at your watch
  station (a lookout post, a gun, the bridge); off watch the time is yours. Turn in on a bunk (`e`),
  or press `Z` to let the hours go by: time runs at up to a thousand times normal speed and stops
  for anything that matters (a contact, general quarters, a hit, a job for you, your watch).
- **General quarters.** "BONG-BONG-BONG... all hands man your battle stations!" Men pour up and down
  the ladders; yours is on the panel, and Enter takes you there, deck by deck.
- **Jobs.** The chief hands out work, and Enter shows you how to do it or takes you through it: feed
  your mount from the ready lockers, fight a fire with a hose from the repair locker, shore a
  flooding compartment, carry the wounded to sickbay, throw a life ring to a man overboard. A
  lookout who spots something first and reports it gets the credit.
- **The captain fights her.** When you're not the one conning her, the captain closes with the
  enemy to gun range, or stands a carrier off at strike range and launches her air group, steers
  round islands, and takes her home when it's over. An officer can take the conn at the helm or plot
  (`e`), which opens the chart view; Esc steps back onto the deck. An admiral signals the force.
- **What comes for her comes for your deck.** Dive bombers scream down on you, torpedo planes come in
  low with the track running at the hull, fighters strafe the gun crews, and a kamikaze doesn't pull
  out. Hits land on the deck they would really hit: bombs on the flight deck and hangar, torpedoes
  in the lowest compartments. If you're on that deck you see it; if not, you feel it through the
  hull and hear about it. Flooding spreads compartment by compartment; if she goes down, she goes
  down under you: "Abandon ship!", over the rail, and a ship at twenty knots doesn't stop for a man
  in the water.
- **The lookouts report by bearing from the bow.** From an open deck, aircraft and ships show at the
  edge of the view ("✈ D3A 'Val' 0.9 km"); below decks you only know what the loudspeaker says.
- **Bombers too:** the fuselage of a B-17 or a Do 17, from the nose to the tail turret, with the sky
  outside. Take a station (`e` on it) to fly her, aim the bombs or man a turret, which opens the flight
  view. Flak bursts beside you and fragments come through the skin; the men hit are the crew at those
  stations. The escape hatch (`e`) is how you bail out.
- **Fighter pilots** fly alone, from the flight view.

**The air.** Fly as fighter pilot, bomber pilot, bomb aimer or air gunner.
- Missions: fighter sweeps, intercepting bomber raids, escorting the bomber stream, ground attack,
  dive bombing, torpedo attacks, strategic bombing deep in enemy country, photo reconnaissance,
  and (for Japan, late war) the special attack.
- Aircraft fly with real speed, turn rate, climb and stall.
- Hits damage engines, wings, tail, fuel and crew. The gunners defend the bomber from their turrets.
- Flak comes up over targets and ships.
- Land back at your airfield, bail out and come down in whichever sector is below you (evading if
  it's enemy country), or ditch and drift in a dinghy until you're rescued, captured or dead.

**The sea.** Serve as a sailor on an AA gun or in damage control, as a watch officer, or as the
captain of a destroyer, cruiser, battleship or submarine. As an admiral you command a task force
from a carrier.
- Salvos walk onto the target as the gunners find the range.
- Torpedoes run straight and sometimes don't explode.
- Submarines dive, and escorts hunt them with sonar and depth charges.
- Carriers keep fighters overhead and launch strikes of dive and torpedo bombers.
- Surface actions, carrier battles, convoy escort, submarine patrols and shore bombardment (which
  thins the enemy ashore).

From the ground you can take off from your own airfield, or signal a boat out to the fleet from
the shore.

**The chain of command, all the way up.** Every soldier's chain runs from his squad leader to his
nation's head of state. Where history knows who held a post on a given day, that's who holds it,
and they fall when they really fell. Rommel is strafed on 17 July 1944 and Kluge takes Army Group
B. Roosevelt dies, and Truman is president. Everyone else is a man with a name, and men die. You
only know what you've been told: word takes time to come down the line.

**The general's war.** From colonel up (G), your command is laid across the war map as a real order of
battle, each formation holding its own strip of the front.
- A battalion holds a sector; three make a regiment (or a Commonwealth brigade under a brigadier).
- Three regiments make a division, two or three divisions a corps, and three corps an army.
- An army group (or Soviet front) holds two or more armies.
- Historical formations and commanders are placed where the data knows them (9. Armee under Model, its
  Panzerkorps under Lemelsen, Harpe and Zorn, von Kluge's 292. Infanterie-Division). The rest are
  generated to national conventions, each with a commander of the right rank; they are killed,
  wounded and relieved like everyone else.
- The staff screen gives orders to the level below yours: battalions for a colonel, regiments for a
  division commander, divisions from corps up. The command roster (`C` or `O`) shows the whole tree
  with every commander and strength, down to the squads of the battalion on the ground you're standing
  on. Pick a distant formation there to give it orders through the staff.
- Every soldier's chain of command (`@`, then Tab) runs through the same formations.

Order a formation to attack, hold, move or come out into reserve, and the staff turns it into
orders for every battalion. Attacks by several divisions on one objective go in together. Commit
the reserve where you choose, wait at headquarters for the situation reports, and be promoted (or
relieved) by results.

The numbers on the staff screen are the game's own, not decoration. Every man, tank and gun listed
is one the battlefield puts on the ground when you're there: a squad, a gun team, a tank and its
crew, a half-track with a rifle squad aboard, the guns of a battery. On the ground you're standing
on they're counted, not estimated. An attack you order really happens:
- Walk or drive into the target sector (`v` on the staff screen: *go and see*) and you're in the
  battle. The first wave is moving up from the side they're attacking from, the rest are behind,
  and the guns are firing.
- Stand in the sector it goes in from, and you watch half the troops there form up and march off
  the map edge into it. You can follow them.
- Stand next door and you hear it, see the smoke by day and the gun flashes at night over the edge,
  and look across (hover the mouse) to see what's burning.

**The war comes to you.** Wait anywhere and the enemy does something about it, according to where
you are:
- On the line: assaults at dawn after a bombardment, counterattacks on ground just taken, night
  patrols and trench raids, snipers, harassing fire.
- Behind the line: fighter-bombers, bomber raids on depots and towns, and night raiders.
- In occupied country: partisans come out of the woods, and commandos go for the installations.
- On the coast: the enemy's navy.
- Behind their lines: search parties, once they know you're there.

**Your body, in detail (@).** Every part and wound, blood lost, pain, drugs, deafness. Cold and heat
matter too: core temperature follows the air, your clothes, whether you're wet, moving or under a
roof. That means shivering hands, hypothermia and frostbite in the Russian winter, and heat
exhaustion in the desert. Tab shows your service record and chain of command.

**Bigger battlefields.** New games default to a large battlefield: 270 x 180 tiles, about 540 x 360
metres, with roughly twice the men on each side. A sector now holds a strong company or a weak
battalion instead of a platoon, and the staff screen's numbers grow with it. Standard (180 x 120) is
quicker on slow machines; huge (360 x 240, three times the men) is for fast ones. Choose it in
Options; it takes effect for new games.

**Stealth.** Being seen is a process, not a switch.
- A man walking in the open is seen at once. A man lying still in a hedge bottom may be looked at for
  a long time before anyone realises what they're looking at. A sniper in a ghillie suit in long grass
  may never be seen at all until he fires, and not always then.
- An observer builds up awareness over seconds: fast if you're close, moving or silhouetted, slow if
  you're far, still and in cover, and faster if he's alert and expecting trouble. Half-aware, he looks,
  and tells his mates there's something over there.
- Camouflage counts where it matches the ground: British and American ghillie suits, the Red Army
  sniper's maskhalat, the German Tarnjacke, Japanese foliage capes and snow smocks. A snow smock on
  green grass is worse than nothing.
- Snipers, scouts, commandos and intelligence men have fieldcraft: quieter, and slower to be noticed.
- Pace **creep** (`W`) is slow, nearly silent and low. Snipers and patrols creep when they aren't
  fighting, and snipers pick hidden positions and move after a few shots.
- The panel tells you how hidden you feel: well hidden, concealed, partly exposed, in the open, or
  "you feel eyes on you".

**Prisoners.** A man who throws down his rifle isn't yet a prisoner.
- Right-click him (beside him) to take him prisoner, and again for his orders.
- Search and disarm him. It takes most of a minute of kneeling beside him. His rifle, grenades and
  ammunition go in a pile, and his paybook and papers go to you; intelligence reads them, or you do if
  you know the language.
- Tell him to follow you, sit and wait, or walk back to your lines on his own. Or hand him to a
  comrade, who walks him to the rear and gets back into the war.
- A wounded enemy on the ground can be taken prisoner, patched up and carried.
- Shout for a surrender ("Hände hoch!", `Y`). Men who are broken, cut off, wounded or out of
  ammunition may take the offer; fanatics almost never do. An unsearched prisoner may still have a
  grenade under his tunic.
- Your prisoners come with you across the map edge. Bring them within sight of the rear, or to a
  command post, aid post or depot, for the credit and the interrogation.

**Orders you can carry out (Enter).** When your sergeant tells you to patch a man up, get ammunition
over to a gunner, get on that gun, fetch ammunition from the dump, run a message or scout the next
hedge, the panel shows what Enter will do: walk there and do it, following him if he moves. With no
special task, Enter walks you toward your squad's objective.

**Walk, run, sprint (W).** A walking man can shoot, listen and keep going all day. A running man
covers ground and can't hit anything. A sprinting man crosses the open in seconds: he's loud,
conspicuous, gasping and harder to hit, and after thirty yards he's done. Breath comes back in a
minute. Fatigue builds over hours of marching, digging and sprinting, lowers the ceiling on your
breath, and only goes with real rest. Load, bad legs, crouching and carrying a man all cap your
pace.

**The same rules for everyone.** Pace, breath, fatigue, cold, heat, wet clothes and frostbite apply
to every soldier on the field, friend and enemy. The enemy freezes in the same snow you do: frozen
riflemen shoot badly, soldiers in the heat look for shade and water, and men seek a roof when
they're cold and nobody's shooting.

**Safe mode.** As in CDDA, with the enemy in sight or rounds coming your way, a step (or a run, or a
click-to-walk) stops with a warning: what's there and which way it is. Take the step again to go
anyway. `'` ignores what you can see now; you're warned again if it comes much closer, or about
anything new. `!` (or Esc > Options) turns safe mode off.

## Also deeper

- **Peeking.** Lean out of cover to look and shoot round a corner, over a wall or out of a window.
  You see from where your head is, and you're harder to spot. Anything that comes through that
  spot can still take your head off.
- **Stamina.** Crawling, heavy loads, mud, snow and swimming wind you. When you're winded you move
  slower and shoot worse. Rest to get your breath back.
- **Morale.** Men recover faster with their leader beside them and an officer in sight. An officer
  going down shakes everyone who saw it, and objectives won or lost move a whole side's nerve.
- **Logistics.** Each side has an ammunition point behind its line, and depots in the rear. Squads
  that run low go back to resupply when things are quiet, or when you send them. Sectors cut off
  from depots and the rear wither. Quartermasters take captured kit for requisition credit (and
  pay well in the rear for souvenirs). Enemy papers taken to intelligence are worth more the
  higher the man who carried them, and the information in them is real.
- **Aim and recoil.** Aim is a sight picture that takes time to build: snap shot, aimed, careful,
  precise, and through a scope, dead steady. Each level costs time: more for a long rifle than a
  pistol, and more when you're winded, hurt or under fire. Every round kicks the muzzle off
  target, and it takes a moment to settle. Full-power rifles kick hard, and SMG bursts climb.
  Going prone, bracing, or using a bipod or tripod tames it. Your **speed** (moves per second:
  cut by load, wounds and breath) governs everything you do.
- **Captured kit.** Anything the enemy drops is yours to use, and you're clumsy with it until you
  learn it. An unfamiliar rifle aims slower, shoots looser and reloads with fumbling; bolts and
  jams take longer. Firing it, loading it and clearing it makes it yours. Allied weapons are
  half-familiar. A captured tank's crew grind the gears and misread the sight. Until you paint
  your own markings on it, your side may take it for the enemy's. The same goes for you in an
  enemy helmet at a distance.
- **Crews.** Every vehicle has seats: driver, gunner, loader, bow gunner, commander. You do your
  own seat's job and nothing else. The men in the other seats fire their own weapons at their
  own targets. From the commander's seat you steer the driver and give the gunners targets.
- **Medicine.** Anyone can pack a wound. Medics and corpsmen do more. Surgeons at aid posts
  operate, and men heal slowly in the line and faster behind it. Allies patch you up and share
  ammunition, and they expect the same of you.
- **Duty.** Superiors hand out tasks, notice neglect and reward help. Shoot your own men, murder
  prisoners, or desert under their eyes, and the consequences escalate: reprimand, demotion,
  arrest, and finally your own side turning on you. Take prisoners and bring them in for credit.
  Some armies shoot theirs.
- **Captivity.** Surrender and you may be shot, or searched and marched to the rear, then held in
  a camp while the war goes on. There's hunger, sickness, Red Cross parcels, escape attempts, and
  liberation if your side takes the ground.

## The AI: Dijkstra maps

The AI follows RogueBasin's
["The Incredible Power of Dijkstra Maps"](https://www.roguebasin.com/index.php/The_Incredible_Power_of_Dijkstra_Maps).
Each side keeps shared maps (`fow/brain.py`):

| map | meaning |
|---|---|
| **exposure** | How much danger a soldier at each tile is in. It's built from every known enemy's field of fire (FOV per contact, weapon range and threat) and reduced by directional cover and dug-in positions. |
| **safety** | Distance to the nearest safe tile. Crossing exposed ground is expensive. |
| **threat distance** | Distance to the known enemy: the approach and assault map. |
| **flee** | Threat distance × −1.2, rescanned. Routing men run intelligently instead of into corners. |
| **home** | Covered route back to your own map edge, used for retreats. |
| **objective** | Covered approaches to each objective. |
| **flank** | Per squad: routes to tiles on the enemy's flank that have a line of fire on a machine gun or bunker. |
| **vehicle** | Routes for tracked or wheeled vehicles, with crushing costs. |

Soldiers roll downhill on a weighted sum of these. Behaviour states only change the weights. The
result is:
- fire and manoeuvre with bounding teams
- flanking attacks on MGs and bunkers
- men crawling to cover when suppressed
- retreats along covered routes, and routs
- banzai charges
- MGs, snipers and tanks holding their range

On top of that:
- Squads share contacts, hear gunfire and investigate it.
- MG teams area-fire at last-known positions, and loaders feed the gunners.
- Snipers shoot and relocate, and pick officers and gunners first.
- AT teams stalk tanks' flanks and rear.
- Medics crawl out to the wounded.
- Officers call artillery on enemy concentrations, occasionally "danger close".
- Engineers cut wire and satchel bunkers.
- Soldiers won't fire through their friends, but friendly fire still happens.

## Sprites, sound and fonts

- **F2** switches between hand-drawn sprites and ASCII.
- **Soldiers are drawn from their kit.** Each figure shows:
  - his actual helmet or cap: M1 with netting, Brodie, Stahlhelm, SSh-40 with its red star, Adrian,
    Type 90 or a field cap with neck flaps, a peaked cap
  - the weapon model in his hands: a Garand isn't a Kar98k, and a PPSh has its drum
  - what's on his back: pack, radio and aerial, flamethrower tanks, a slung rifle
  - webbing, stick grenades in the belt, binoculars, the medic's armband, greatcoats and snow
    smocks, field dressings
  - his uniform, by army and climate (khaki drill in the desert, HBT in the Pacific)
  - his pose (standing, kneeling, prone, aiming, hands up, down and bleeding), facing the way he
    last moved or fired
- **Vehicles and big guns are their real size**, about 2 m to a tile:
  - Sherman 3×2, King Tiger 4×2, jeep 2×1, landing craft 5×2, 88mm flak 3×3
  - they turn only where there's room, run down the enemy, and scatter their own men
  - they leave wrecks as big as they were, and a turret points where it's aiming
- **F3** turns sound on or off. Gunfire, explosions, engines, shell whistles, sirens and
  ricochets are all synthesised in the game, positioned in stereo, and delayed by distance.
  Sounds are muffled beyond walls, and there are ambient battle, wind and rain loops.
- **Voices**:
  - Shouts, orders, acknowledgements and radio traffic are spoken aloud, in each army's own
    language, by the system's speech synthesiser (macOS `say`, or espeak-ng on Linux). Romanised
    Russian, Japanese and Chinese are converted back to native script first.
  - Shouts are strained and echo, radio comes through a set with static and a squelch, and
    distance and deafness muffle what you hear.
  - Lines are rendered in the background and cached in `~/.fogofwar/voices/`. The first run
    takes a minute or so to warm up.
  - With no synthesiser, soldiers shout in formant-synthesised gibberish. Toggle voices in
    Options.
- **The mixer** (Esc > Options): master volume, then weapons and explosions, battle ambience
  with wind and rain (turned well down by default), voices, footsteps and engines, and the
  interface, each on its own slider. You can also choose which sounds get written in the log:
  all, only nearby ones, or none.
- **F4** switches the font between DejaVu Sans Mono and the classic bitmap one.
- **Mouse wheel over the map, or + / -**: zoom, in sprites and ASCII alike. The map's tiles or
  font are rebuilt at each size, so they stay crisp, and the interface doesn't change size.

Settings persist in `~/.fogofwar/settings.json`, and are all on the Options screen (Esc > Options, or from the main menu).

## Kit

Your kit works like Escape from Tarkov's:
- Equipment slots: helmet, body, webbing, pack, a slung rifle, a second long arm, holster and
  bayonet/knife, plus pockets.
- Webbing and packs are grids. Every item takes up w×h cells and can be rotated.
- Magazines, stripper clips and belts are real items with round counts. Reloading swaps in the
  fullest magazine from the quickest pouch, and speed reloads drop the empty one.
- Bodies keep their kit, and searching them opens a second pane beside yours.
- Everything costs time, and digging into your pack takes longer than reaching a pouch.

Open it with `i`. In the kit screen:
- Arrows move, and Enter picks up or puts down (drag and drop with the mouse works too).
- `r` rotates, `e` uses or equips, `l` loads, `u` unloads, `c` counts rounds, `d` drops, `q`
  quick-moves, `x` looks.
- Tab switches between your kit and the body you're searching. `[` and `]` switch between piles.

## Diegetic interface

What you know is what your soldier knows.
- **Menus come from your `@`**: inventory, item actions, throws, orders and the radio pop out of
  your soldier with a connector line. Item actions chain off the selected line.
  **Tooltips point at the tile** you look at or hover.
- **No hit points.** The body doll on the right shows each part's condition in colour, plus
  bleeding marks. Suppression narrows your vision. Blood loss drains colour from the world.
  Pain flashes red. Blasts deafen you.
- **Sound**: gunfire you can't see appears on the map where you think it came from, as
  `crack`, `brrrt` or `BOOM`. Veterans can tell a Garand from a Kar98k.
- **Speech bubbles**: soldiers shout in their own languages ("Handgranate!", "Sanitar!",
  "Tennōheika banzai!").
- **Your gear gates your knowledge.** Without a watch you only know the time of day. Without a
  compass or map, sound directions are vague. Without a map you don't see the objectives or the
  front; you follow your squad leader, who points: "there, NE, 250 yards".
- **Ammo is estimated** ("about half") unless you count it.
- **Hit chances are words** ("a long shot"). You can switch them to numbers in Options.

## Controls

| key | action |
|---|---|
| arrows / numpad / `hjklyubn` | move (into an enemy: melee) |
| Shift+direction | keep going until something happens (`HJKLUN` too; `Y` and `B` are shout and bandage) |
| `W` | pace: creep / walk / run / sprint |
| Enter | carry out your current order (walk there and do it) |
| `e` aboard | ladders and hatches, the helm or plot, a crew station, the escape hatch |
| `<` `>` aboard | up / down a ladder |
| `Z` aboard | let the hours go by (any key stops); `e` on a bunk to turn in |
| F1 | help |
| `!` / `'` | safe mode on/off / ignore the dangers you can see now |
| left-click | walk there |
| right-click | context menu (fire, throw, call artillery, order squad...) |
| `.`, numpad 5, `s` / `z` | wait a second / wait until something happens |
| `c` / `p` | crouch / prone |
| `f` or Tab | aim & fire (`Tab` next target, `a` aim longer, `A` aim fully and fire) |
| `F` | fire mode (or AP/HE in a tank) |
| `r` | reload / clear jam |
| `t` | throw (`c` to cook) |
| `i` `g` `d` `w` `a` | kit (PgUp/PgDn for more; tabs for each pile and body within reach), pick up, drop, wield, use |
| `B` | patch up yourself, or a wounded comrade beside you (or right-click him) |
| `q` | lean out of cover: round a corner, over a wall, out of a window (`q` again or move to pull back) |
| `S` | resupply at a depot or ammo crate |
| `D` | dig in |
| `V` | binoculars |
| `e` | enter a vehicle or man a gun; inside: change seats, crew orders, climb out |
| `v` | vehicle MG (your seat's), or from the commander's seat, point the MGs at a target |
| `o` | close a door |
| `O` | orders for the squad you lead |
| `C` | command: your chain of command and anyone you outrank |
| `R` | radio (fire mission, smoke, air) |
| `Y` | shout (medic!, grenade!, surrender) |
| `G` | general staff (colonels and up): divisions, corps, reserve, go and see (`v`), wait at HQ |
| `F5` | minimap (click it to look there) |
| Ctrl+arrows | pan the view (Home: back to you) |
| `x` / `;` | look (or just rest the mouse on something) |
| `m` | the war map: scrolls forever, `z` wide view; orders from colonel up |
| `P` | message log |
| `@` | yourself: health in detail (Tab: service record and chain of command) |
| `?` | help |
| Esc | menu / save |
| F2 / F3 / F4 | sprites / sound / font |
| wheel, `+` / `-` | zoom toward the mouse or the look cursor |
| middle-drag / Home | pan the view / back to you |
