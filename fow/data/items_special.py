"""The secret war's kit: silenced weapons, sabotage stores, suitcase radios, cameras and cover papers.

Most of it came out of two places: SOE's Station IX at The Frythe (the Welrod, the Sleeve Gun, the time
pencil, the limpet) and the OSS Research and Development Branch (the High Standard HDM, the Liberator,
the smatchet was British but they loved it).  None of it turns up on an ordinary soldier (freq 0): it
comes in an agent's kit, or down on a parachute in a container.

Imported by items.py before the magazines are made, so these guns get theirs.
"""
from __future__ import annotations

from .defs import ItemType
from .items import CALIBERS, _reg, explosive, gear, gun, melee

# the calibres the ordinary armies didn't use
for _cal, _nm, _w in (("32acp", ".32 ACP (7.65mm Browning)", 0.008), ("22lr", ".22 Long Rifle", 0.004)):
    CALIBERS[_cal] = (_nm, _w)
    _reg(ItemType(f"ammo_{_cal}", f"{_nm} rounds", kind="ammo", cal=_cal, weight=_w, volume=_w * 0.6, glyph="=",
                  color=(200, 180, 90), stack=1, desc=f"Ammunition: {_nm}."))

_SOE = ["uk", "france", "poland", "canada"]

# ---------------------------------------------------------------- guns
gun("welrod", "Welrod Mk II", "pistol", "32acp", 8, 18, 2.4, 9, _SOE + ["usa"], (1943.0, 1950), weight=1.1,
    hands=1, shot=140, reload=160, freq=0, loud=24, sound="a soft cough, like a book dropped on a carpet",
    desc="A bolt-action pistol that is mostly silencer: baffles and rubber wipes the length of the barrel. "
         "Station IX, 1942. At a few feet, in a street with traffic, nobody hears it. One shot, then work the "
         "bolt; the magazine is the grip. For killing sentries and informers - there was no other use for it.")
gun("delisle", "De Lisle carbine", "carbine", "45acp", 7, 26, 0.9, 40, ["uk", "canada"], (1943.5, 1950), weight=3.7,
    shot=120, reload=200, freq=0, loud=30, sound="the click of a bolt, and almost nothing else",
    desc="A Lee-Enfield action rebored for the .45 pistol round inside a huge integral silencer. Quieter than "
         "the bolt working. Commandos took it on raids; a hundred and thirty were made.")
gun("sten_mk2s", "Sten Mk IIS", "smg", "9mm", 32, 20, 2.8, 16, _SOE, (1943.2, 1950), weight=3.5,
    modes=("single", "auto"), burst=5, shot=55, bcost=100, reload=170, jam=0.02, freq=0, loud=44,
    sound="a clatter of the bolt and a string of muffled thuds",
    desc="A Sten with a silencer for a barrel shroud. The bolt is louder than the shot. Fire single rounds, "
         "or it burns out the baffles.")
gun("hdm_pistol", "High Standard HDM", "pistol", "22lr", 10, 12, 2.2, 10, ["usa", "china"], (1944.0, 1950),
    weight=1.1, hands=1, shot=50, reload=110, freq=0, loud=28, sound="a sharp tick, like a stick snapping",
    desc="A .22 target pistol with a silencer, for the OSS. Donovan fired a magazine into a sandbag in the "
         "Oval Office while Roosevelt was dictating; the President never looked up.")
gun("liberator", "FP-45 Liberator", "pistol", "45acp", 1, 24, 4.5, 6, ["usa", "france", "china", "poland"],
    (1942.5, 1950), weight=0.45, hands=1, shot=60, reload=420, freq=0, loud=62, feed="tube",
    sound="the flat bang of a pistol",
    desc="A million made in eleven weeks, at $2.10 each: a stamped-steel single-shot .45 with ten rounds in "
         "the grip and a comic-strip instruction sheet with no words. Kill a sentry, take his rifle. Knock "
         "the empty case out with a stick.")
gun("colt1903", "Colt M1903 Pocket Hammerless", "pistol", "32acp", 8, 16, 2.5, 11, ["usa", "uk", "france"],
    (1903, 1950), weight=0.7, hands=1, shot=50, reload=90, freq=0, loud=56, sound="a pistol shot",
    desc="A slim .32 that doesn't spoil the line of a jacket. General officers carried them; so did OSS and "
         "SOE agents. Flat, reliable, and legal-looking in most of Europe.")
