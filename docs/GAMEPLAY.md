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

**Reading the ground.** Whether you can get through something is shown three ways:
- *How it's drawn.* Anything you can't walk through stands up out of the ground: a dark rim round it
  and a shadow cast down and to the right (trees, palms, mangroves, boulders, wagons, stacks), or a
  raised, bevelled block (walls, bocage hedgerows). Anything you can walk through lies flat, ground
  showing between: undergrowth, dense jungle, bamboo, garden hedges, crops, reeds, rubble. In ASCII
  the trees are `♣` `♠` `τ` and walkable greenery is `%` `"` `;` `!`.
- *The look.* Rest the mouse on a tile (or `x`) and it says the going, from the same costs the
  pathing uses, slope included: "No way through on foot - a tank could push through it", "Very slow
  going - you can't see into it". With *Hit chances as numbers* on, it gives the multiple:
  "(x2.6 the time)". In a vehicle it's the vehicle's going: what it can smash through, what's too deep.
- *X, reading the ground.* Tints the battlefield: red where there's no way through (for you on foot,
  or for the vehicle you're in), amber where it's slow, deeper the slower. `X` again turns it off; it's
  also in Options.

**Landmarks.** Every sector has a few places men steered by and fought over, chosen by its country,
climate and ground (`landmarks.py`). They're candidate objectives, preferred over a nameless field, and
they're real terrain:
- *France, the Low Countries, Germany, Italy:* a windmill on its rise (a stone tower mill, or a wooden
  post mill in the north and east); a railway right across the sector with its station or halt, the
  platform, goods wagons and sometimes a strafed locomotive on the siding, the water tower and the
  telegraph poles; a château behind its park wall, a poplar-lined gravel drive, a fountain in the
  forecourt and cellars under it all; the village cemetery - high stone walls in France and Italy,
  family vaults better cover than any house, a chapel, cypresses; a brickworks with its kilns, clay pit
  and chimney; a quarry (a hole in the ground, cliffs round it); a slag heap with its pithead in the
  mining country; a castle on its hill, its curtain wall breached, towers and a keep you can climb; a
  Würzburg radar station behind its wire, with bunkers and Tobruk pits; a landing strip; a tank farm
  of oil tanks in their earth bunds, which go up like the end of the world when hit.
- *Russia and the Ukraine:* the grain elevator (Stalingrad's was fought over for days), its silos
  concrete that stops anything; the kolkhoz with its long barns, silos and dead tractors; wooden
  windmills; birch-shaded cemeteries of wooden crosses.
- *The desert:* a fort with corner towers and a whitewashed barracks; the marabout, a holy man's tomb
  (Sidi Rezegh is one); the landing ground, its edges marked with painted drums; an oasis.
- *The Pacific and Asia:* a coconut plantation in rows (Guadalcanal's were Lever Brothers'), the
  manager's bungalow and the copra sheds; a mission church; a shrine behind its torii; a pagoda - a
  cluster of stupas in Burma, a brick tower in China; an airstrip.
- *Coasts:* a lighthouse on the bluff above the beach.
- *Where the fighting's been heavy:* the burnt-out tanks of the last attack, in their shell holes.

Smaller touches: a calvary at the crossroads, the memorial to the last war in a village with a church,
named buildings (the mairie, the café, the Gasthaus, the osteria, the kolkhoz office, the teahouse),
poplars along French and Italian roads, telegraph poles across the steppe and the desert, Tobruk pits in
a German line and stone sangars where the ground's rock. Towers, keeps, lighthouses, pagodas and the
elevator have open tops: a sniper up there sees over everything, as in a church tower.

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

**Orders that need a place** (advance, assault, flank, suppress, defend, ambush at) offer a short
list first: the next objective, the enemy positions your side knows of, the other objectives. Enter
takes the first; you can still pick any spot on the map, and Tab steps the cursor through the list.

**Tasks.** Between the fighting a leader sends his men round the dead and the dumps: for
ammunition that fits their weapons, for dressings and morphine, for grenades and weapons, or for
the enemy's papers and maps, which come to you (for the intelligence officer). He has the wounded
carried back to the aid post, the men who've surrendered searched and marched to the rear (your
order, your credit), and the tank crews given a hand. Everything taken is really taken out of the
dead men's webbing. The men work when no enemy is close and fight when one is, never send more
than half the squad to carry, and the leader reports what they found.

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

## Behind the line: bases

Headquarters, depots, aid stations, motor pools, airfields and naval bases are staffed by real
men at real posts. They carry what rear-echelon men carried, go back to their posts when nothing's
happening, can be killed, and are only there while the base is (and still there when you come
back). Walk into one to talk, or right-click him.

| who | where | what he does for you |
|---|---|---|
| adjutant | headquarters | orders; report in when you've lost your unit; the situation; a pass to the rear |
| clerk | headquarters, naval base | your pay; mail from home; your service record (and the promotion the CO signs); a letter home |
| military police | headquarters, naval base | where to find everyone - or your arrest, if you're wanted |
| quartermaster | depot, ammunition point | trade what you carry; draw kit |
| armourer | depot | strip and clean your weapon (it jams less); ammunition; swap a captured weapon for an issue one |
| cook | depot, airfield, naval base | a hot meal, a mug of whatever your army drinks, rations for the road |
| chaplain (the Red Army: political officer) | aid station | a talk; the tags of the dead; a letter to a family |
| surgeon | aid station | treatment |
| motor sergeant | motor pool | a vehicle; repairs |
| air operations officer | airfield | flying orders for aircrew |
| port director | naval base | a ship; the liberty boat back to yours |

**The adjutant's orders** are real jobs in the real war, and they show in your orders like any
other, with the arrow and Enter to get on with them, across sectors if need be:
- carry dispatches to another headquarters and hand them to an officer there;
- go up and rejoin a company in the line (you're put in a squad when you arrive);
- patrol into enemy ground, see what's there, and come back and report;
- stand a guard at the base;
- report to the naval base for a ship, or to the airfield for flying duties.

Each has a deadline. Carry it out and report back for credit, merit and your reputation; let it
lapse and the adjutant will have words.

## Kinds of war

**Battle types.** A front-line fight is only one of them. The others:
- **The big push**, over the top against a prepared line.
- **Holding the line** against wave after wave.
- **A tank battle** with dozens of tanks.
- **A night patrol** to find the enemy and get home unseen.
- **A commando raid** on a depot or battery far behind the line.
- **An agent behind the lines**: a career, a cover and a mission (below).
- **Partisans**: an ambush on a convoy, or a resistance band's own mission.
- **Encircled**, breaking out to your own lines.
- **Rearguard**, holding until the army gets away.
- **A sniper's hunt.**
- **Shot down** deep in enemy country.
- **Prisoner of war.**

**The secret war: agents and the resistance.** An agent is a career drawn from what the services
really sent:

- an SOE circuit organiser, wireless operator ("the pianist") or courier;
- a Jedburgh team leader, dropped in uniform after D-Day;
- an OSS saboteur or spy, or an SIS agent;
- a Cichociemny of the Polish Home Army;
- a Soviet partisan organiser or GRU radio agent;
- an Abwehr or SD man, or one of Skorzeny's Operation Greif commandos in American uniform (the
  Ardennes only);
- a Japanese Nakano School officer.

Each gets a cover for the country he's dropped into (@, then Tab to the Cover page): a local name,
a trade that explains him (railwayman, country doctor, curate, commercial traveller, district nurse
and so on), the papers that trade needs (carte d'identité or Kennkarte, work permit, curfew pass,
demobilisation papers), its tools, a circuit named after a trade, and a field name. You go in plain
clothes with a civilian's bag: no identity tags, no webbing. At a papers check the right documents,
the language and a steady face help; banknotes sometimes help more.

The mission comes from the career:

- steal the plans from their headquarters;
- sabotage a depot, the guns, an airfield or the railway, with timed charges;
- receive a supply drop at night with the local reception committee;
- get your wireless traffic out;
- kill a man who is breaking the network;
- bring out a shot-down airman hiding in a barn;
- photograph their positions with a Minox and bring the film home.

A partisan (maquisard, FTP, Home Army, Soviet partisan, Chinese guerrilla) leads a small band on the
ambush or on the same sabotage, drop, elimination and rescue missions; the band is its own
reception committee.

The kit is the kit they had, none of it issued to ordinary soldiers:

- the Welrod, whose cough nobody hears at a few feet; the De Lisle carbine; the silenced Sten Mk IIS;
  the High Standard HDM; the one-shot FP-45 Liberator; the Colt Pocket Hammerless and the PPK; the
  sleeve gun;
- the smatchet, the garrotte, the cosh;
- Nobel 808 plastic explosive, TNT blocks and limpet mines;
- time pencils: place a charge with one in your kit and it's set for about ten minutes, faster in
  the heat and slower in the cold, and nobody runs from a bomb they don't know is there;