gun("ppk", "Walther PPK", "pistol", "32acp", 7, 16, 2.4, 11, ["germany", "italy", "hungary"], (1931, 1950),
    weight=0.6, hands=1, shot=50, reload=90, freq=0, loud=56, sound="a pistol shot",
    desc="The Polizeipistole Kriminal: a detective's pistol. The Gestapo, the SD, Party officials and "
         "staff officers carried them.")
gun("sleeve_gun", "Welwand 'sleeve gun'", "pistol", "32acp", 1, 18, 3.5, 3, _SOE, (1943.3, 1950), weight=0.5,
    hands=1, shot=60, reload=400, freq=0, loud=26, feed="tube", sound="a faint pop",
    desc="A silenced single-shot tube worn up the sleeve on a lanyard: drop it into your hand, press it "
         "against a man, squeeze. For the moment the papers check goes wrong.")

# ---------------------------------------------------------------- knives and worse
melee("smatchet", "smatchet", 24, ["uk", "usa"], (1942.0, 1950), weight=0.8, freq=0,
      desc="Fairbairn's heavy leaf-bladed knife, a short sword really: the pommel for the jaw, the blade for "
           "everything else. 'The psychological effect of a fine, heavy weapon in the hands of the man who "
           "carries it.'")
melee("garrote", "garrotte", 6, ["uk", "usa", "france", "poland", "germany", "ussr"], (1940.0, 1950), weight=0.05,
      freq=0, tool="garrote",
      desc="A length of piano wire between two wooden toggles. From behind, it's over in seconds and makes no "
           "sound at all.")
melee("knuckleduster", "M1918 trench knife", 17, ["usa"], (1918.0, 1950), weight=0.5, freq=0,
      desc="A triangular spike blade with a knuckleduster guard, from the last war's trench raids.")
melee("cosh", "cosh", 10, ["uk", "usa", "france", "germany"], (1900.0, 1950), weight=0.4, freq=0,
      desc="Lead shot sewn into a leather sock. Puts a man down without killing him - usually.")

# ---------------------------------------------------------------- sabotage stores
explosive("pe_808", "Nobel 808 plastic explosive", "plastic", _SOE + ["usa"], (1940.0, 1950), fuse=10, power=180,
          radius=3, frags=4, pen=90, weight=0.45, freq=0,
          desc="A pound of green plasticine that smells of almonds and gives you a headache. Moulds round a rail "
               "or a transformer. Needs a detonator and a fuse - or a time pencil, and then you walk away.")
explosive("tol_block", "TNT block (400 g)", "block", ["ussr", "germany", "japan", "italy", "finland"], (1930.0, 1950),
          fuse=10, power=170, radius=3, frags=4, pen=70, weight=0.45, freq=0,
          desc="A 400-gram block of cast TNT with a detonator well. The partisans' standard charge: three under a "
               "rail joint takes out a metre of track and derails whatever comes next.")
explosive("limpet", "limpet mine", "magnetic", _SOE + ["usa"], (1940.0, 1950), fuse=10, power=260, radius=3,
          frags=4, pen=160, weight=4.5, freq=0,
          desc="Six magnets round a charge in a steel pot, meant for ships' hulls - and just as happy on a "
               "locomotive or a fuel tank. The delay is an ampoule of acid eating through a celluloid washer.")
gear("time_pencil", "time pencil", "tool", tool="time_pencil", weight=0.02, volume=0.02, glyph="/",
     color=(200, 180, 90), freq=0,
     desc="The No. 10 Delay Switch: squeeze the copper tube to break the ampoule, pull the safety strip, and "
          "the acid starts eating the wire that holds back the striker. The colour of the band gives the "
          "delay: ten minutes, half an hour, two hours. They ran fast in the heat and slow in the cold.")

# ---------------------------------------------------------------- wireless, and talking to aircraft
gear("radio_b2", "Type 3 Mk II ('B2') suitcase set", "tool", tool="wireless", weight=14.5, volume=12, size=(3, 2),
     glyph="&", freq=0,
     desc="SOE's standard transceiver, in an ordinary leather suitcase: transmitter, receiver, power pack, "
          "headphones, a Morse key and seventy feet of aerial to string up in an attic. Five hundred miles "
          "to England. The detector vans can take a bearing in minutes.")
gear("paraset", "Whaddon Mk VII 'Paraset'", "tool", tool="wireless", weight=5.2, volume=5, size=(2, 2), glyph="&",
     freq=0, desc="SIS's little set in a wooden box, small enough to hide under a floorboard. Weak, simple and "
                  "reliable; a pianist could hear London on it through a thunderstorm.")