- the B2 suitcase set, the Paraset, the SSTR-1 and the Soviet Sever; the S-Phone; signal torches.

A silenced shot doesn't blow your cover unless someone sees you fire.

**The wireless** (R, or `a` on the set) talks to London, Moscow or Berlin in Morse:

- a report, which counts the enemy you've really seen;
- a request for a supply drop;
- listening for the BBC's personal messages.

Every minute on the air is a minute for the enemy's direction-finders. Twenty-odd minutes near one
place and a detector car with a loop aerial comes with a squad of field police, to where you were
transmitting. Move between transmissions and they start their bearings again. Caught at the set,
you're finished.

**Drops.** The aircraft belong to a real special-duties squadron: 138 Squadron RAF's Halifaxes, the
Carpetbaggers' B-24s, the Soviet Li-2s. The aircraft comes over the field at night at the time
London gave you. It drops only if the lights are there: your torches at the dropping zone, the
reception committee's, or the S-Phone talking the pilot in. Otherwise it circles twice and goes
home. The containers land spread along its line with what a load really held (Stens and magazines,
Brens, plastic and time pencils, grenades, dressings, Liberators, money). The committee carries
them off the field. The enemy heard the aircraft too.

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
- **Between battles.** When the job's done the signal comes from the task force commander. If
  she's short of fuel, has fired off her torpedoes or depth charges, lost half her air group or
  taken damage, she goes back to base. Otherwise there's more work: another enemy force reported,
  a coast to bombard, a convoy to take through, a submarine to hunt, men in the water to pick up,
  or a landing to cover against wave after wave of air attack. Fuel burns with speed (a status
  line shows it).
- **In port.** She anchors off a naval base (a real one where the theatre had one: Kerama Retto,
  Espiritu Santo, Alexandria, Portsmouth...). The oiler, the ammunition lighters and the repair
  gangs take as long as they take; `Z` lets the hours go. Off watch you can take the liberty boat
  ashore (`e` at the rail) to the base, with its quay and piers, port director, clerk, cook and
  MPs. Be back by 0500. When the refit's done her sailing orders come, and at 0600 she sails,
  with you or without you. Miss her and you're absent without leave: turn yourself in, or wait
  for the MPs.
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
exhaustion in the desert. Tab shows your skills, then your service record and chain of command.

**Skills.** Every soldier - you, your men, the enemy - has twelve skills from 0 to 10, shown in words
(untrained, a beginner, adequate, competent, skilled, expert, a master; the number too with numbers on):
marksmanship, gunnery, stealth, observation, hand to hand, first aid, demolitions, driving, radio and
fire calls, leadership, fitness and languages. Each starts as a roll around the man's general
training, so any private might turn out a fine shot or a natural at creeping about. His job and unit
then put a floor under what they drilled into him:

- a sniper can stalk, see and shoot;
- an agent can pass unseen, speak the language and work a set;
- a medic can close a wound, and a surgeon operate;
- an engineer knows charges;
- a tank crewman can drive and lay a gun;
- SAS, commandos, Rangers, Brandenburgers, the OSS and the Jedburghs are good at most of it.

Traits shift them (a crack shot, a clumsy man, a veteran). They're used where they matter:

- marksmanship steadies and speeds the aim;
- gunnery lays the tank gun, the field gun and the mortar;
- stealth makes you slower to be noticed, observation quicker to notice;
- first aid closes wounds, demolitions sets a charge faster;
- radio skill puts the guns nearer the target;
- leadership steadies the men round you;
- fitness decides how fast you tire;
- languages help when you tell the enemy to surrender.

They come on slowly with use, less so the better you are, and you're told when one improves.

**Hand to hand.** Rare, and when it came short and ugly. Each blow is one exchange of about a
second:

- the move, from what's in your hands: a bayonet thrusts, a rifle butt smashes, a kukri, sword or
  sharpened spade chops, a knife stabs, fists punch. Or you grab him, knock his weapon aside, or
  shove him off to make room to shoot.
- his answer: a parry with his rifle or blade, a twist aside, an arm thrown up (and the blow lands
  on the arm) - or nothing, if he never saw it coming.
- where it lands: a real part of the body with the wound its weapon makes, told as it happened
  ("You smash your rifle butt into the German's jaw - bone breaking"). A helmet turns a blow; a
  bayonet can stick between ribs and have to be wrenched free (a round fired frees it).

Two men can lock together. Then it's the knife, the throat, a throw to the ground, or tearing free,
and neither can bring a long gun round (a pistol, yes). A man looking the other way, or in the
dark, who hasn't noticed you can be killed with a knife or strangled almost without a sound: what
commandos and agents trained for.

Hand-to-hand skill, strength and wind, wounds, reach (a rifle and bayonet outreaches a knife), two
on one, a man on the ground and surprise all count. The right-click menu shows each move with the
odds as you'd judge them.

**The lie of the land.** Every sector has a real surface under it, in metres:

- gentle in Normandy's farmland;
- rolling on the steppe, and cut by balkas, the dry steep-sided ravines men lived in at Kursk and
  Stalingrad;
- steep in the Italian mountains and at Cassino, with a volcanic cone on Iwo Jima, jungle ridges on
  Guadalcanal, and near-flat desert but for the long low ridges that decided Alamein.

Rivers run in their valleys and cliffs stand up. The hills the staff named on their maps (Hill 112,
Point 593) are real hills. A crest hides what's behind it, for everyone: dead ground and the reverse
slope are real. A man higher up sees over the hedges and crops that hide the same field from a man
at their level. Uphill is slow and hard on the breath. The map is shaded as the land lies, with
contour lines every five metres. Look at a spot with a map in your kit and you're told its height
(and how far above or below you it is); without one, just whether it's up or down from you.

**Upstairs and down.** Buildings have floors. Walk onto the stairs and press `<` to climb: upstairs
has the same walls and windows as the ground floor, three metres higher, so from a window you see
and shoot over the hedges, walls and crops outside. The top of a church tower, a flat roof and a
barn's hayloft are open, so up there your own building's walls don't block you at all. The stairs
are the only way down.

A trapdoor (`>`) takes you into a cellar, the safest place in a bombardment: nothing sees in or out,
and a shell bursting outside is dust and a ringing in the ears. A floor blown out from under you
drops you into the rubble. Everyone uses the same stairs: defenders put their snipers and some of
their machine gunners upstairs (the sniper in the church tower), and men go down into the cellars
when the shells come.

**The roads behind the line.** Supplies come up to every front along real routes on the war map:

- from the depots and headquarters and the side's rear, sector by sector;
- each sector a front draws through carries traffic in proportion to how many fronts depend on it.

Walk through one and the roads are busy:

- ammunition, fuel and ration lorries (Red Ball Express GMCs, Bedfords, Lend-Lease Studebakers, Opel
  Blitzes);
- horse-drawn wagons and panje carts (half the German and Soviet columns moved at a walk);
- lorry-loads of replacements and tanks going up; ambulances and prisoners coming back;
- a dispatch rider, a staff car;
- military police at the crossroads, engineers filling the shell holes, linemen on the wire.

Your own side's lorries tell you what they carry and where it's going. When replacements and tanks
reach the far edge, they join the front they were sent to. The enemy's rear is the same, when
you're behind his lines.

Destroy a convoy and it's a cut in that road on the war map. The fronts beyond it are short of
shells, fuel and men until it's mended (a cut halves in about two hours). Their men start battles
short of rounds, their batteries run low, their replacements don't come, and short supply weighs
on every battle they fight. Blow up a depot and its sector supplies nothing. Off your map, both
sides go for the roads too: fighter-bombers over the busiest routes, partisans on the lines in
occupied country. Shooting up an ambulance, red crosses and all, is a crime to armies that cared
about the Geneva Convention.

**Orders, several at once.** The squad leader, the platoon sergeant, the adjutant's written orders,
the fire direction centre, your briefing: you can hold several orders at a time. The panel shows the
one you're on and the next two; `T` opens the orders book:

- who gave each order, and how it reached you (shouted, by runner, on the radio, written);
- when it was given and when it's due;
- what doing it brings: trust, a line in your record, commendations, the quartermaster's credit,
  promotion;
- what failing brings, in your army's own terms.

The punishments are carried out:

- a first failure is a dressing-down and extra duty (a beating in the Japanese army), and the
  fatigues are served at the next base before the adjutant gives you anything else;
- three failures put you on report: a fine docked from your pay, no pass for a fortnight, and an
  entry in your record;
- five cost you your stripe; for a Red Army private, the penal company.

Choose an order in the book and Enter gets on with that one.

**Autopilot and succession.** `A` hands your soldier to his training: the same AI every man runs,
following his orders (a squad you lead takes its orders from above), while you watch; `A` again
takes over. With succession on (Options, WHEN YOU DIE), death isn't the end of the battle: the war
goes on on the same field and you're someone else. Who is set by a rule:

- squad: a man of your squad;
- unit: your company or battery;
- nearest: whoever's nearest;
- role: the nearest man in your job;
- rank: the most senior man near;
- random: anyone on the field;
- killer: the man who killed you.

You can also allow either side, cap the number of lives, or be offered a list to choose from.
Each of the fallen goes in the memorial, and each new man starts with his own kit, rank and a
clean record.

**Talk to anyone.** `E` (or right-click a man) talks to whoever's beside you. Every soldier is a
man with a life of his own: a home town (the one his letters come from), the trade he'll go back to,
who's waiting, what he's like, whether he smokes. He has an opinion of you, and it moves with what
you do: a cigarette, a dressing when he was bleeding, staying with him when he was hit; asking
favours, being a danger to your own side.

With a comrade you can talk about:
- where he's from and who's waiting;
- how he's holding up: the truth about his wounds, his nerve, his ammunition, his canteen and his feet;
- what he's seen: he points, and it's marked where he means;
- the latest rumour: the war's real news as it reaches a foxhole, or a latrine rumour;
- what he makes of the sergeant.

You can also ask him for a smoke, ammunition, water or covering fire; steady him when he's shaking;
or trade. In a trade you see his face as you hold each thing up: he'd take it, or he shakes his
head.

The dying may ask you to take something home. The chaplain sees it gets there, and it goes in your
record.

A prisoner owes you his name, rank and number. For a cigarette, or when he's frightened enough, he
may tell you where his guns are. It's sometimes the truth, and you can't tell which. Without a
common language (your languages skill), it's gestures: a cigarette held out, a trade by pointing.

**The noise of a fight, the life of a quiet hour.** In a fight, men are loud:
- the wounded cry out, in their own language: where they're hit, the blood, the legs that won't
  carry them, and at the end their mothers;
- the crying goes on until a medic reaches them or they go quiet, and it wears on everyone who hears it;
- a man's buddy shouts his name when he's hit, runs to him if he can, and takes his death hard;
- men call "Moving!" and "Covering!", "I'm out!", "Where's it coming from?!" and "Incoming!";
- the frightened panic and a steadier mate talks them down, and the NCOs keep them firing, spread
  them out and get them up.

When it's quiet:
- smokers pass their cigarettes round (at night the glow can be seen);
- men trade what they have for what they want, and real things change hands;
- they show the photograph, read the letter, pray, and hum a song from home;
- the sergeant makes them change their socks;
- a man goes to his dead buddy's body and takes one of the tags;
- a souvenir hunter goes through the enemy dead for a Luger or a watch.

**Success is rewarded.** Doing well in the fight wipes out what you did wrong before, as it did for
real soldiers:
- killing the enemy in a fight, knocking out a tank, taking an objective, being wounded;
- bringing a wounded man in under fire, taking prisoners, a medal.

Every few points of it take a strike off your record, with the extra duty, the fine and the stopped
leave that came with it. The charge sheet is torn up. A big deed, or enough of them, gives back a
stripe you lost, and a Red Army penal soldier who fights well, or bleeds, is rehabilitated.

**Use things where they lie.** A dressing on the ground, the dead man's morphine or his canteen, a
letter in the mud: `a` lists what's within reach as well as what you carry. The kit screen uses
things in a pile or on a body where they are (`e`), and patching up a wounded man offers the
dressings lying round him. What's left goes back where it was.

**Serve in a famous division.** The new-game screen's Unit line offers the regular divisions,
brigades, regiments and battalions that fought each battle, alongside the special units:
- US: the Big Red One, the 29th's Blue and Gray, the Screaming Eagles, the Old Breed;
- British and Commonwealth: the Desert Rats, the 51st Highland, the Rats of Tobruk, the Red Devils;
- Soviet: Rodimtsev's 13th Guards, the Panfilov men;
- German: Großdeutschland, Panzer Lehr, the 352nd above Omaha;
- the Ariete, the Sendai Division, the Carpathians at Cassino, and more.

Your papers carry the regiments that really served in it, your chain of command is its real
commanders, and veterans know their business. Every soldier of those divisions, yours and the
enemy's, carries the right regiments too.

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
  The machine gunners pick what their rounds can hurt:
  - men, lorries and cars;
  - an open-topped half-track from the side, or men riding on a hull;
  - thin plate their bullets go through;
  - a commander with his head out of the hatch, if there's nothing better.

  They don't spray a buttoned-up tank's armour, and the main gun doesn't fire AP at armour it
  plainly can't get through. It holds the round for a flank shot.