gear("sstr1", "SSTR-1 suitcase set", "tool", tool="wireless", weight=13.0, volume=11, size=(3, 2), glyph="&",
     freq=0, desc="The OSS's own set, in three waterproof boxes that fit an ordinary suitcase.")
gear("sever_radio", "'Sever' radio", "tool", tool="wireless", weight=2.2, volume=2, size=(2, 1), glyph="&",
     freq=0, desc="The Soviet partisans' and scouts' tiny Morse transceiver, 'the North'. Twenty thousand were "
                  "made in besieged Leningrad; they reached Moscow from four hundred miles behind the lines.")
gear("s_phone", "S-Phone", "tool", tool="sphone", weight=6.5, volume=5, size=(2, 2), glyph="&", freq=0,
     desc="A UHF radiotelephone strapped to your chest: talk the aircraft onto the field in plain speech "
          "from ten miles out, and nobody on the ground more than a mile away can hear either side.")
gear("signal_torch", "signal torch", "tool", tool="torch", weight=0.4, volume=0.3, glyph="/", freq=0,
     desc="A torch with a red filter. Three in a line into the wind for the dropping zone, a fourth at the "
          "end flashing the recognition letter in Morse.")
gear("minox", "Minox camera", "tool", tool="camera", weight=0.13, volume=0.05, glyph="=", freq=0,
     desc="A Latvian miniature camera the size of a finger, fifty exposures on a film no wider than a "
          "matchstick. Hold it steady, a foot and a half from a page.")
gear("one_time_pad", "one-time pad", "tool", tool="code", weight=0.01, volume=0.01, glyph="?", freq=0,
     color=(220, 210, 180), desc="Printed on silk, a sheet to a message, and each sheet burned after use. "
                                 "Unbreakable - if you never use a sheet twice.")
gear("film", "exposed Minox film", "tool", tool="film", weight=0.01, volume=0.01, glyph="=", freq=0,
     desc="A cassette of exposed film. What's on it could be worth a division.")

# ---------------------------------------------------------------- money and papers
gear("francs", "banknotes (francs)", "tool", tool="money", weight=0.001, volume=0.001, glyph="$", stack=500,
     color=(190, 200, 160), freq=0, desc="Hundred-franc notes, some genuine. For rent, for food, for a "
                                         "gendarme who looks the other way.")
gear("zloty", "banknotes (złoty)", "tool", tool="money", weight=0.001, volume=0.001, glyph="$", stack=500,
     color=(190, 200, 160), freq=0, desc="Occupation złoty ('młynarki'), and a few gold dollars sewn into a belt.")
gear("roubles", "banknotes (roubles)", "tool", tool="money", weight=0.001, volume=0.001, glyph="$", stack=500,
     color=(190, 200, 160), freq=0, desc="Roubles, and Reichskreditkassenscheine for where the Germans are.")
for _id, _nm, _d in (
        ("work_permit", "work permit", "An Arbeitskarte stamped by the labour office: you're employed, so "
                                         "you're not to be sent to the Reich."),
        ("rail_pass", "railway pass", "An Ausweis to walk the permanent way: the railways can't run without "
                                       "platelayers."),
        ("travel_permit", "travel permit", "Permission to travel between districts, with the reason typed in."),
        ("curfew_pass", "curfew pass", "Permission to be out after the curfew - a doctor's, a midwife's, a "
                                       "priest's."),
        ("demob_papers", "demobilisation papers", "Proof you were properly discharged in 1940 and aren't a "
                                                  "deserter or an escaped prisoner.")):
    gear(_id, _nm, "tool", tool="cover_papers", weight=0.01, volume=0.01, glyph="?", color=(220, 210, 180),
         freq=0, desc=_d + " Forged, or genuine and stolen.")
gear("spanner", "large spanner", "tool", tool="trade", weight=1.0, volume=0.5, freq=0,
     desc="A platelayer's or an electrician's spanner. It explains you - and it's a weapon.")
gear("breviary", "breviary", "tool", tool="trade", weight=0.3, volume=0.2, freq=0, glyph="?",
     desc="A worn prayer book with a ribbon marker. Soldiers don't search priests closely, mostly.")
gear("doctors_bag", "doctor's bag", "medical", med="kit", power=6, uses=6, weight=2.5, volume=3.0, glyph="+",
     color=(90, 60, 40), freq=0,
     desc="A black leather bag: stethoscope, dressings, morphine, and a false bottom.")
gear("chocolate", "bar of chocolate", "tool", tool="ration", weight=0.1, volume=0.05, freq=0,
     desc="Real chocolate from England. Worth more than money here.")