- **Getting in, getting on, getting out.** `e` beside a vehicle gets you in: a seat if it has
  seats (a half-track, a truck), a crew position if you're a tanker or it's empty or abandoned,
  otherwise a handhold on a tank's engine deck with up to five others. Riders are fast and
  exposed: anything that hits the tank, and any burst of fire across its hull, can hit them.
  `e` again gets you down. Right-click a vehicle for the rest.
- **Vehicles are made of parts.** A hit that gets inside breaks particular things, and each takes its
  own work away. A broken track or a smashed transmission: it can't move, but it can still shoot. A
  dead engine: no moving, and the turret is cranked round by hand. A jammed turret ring: the hull has
  to swing to aim. Smashed sights: open sights, and a crew that's half blind buttoned up. A damaged
  gun fires wild; a knocked-out one doesn't fire. A dead radio: no calls. Holed fuel tanks make the next
  hit likelier to start a fire, and a round in the ammunition racks can blow it apart. A crewman hit
  leaves his seat empty until the others pull him clear and one climbs across. After a penetration
  about a third of tanks brew up, a third are abandoned, and a third fight on with what still works.
  Hover over a vehicle to see its state: ours, everything the crew would tell you; the enemy's, only
  what shows from outside (a track lying off, holes, smoke, a head out of the hatch).
- **Seeing from a tank.** The commander with his head out of the hatch sees furthest, and can be
  shot. Buttoned up, it's periscopes, and worse if they're cracked. The gunner sees only down his
  sight; the driver through his visor. AI commanders ride head-out when it's quiet (and, depending on
  their army's habits, in a fight at a distance), and duck down when they're shelled, hit, or there are
  infantry close. Up in a vehicle, or riding on one, you see over maize, sunflowers, undergrowth,
  garden hedges and hay; so does everyone looking at a vehicle.
- **The sun and the moon.** Each battle has its place and its clock, so the sun rises when it really
  rose and a dawn attack starts in the half-light it started in. Twilight widens the view by degrees.
  At night the moon matters: the D-Day drop and El Alamein's barrage went in under a full moon, and
  cloud hides it.
- **Fire support that exists.** Every shell that falls and every aircraft that comes over belongs to
  a unit that is somewhere:
  - batteries of guns (with names, like *C Battery, 12th Field Artillery Battalion* or
    *3./Artillerie-Regiment 13*) at the artillery positions on the war map, with their guns, crews
    and rounds;
  - a mortar platoon with each battalion in the line;
  - named warships off a landing beach (USS Texas off Omaha);
  - squadrons at their airfields, with so many aircraft serviceable.

  A call for fire (`R`, or an AI officer's) goes to a battery that can reach and isn't firing, and it
  fires what it has. With none free, the answer is no. On your map the guns and tubes are there to
  see, and to silence: overrun an enemy gun line and its fire stops. Off your map you hear them
  from their direction before the rounds come in. Batteries fire at the fighting in their reach all
  day, are resupplied from the depots, and are lost when their ground is taken. Guns that fire give
  themselves away to the enemy's sound-rangers and flash-spotters: counter-battery fire follows, from
  the enemy's guns (that was the artillery's business; mortars rarely had the range for gun lines).
  Mortars are harder to locate, until the counter-mortar organisations and radars of 1944; when they
  are found, counter-mortar fire comes from guns and mortars both. Aircraft come from their
  airfield's direction, are shot down by flak, and need an hour on the ground between sorties.
- **The gun line.** As an artilleryman you're the layer on a field gun of a real battery. The fire
  missions come down the wire with the charge, azimuth and elevation worked out from where your gun
  is and where the target is. You lay and fire (Enter), the observer calls corrections from where the
  rounds really fell, and at the end he reports what the mission did, taken off the enemy on the war
  map. As a mortarman in the battalion's mortar platoon, you get your tube's share of its missions,
  and the ammunition bearers bring bombs up from the platoon's carts.
- **Keeping the tanks going.** A thrown track is half an hour's work for four men with a
  sledgehammer and track tools; a dead engine or a damaged gun needs fitters (the motor pool's,
  or the two who ride up with an ammunition truck). Crews only climb out to work when nobody's
  shooting at them and they haven't been hit for a minute. Idle infantry close by walk over and lend
  a hand (three at a time), and so can you (right-click: *Help fix*); leading a squad, `O` has
  *Give the crew a hand*. Racks run dry: when it's quiet, each side
  sends an ammunition truck up from the rear to where its vehicles are short, and they drive to it
  and pass the rounds up, one every eight seconds at best (about 18 minutes for a full load). With
  a radio you can ask for one (`R`). Your sergeant may send you to help with the track or to
  carry a crate of shells up from the truck (right-click the truck: *Take a crate*; right-click the
  tank: *Hand up the shells*); Enter does it. Behind the line the motor sergeant (or the adjutant)
  has **supply runs**: a loaded truck of your own to drive to the tanks in another sector, where
  they've been fighting and are nearly out. It's done when they're loaded.
- **Medicine.** Anyone can pack a wound. Medics and corpsmen do more. Surgeons at aid posts
  operate, and men heal slowly in the line and faster behind it. Allies patch you up and share
  ammunition, and they expect the same of you.
- **Medical evacuation.** Badly hit, out of the enemy's sight and fire, with a radio (yours, your
  tank's, or the radioman beside you), you can call for stretcher-bearers. Four men come on foot from
  the aid post on your ground, or up from the rear, and they can be shot on the way. They get you
  onto the stretcher and carry you back. Then it's your army's evacuation chain (aid post, clearing
  station, field hospital, general hospital) and one to three months in a ward while the war goes
  on. You come back whole, through the replacement system, to a squad at the front. Lose a limb,
  and you're invalided home.
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

**Everyone is armed the way his army armed him.** A rifleman has his rifle and bayonet, an officer
his pistol, a tank crewman a pistol or a sub-machine gun, aircrew the pistol they flew with, a
sailor aboard his rigging knife (the small arms are in the ship's armoury), a cook or a clerk a
carbine. Belt knives come with the army: Ka-Bars for Marines in the Pacific, boot knives for
Germans, the puukko for every Finn, the clasp knife issued to every Commonwealth soldier.

**Medics and the red cross.** In Europe and Africa, American and Commonwealth medics went
unarmed and wore the Red Cross armband (a few carried a pistol anyway), and German Sanitäter
could carry a pistol to defend their wounded. Most armies held their fire on an unarmed medic
wearing the armband, and so does the AI here: a marksman won't pick him out, though bullets and
shells don't read armbands. The Japanese didn't respect it, and on the Eastern Front neither
side did, so medics there went armed, and American medics and Navy corpsmen in the Pacific took
off the red cross and carried carbines. Pick up a rifle and you're a rifleman again, armband or
not. Chaplains were non-combatants too, and go unarmed.

**Every item has a story, and every one is a particular one.** Examine anything (`x` in the kit
screen, or its right-click menu) for its history: what the men who carried it called it and
thought of it, its quirks, where it served. The one in your hands has its own particulars:

- a rifle's maker and serial number (Springfield or Winchester, Inland or Rock-Ola for a carbine,
  "byf" or "bnz" with the year and the Waffenamt eagle for a Kar98k, Izhevsk or Tula, ROF Maltby or
  Lines Bros. for a Sten, the chrysanthemum on an Arisaka), its condition, and sometimes initials
  or notches carved in the butt;
- identity tags in their army's format: the American name, number, tetanus year, blood group and
  religion; the British red and green fibre discs; the German oval zinc Erkennungsmarke that
  snaps in half;
- a letter from home, from a real kind of place, about what was really happening there: war
  bonds and gas rationing, the Blitz and Woolton pie, the night raids and the Volkssturm,
  evacuation beyond the Volga, rice rationing and the thousand-stitch belts;
- photographs, engraved watches and lighters, wedding rings, a dead man's diary;
- newspapers (Stars and Stripes, Yank, Signal, Krasnaya Zvezda) carrying the real headline of
  their side's latest news by the day's date.

Each army carries its own things:

- rations: K- and C-rations and the D bar, compo tins and bully beef, Lend-Lease pork ("the second
  front") and sukhari, the Eiserne Portion and Scho-Ka-Kola, kanpan, galletta;
- drink: SRD rum, the "narkom's hundred grams", schnapps, sake, farmhouse wine;
- stimulants: Pervitin and Benzedrine keep you going, and a second dose too soon costs you;
- makhorka rolled in newspaper, a Zippo or a trench lighter;
- a senninbari or omamori, a signed Hinomaru flag, an Iron Cross, a crucifix, a pin-up;
- a shaving kit, a "housewife" sewing kit, chewing gum.

Houses hold the country's own: wine in France and Italy, vodka in Russia and Poland, schnapps in
Germany, sake in Japan, and their people's letters and photographs.

Open it with `i`. In the kit screen:
- Arrows move, and Enter picks up or puts down (drag and drop with the mouse works too).
- `r` rotates, `e` uses or equips, `l` loads, `u` unloads, `c` counts rounds, `d` drops, `q`
  quick-moves, `x` looks. Right-click an item for everything you can do with it.
- Tab switches between your kit and the other side: the ground, or a body you're searching.
  `[` and `]` switch between piles and bodies within reach. `i` or Esc closes.

## Diegetic interface

What you know is what your soldier knows.
- **Menus come from your `@`**: inventory, item actions, throws, orders and the radio pop out of
  your soldier with a connector line. Item actions chain off the selected line.
  **Tooltips point at the tile** you look at or hover.
- **No hit points.** The body doll on the right shows each part's condition in colour, the
  blood where it's coming out, the dressings and tourniquets on. `@` shows it large, with every
  wound marked. Suppression narrows your vision. Blood loss drains colour from the world. Pain
  flashes red. Blasts deafen you.
- **Pictures, not only words.** The interface draws what your soldier would see or feel. Every
  word is still there beside the picture. Options > Pictures in the interface switches them off.
  - The panel: you in your stance, behind cover as high as the cover really is; the weapon in
    your hands; the rounds in its magazine, brass where you've counted them and faded across the
    range your guess covers; your grenades; the sky as it is; your watch, if you have one; a
    compass needle, or the arrow of your leader's arm; a figure for each man of your section in
    his state.
  - The kit screen: every item drawn, rifle, clips, grenades, the letter from home. Empty slots
    show a faint outline of what goes there.
  - The log: a sign by each line for what kind of news it is (heard, shouted, radio, wounds,
    warnings).
  - Aiming: a sight picture. The man shows only as much as his cover leaves, and the spread of
    your rounds is a circle as big as the hit chance makes it, in the same band as the words.
  - The war map: a map sheet in ink, with woods, hedgerows, villages and roads, and who holds
    each square in grease pencil. Without a map it's a pencil sketch of the ground you've walked.
  - The orders book: how each order reached you (shouted, runner, radio, written).
  - A crewman's panel: the vehicle from above with each seat marked, yours, manned or empty.
  - The new-game screen: the man you're making, in his army's cloth and helmet, with his job's
    weapon.
- **Sound**: gunfire you can't see appears on the map where you think it came from, as
  `crack`, `brrrt` or `BOOM`. Veterans can tell a Garand from a Kar98k.
- **Speech bubbles**: soldiers shout in their own languages ("Handgranate!", "Sanitar!",
  "Tennōheika banzai!").
- **Your gear gates your knowledge.** Without a watch you only know the time of day. Without a
  compass or map, sound directions are vague. Without a map you don't see the objectives or the
  front; you follow your squad leader, who points: "there, NE, 250 yards".
- **Ammo is estimated** ("about half") unless you count it.
- **Hit chances are words** ("a long shot"). You can switch them to numbers in Options.
- **Everything around you** (`V`, as in Cataclysm): a list of the men and vehicles you can see,
  the sounds you've just heard (placed where you think they came from), and whatever's lying on
  the ground in sight, nearest first. Choosing one puts the look cursor on it. `f` or Enter
  fires at an enemy, Enter walks you to a friend or a pile of kit, `x` looks, and `b` raises
  your binoculars, which tell you an MG gunner from a rifleman at a distance.

## Controls

**Every key and click, screen by screen, is in [CONTROLS.md](CONTROLS.md).** In the game, F1 or
`?` shows the same list, opened at the part for where you are, and a line under your orders gives
the keys for whatever's beside you. The ones you'll use most:

| key | action |
|---|---|
| arrows / numpad / `hjklyubn` | move (Shift or `HJKLUN`: run); left-click walks there, finding a way through ground you haven't seen (`x`, then Enter, from the keyboard) |
| Enter | carry out your current order |
| `c` / `p` | crouch / prone |
| `f` or Tab | aim & fire (`Tab` next target, `a` aim longer, `A` aim fully and fire) |
| `r` / `t` / `F` | reload / throw / fire mode |
| `B` / `Y` | patch up / shout (medic!) |
| `i` `g` `d` `w` `a` | kit, pick up, drop, take up a weapon, use something |
| `e` | get into a vehicle beside you (or onto a tank's hull), and out again |
| right-click | everything you can do with that tile, man or vehicle |
| `x` / `V` | look / everything around you in a list |
| `O` / `C` / `R` | squad orders / command / radio |
| `m` / `@` / `P` | war map / yourself / message log |
| `.` / `z` | wait a second / wait until something happens |
| Esc | the menu (save and quit, options) |
| F2 / F3 / F4 | sprites / sound / font |
