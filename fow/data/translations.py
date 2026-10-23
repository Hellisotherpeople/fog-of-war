"""English for every fixed line the non-English armies say (the "Your side speaks English" option).

EN[lang][native line] -> the English a wartime film would dub or subtitle.  Keys are the exact strings
of data/nations.py (shouts), data/ranks.py (ACK, REFUSE), data/phrases.py (P), data/chatter.py (C)
and data/banter.py (BANTER, lines and replies), grouped by source.  Placeholders are kept: {rank} is
still the native rank title, {name} a surname, {sweet} the partner word; {part} should be filled from
PART_EN (the English body-part word), and {give}/{want} from chatter.NOUN["en"].
UNIVERSAL holds only wordless sounds, so it needs no entry.
"""

EN = {
    # ==================== German
    "de": {
        # shouts.attack
        "Vorwärts!": "Forward!",
        "Los, los, los!": "Move, move, move!",
        "Angriff!": "Attack!",
        "Hurra!": "Hurrah!",
        "Marsch, marsch!": "At the double!",
        # shouts.grenade
        "Handgranate!": "Grenade!",
        "Vorsicht, Granate!": "Look out, grenade!",
        "Deckung!": "Take cover!",
        # shouts.medic
        "Sanitäter!": "Medic!",
        "Sani! Sani!": "Medic! Medic!",
        "Hilfe!": "Help!",
        "Mutti!": "Mama!",
        # shouts.reload
        "Nachladen!": "Reloading!",
        "Magazin!": "Magazine!",
        # shouts.contact
        "Feind in Sicht!": "Enemy in sight!",
        "Da! Amis!": "There! Yanks!",
        "Achtung, Feind!": "Look out, enemy!",
        "Iwan kommt!": "Ivan's coming!",
        # shouts.retreat
        "Rückzug!": "Retreat!",
        "Zurück, zurück!": "Back, back!",
        "Absetzen!": "Fall back!",
        # shouts.surrender
        "Nicht schießen! Kamerad!": "Don't shoot! Kamerad!",
        "Hände hoch, ich ergebe mich!": "Hands up - I surrender!",
        # shouts.tank
        "Panzer! Panzerschreck nach vorn!": "Tank! Panzerschreck up front!",
        "Feindpanzer!": "Enemy tank!",
        # shouts.sniper
        "Scharfschütze!": "Sniper!",
        # shouts.mg
        "MG! Volle Deckung!": "Machine gun! Hit the dirt!",
        # shouts.pain
        "Aaah!": "Aaah!",
        "Verdammt!": "Damn it!",
        "Ich bin getroffen!": "I'm hit!",
        "Scheiße!": "Shit!",
        # ACK
        "Jawohl, Herr {rank}!": "Yes, Herr {rank}!",
        "Zu Befehl!": "At your command!",
        "Verstanden!": "Understood!",
        "Jawohl!": "Yes, sir!",
        # REFUSE
        "Unmöglich, Herr {rank}! Wir sind festgenagelt!": "Impossible, Herr {rank}! We're pinned down!",
        "Das ist Selbstmord!": "That's suicide!",
        # P.follow_me
        "Ich übernehme!": "I'm taking over!",
        "Mir nach!": "Follow me!",
        "Alle auf mich hören!": "Listen to me, all of you!",
        # P.ambush_fire
        "Feuer!": "Fire!",
        "Jetzt! Feuer frei!": "Now! Open fire!",
        # P.seen_fire
        "Sie haben uns gesehen - Feuer frei!": "They've seen us - open fire!",
        # P.fire_control
        "Ziel: das MG! Feuer!": "Target, the machine gun! Fire!",
        "Alles auf das MG!": "Everything on the machine gun!",
        "MG halblinks - Schnellfeuer!": "Machine gun, half left - rapid fire!",
        # P.smoke
        "Nebel! Nebel werfen!": "Smoke! Throw smoke!",
        "Nebel vor!": "Smoke forward!",
        # P.flank
        "In die Flanke!": "Hit them in the flank!",
        "Links herum, los!": "Round to the left, go!",
        "Umgehen!": "Go round them!",
        # P.resupplied
        "Alle versorgt? Weiter!": "Everyone stocked up? Move on!",
        # P.medic_comfort
        "Halt durch, ich hab dich.": "Hold on, I've got you.",
        "Das wird wieder.": "You'll be all right.",
        "Bleib bei mir!": "Stay with me!",
        "Nicht hinsehen.": "Don't look.",
        # P.medic_coming
        "Komme!": "Coming!",
        "Halt aus!": "Hang on!",
        "Bleib unten, ich komme!": "Stay down, I'm coming!",
        # P.fire_mission
        "Feuerauftrag! Planquadrat folgt!": "Fire mission! Grid square follows!",
        "Sprenggranaten auf diese Stellung!": "High explosive on that position!",
        "Batterie, Wirkungsfeuer!": "Battery, fire for effect!",
        # P.ammo
        "Munition!": "Ammo!",
        # P.runner
        "Bin unterwegs!": "On my way!",
        "Sofort!": "At once!",
        # P.senior_now
        "Du bist jetzt der Dienstältere. Die Gruppe gehört dir.": "You're the senior man now. The squad's yours.",
        # P.lt_down
        "Der Leutnant ist gefallen!": "The lieutenant's been killed!",
        # P.capt_down
        "Der Hauptmann ist gefallen!": "The captain's been killed!",
        "Der Alte ist tot!": "The Old Man's dead!",
        # P.o_hold
        "Stellung halten! In Deckung!": "Hold your positions! Get under cover!",
        # P.o_dig
        "Eingraben! Wir bleiben hier.": "Dig in! We're staying here.",
        # P.o_move
        "Vorrücken! Los!": "Advance! Go!",
        # P.o_retreat
        "Zurück! Zurück!": "Fall back! Fall back!",
        # P.o_hold_fire
        "Feuer einstellen! Nicht schießen!": "Cease fire! Hold your fire!",
        # P.o_return_fire
        "Nur das Feuer erwidern!": "Return fire only!",
        # P.o_fire_at_will
        "Feuer frei!": "Fire at will!",
        # P.o_ambush
        "Runter! Keiner schießt, bis ich es sage!": "Get down! Nobody fires till I say so!",
        # P.o_suppress
        "Niederhalten! Feuer auf die Stellung!": "Keep their heads down! Fire on that position!",
        # P.o_regroup
        "Sammeln!": "Regroup!",
        # P.o_mount
        "Aufsitzen!": "Mount up!",
        # P.o_dismount
        "Absitzen!": "Dismount!",
        # P.o_resupply
        "Munition fassen!": "Draw ammunition!",
        # P.o_report
        "Meldung!": "Report!",
        # P.t_help
        "Kümmer dich um ihn! Verbinde ihn!": "See to him! Bandage him up!",
        # P.t_ammo
        "Bring ihm Munition!": "Get him some ammo!",
        # P.t_gun
        "An das MG! Los!": "Get on that machine gun! Go!",
        # P.t_down
        "Runter, du Idiot!": "Get down, you idiot!",
        # P.t_come
        "Hierher! Zu mir!": "Over here! To me!",
        # P.t_fire
        "Schieß doch! Feuer!": "Shoot, will you! Fire!",
        # P.t_dig
        "Eingraben! Los!": "Dig in! Move!",
        # P.t_runner
        "Bring das zu ihm! Lauf!": "Take this to him! Run!",
        # P.t_fetch
        "Hol Munition vom Lager!": "Fetch ammo from the dump!",
        # P.t_scout
        "Sieh nach, was da vorne ist. Leise.": "See what's up ahead. Quietly.",
        # P.t_escort
        "Bring die Gefangenen nach hinten.": "Take the prisoners to the rear.",
        # P.praise
        "Gut gemacht.": "Well done.",
        "Brav.": "Good lad.",
        # P.rebuke
        "Das war ein Befehl!": "That was an order!",
        "Bist du taub?": "Are you deaf?",
        # P.ff_rebuke
        "Pass auf, wohin du schießt!": "Watch where you're shooting!",
        # P.arrest
        "Waffe weg! Sofort!": "Drop your weapon! Now!",
        # P.murder
        "Er schießt auf die eigenen Leute! Schnappt ihn!": "He's shooting at our own men! Grab him!",
        # P.pow_shot
        "Der hatte sich ergeben!": "He'd surrendered!",
        # P.share_ammo
        "Hier, nimm!": "Here, take it!",
        # C.hit_light
        "Scheiße! Getroffen!": "Shit! I'm hit!",
        "Nur ein Streifschuss - weiter!": "Just a graze - keep going!",
        # C.hit_bad
        "Ich bin schwer getroffen!": "I'm hit bad!",
        "Oh Gott, oh Gott!": "Oh God, oh God!",
        "Sanitäter! SANITÄTER!": "Medic! MEDIC!",
        "Hilfe! Helft mir doch!": "Help! Somebody help me!",
        # C.part
        "Mein {part}! Mein {part}!": "My {part}! My {part}!",
        "Oh Gott, mein {part}!": "Oh God, my {part}!",
        "Mein {part} - ich spür's nicht mehr!": "My {part} - I can't feel it any more!",
        # C.legs
        "Ich kann nicht laufen!": "I can't walk!",
        "Lasst mich nicht liegen!": "Don't leave me lying here!",
        "Mein Bein ist ab - oh Gott!": "My leg's gone - oh God!",
        # C.gut
        "Bauchschuss... oh Gott...": "Gut shot... oh God...",
        "Wasser... gebt mir Wasser...": "Water... give me water...",
        "Das war's... Bauchschuss...": "That's it... gut shot...",
        # C.chest
        "Ich krieg keine Luft... keine Luft!": "I can't breathe... can't breathe!",
        "Lungenschuss... ich ersticke!": "Hit in the lung... I'm choking!",
        # C.eyes
        "Meine Augen! Ich seh nichts mehr!": "My eyes! I can't see!",
        "Ich bin blind!": "I'm blind!",
        # C.bleeding
        "Ich verblute! Helft mir!": "I'm bleeding to death! Help me!",
        "So viel Blut... so viel Blut...": "So much blood... so much blood...",
        "Abbinden! Bindet es ab!": "Tourniquet! Tie it off!",
        # C.dying
        "Mutti... Mutti...": "Mama... Mama...",
        "Ich will nicht sterben... nicht hier...": "I don't want to die... not here...",
        "Sagt meiner Mutter...": "Tell my mother...",
        "Mir ist so kalt...": "I'm so cold...",
        "Vater unser, der du bist im Himmel...": "Our Father, who art in heaven...",
        # C.shock
        "Geht schon... geht schon...": "I'm all right... I'm all right...",
        "Ich ruh mich nur aus...": "I'm just resting...",
        "Wird's dunkel?": "Is it getting dark?",
        # C.buddy_down
        "{name}! {name} ist getroffen!": "{name}! {name}'s hit!",
        "Sie haben {name} erwischt!": "They got {name}!",
        "{name} ist verwundet! Sani!": "{name}'s wounded! Medic!",
        "Nein! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} ist tot!": "{name}'s dead!",
        "Oh Gott... {name}...": "Oh God... {name}...",
        "{name} ist gefallen!": "{name}'s been killed!",
        "Die Schweine haben {name} umgebracht!": "The swine have killed {name}!",
        # C.comfort
        "Halt durch, Kamerad. Halt durch.": "Hang on, comrade. Hang on.",
        "Der Sani kommt gleich.": "The medic's on his way.",
        "Bleib bei mir! Sieh mich an!": "Stay with me! Look at me!",
        "Heimatschuss, Junge. Du fährst nach Hause.": "That's your ticket home, lad. You're going home.",
        # C.under_fire
        "Woher kommt das?!": "Where's that coming from?!",
        "Ich seh sie nicht!": "I can't see them!",
        "Runter! Kopf runter!": "Get down! Heads down!",
        "Herrgott!": "Good God!",
        "Wo sind die?!": "Where are they?!",
        # C.moving
        "Sprung auf!": "Up and go!",
        "Ich geh vor!": "I'm going forward!",
        "Gib mir Feuerschutz!": "Cover me!",
        # C.covering
        "Feuerschutz!": "Covering fire!",
        "Ich geb dir Deckung!": "I'll cover you!",
        "Los, ich decke!": "Go, I've got you covered!",
        # C.out_of_ammo
        "Keine Munition mehr!": "I'm out of ammo!",
        "Munition! Ich brauch Munition!": "Ammo! I need ammo!",
        "Letztes Magazin!": "Last magazine!",
        # C.got_him
        "Hab ihn!": "Got him!",
        "Der ist erledigt!": "He's finished!",
        "Einer weniger!": "One less!",
        # C.shelling
        "Volle Deckung!": "Hit the dirt!",
        "Granatwerfer! Runter!": "Mortars! Get down!",
        "Artillerie!": "Artillery!",
        "Da kommt was!": "Incoming!",
        # C.panic
        "Ich kann nicht mehr!": "I can't take any more!",
        "Wir gehen hier alle drauf!": "We're all going to die here!",
        "Ich hau ab!": "I'm getting out of here!",
        "Ich will nach Hause...": "I want to go home...",
        # C.nco_fire
        "Weiterfeuern!": "Keep firing!",
        "Ziele wählen!": "Pick your targets!",
        "Kurze Feuerstöße!": "Short bursts!",
        "Schießt doch!": "Shoot, damn you!",
        # C.nco_spread
        "Auseinander! Eine Granate und ihr seid alle hin!": "Spread out! One grenade and you're all done for!",
        "Abstand halten!": "Keep your spacing!",
        # C.nco_up
        "Auf! Marsch!": "Up! Move!",
        "Hier könnt ihr nicht bleiben!": "You can't stay here!",
        "Hoch mit euch!": "On your feet!",
        # C.medic_coming
        "Ich komme! Halt aus!": "I'm coming! Hang on!",
        "Bin gleich da!": "Almost there!",
        # C.offer_smoke
        "Zigarette?": "Cigarette?",
        "Willst du eine?": "Want one?",
        "Hier, nimm eine.": "Here, have one.",
        # C.thanks
        "Danke, Kamerad.": "Thanks, comrade.",
        "Du bist ein Engel.": "You're an angel.",
        "Vergelt's Gott.": "God bless you.",
        # C.trade_offer
        "Tausch? Mein {give} gegen dein {want}?": "Trade you {give} for {want}?",
        "Hast du {want}? Ich hab {give}.": "You got {want}? I've got {give}.",
        # C.trade_yes
        "Abgemacht.": "Deal.",
        "Gemacht.": "Done.",
        "Na gut.": "Oh, all right.",
        # C.trade_no
        "Kommt nicht in Frage.": "Out of the question.",
        "Nee, behalt's.": "Nah, keep it.",
        "Was soll ich damit?": "What would I do with that?",
        # C.photo
        "Das ist meine {sweet}.": "That's my {sweet}.",
        "Mein Junge. Hab ihn noch nie gesehen.": "My boy. Never seen him yet.",
        "Meine Eltern, zu Hause.": "My folks, back home.",
        # C.letter_good
        "Sie wartet auf mich.": "She's waiting for me.",
        "Mutter schreibt, es geht allen gut.": "Mother writes that everyone's well.",
        # C.letter_bad
        "...Unser Haus ist weg. Ausgebombt.": "...Our house is gone. Bombed out.",
        "Mein Bruder ist gefallen. Bei Orel.": "My brother's been killed. At Orel.",
        # C.pray
        "Herr, sei bei mir...": "Lord, be with me...",
        "Lieber Gott, lass mich heimkommen.": "Dear God, let me get home.",
        # C.mourn
        "Ruhe sanft, {name}.": "Rest in peace, {name}.",
        "Tut mir leid, Kamerad.": "I'm sorry, comrade.",
        "Ich schreib deiner Mutter, {name}.": "I'll write to your mother, {name}.",
        # C.souvenir
        "Guck mal, was ich gefunden hab!": "Look what I found!",
        "Beute!": "Loot!",
        # C.steady
        "Ruhig. Atme. Wird schon.": "Easy. Breathe. You'll be all right.",
        "Bleib bei mir. Wir schaffen das.": "Stay with me. We'll make it.",
        # C.feet
        "Socken wechseln! Ich will keine Erfrierungen sehen.": "Change your socks! I don't want to see any frostbite.",
        "Iss was, das ist ein Befehl.": "Eat something, that's an order.",
        "Gewehr reinigen, aber dalli!": "Clean your rifle, and make it snappy!",
        # BANTER
        "Wenn ich nur wüsste, wo wir sind.": "If only I knew where we were.",
        "Frag den Leutnant. Der weiß es auch nicht.": "Ask the lieutenant. He doesn't know either.",
        "Schon wieder Erbsensuppe.": "Pea soup again.",
        "Sei froh, dass es überhaupt was gibt.": "Be glad there's anything at all.",
        "Hast du Post von zu Hause?": "Any mail from home?",
        "Meine Mutter schreibt, die Bomben kommen jetzt jede Nacht.": "My mother writes the bombers come every night now.",
        "Weihnachten sind wir zu Hause, hieß es.": "Home by Christmas, they said.",
        "Sie haben nicht gesagt, welches Weihnachten.": "They didn't say which Christmas.",
        "Hast du 'ne Zigarette?": "Got a cigarette?",
        "Die letzte. Teilen wir.": "My last one. We'll share it.",
        "Meine Füße sind seit Wochen nass.": "My feet have been wet for weeks.",
        "Meine sind seit Wochen tot.": "Mine have been dead for weeks.",
        "Glaubst du, das hat noch Sinn?": "You think there's any point any more?",
        "Halt den Mund. Sowas sagt man nicht laut.": "Shut your mouth. You don't say that out loud.",
        "Der Feldwebel schnarcht wie ein Panzer.": "The sergeant snores like a tank.",
        "Und riecht wie einer.": "And smells like one.",
        "Nach dem Krieg mache ich eine Kneipe auf.": "After the war I'm opening a bar.",
        "Ich komme jeden Abend.": "I'll be in every night.",
        "Es ist so still.": "It's so quiet.",
        "Sag das nicht. Nie.": "Don't say that. Ever.",
        "Was isst du als Erstes zu Hause?": "What's the first thing you'll eat back home?",
        "Mutters Sauerbraten. Und dann schlafe ich eine Woche.": "Mother's pot roast. Then I'll sleep for a week.",
        "Die Amis haben alles. Sogar Schokolade.": "The Yanks have everything. Even chocolate.",
        "Und wir haben Durchhalteparolen.": "And we've got slogans about holding out.",
    },
    # ==================== Russian (romanised)
    "ru": {
        # shouts.attack
        "Urraaa!": "Hurraaah!",
        "Za Rodinu!": "For the Motherland!",
        "Vperyod!": "Forward!",
        "Ni shagu nazad!": "Not one step back!",
        # shouts.grenade
        "Granata!": "Grenade!",
        "Lozhis'!": "Get down!",
        # shouts.medic
        "Sanitar!": "Medic!",
        "Pomogite!": "Help!",
        "Mama!": "Mama!",
        # shouts.reload
        "Perezaryazhayu!": "Reloading!",
        # shouts.contact
        "Fritzy!": "Fritzes!",
        "Nemtsy!": "Germans!",
        "Vrag vperedi!": "Enemy ahead!",
        # shouts.retreat
        "Otkhodim!": "Fall back!",
        "Nazad!": "Back!",
        # shouts.surrender
        "Ne strelyay! Sdayus'!": "Don't shoot! I surrender!",
        # shouts.tank
        "Tank! Protivotankovoye!": "Tank! Anti-tank!",
        # shouts.sniper
        "Snayper!": "Sniper!",
        # shouts.mg
        "Pulemyot! Lozhis'!": "Machine gun! Get down!",
        # shouts.pain
        "Aaa!": "Aaah!",
        "Blyad'!": "Fuck!",
        "Ranen!": "I'm hit!",
        # ACK
        "Tak tochno!": "Yes, sir!",
        "Est'!": "Will do!",
        "Slushayus', tovarishch komandir!": "At your orders, Comrade Commander!",
        "Ponyal!": "Got it!",
        # REFUSE
        "Nevozmozhno, tovarishch komandir! Prizhali!": "Impossible, Comrade Commander! We're pinned down!",
        "Nas vsekh tut polozhat!": "They'll lay every one of us out here!",
        # P.follow_me
        "Ya komanduyu!": "I'm in command!",
        "Za mnoy!": "Follow me!",
        "Slushay moyu komandu!": "Listen to my orders!",
        # P.ambush_fire
        "Ogon'!": "Fire!",
        "Seychas! Ogon'!": "Now! Fire!",
        "Bey ikh!": "Let them have it!",
        # P.seen_fire
        "Nas zametili - ogon'!": "They've spotted us - fire!",
        # P.fire_control
        "Po pulemyotu - ogon'!": "At the machine gun - fire!",
        "Vse po pulemyotu!": "Everyone on the machine gun!",
        "Pulemyot sleva - ogon'!": "Machine gun on the left - fire!",
        # P.smoke
        "Dym! Stav' dym!": "Smoke! Lay smoke!",
        "Dymovuyu!": "Smoke grenade!",
        # P.flank
        "Obkhodi s flanga!": "Go round the flank!",
        "Zakhodi sleva!": "Come in from the left!",
        "V obkhod!": "Outflank them!",
        # P.resupplied
        "Vse poluchili? Poshli!": "Everyone got theirs? Let's go!",
        # P.medic_comfort
        "Derzhis', ya zdes'.": "Hold on, I'm here.",
        "Vsyo budet khorosho.": "Everything will be all right.",
        "Ne smotri tuda!": "Don't look at it!",
        # P.medic_coming
        "Idu!": "Coming!",
        "Derzhis'!": "Hold on!",
        "Lezhi, ya idu!": "Stay down, I'm coming!",
        # P.fire_mission
        "Ogon' artillerii!": "Artillery fire!",
        "Batareya, ogon'!": "Battery, fire!",
        "Davay artilleriyu!": "Call in the artillery!",
        # P.ammo
        "Patrony!": "Ammo!",
        # P.runner
        "Begu!": "On my way!",
        "Uzhe begu!": "Already going!",
        # P.senior_now
        "Ty teper' starshiy. Otdeleniye tvoyo.": "You're senior now. The squad's yours.",
        # P.lt_down
        "Leytenanta ubili!": "They've killed the lieutenant!",
        # P.capt_down
        "Kapitana ubili!": "They've killed the captain!",
        "Kombata ubili!": "They've killed the battalion commander!",
        # P.o_hold
        "Stoyat'! V ukrytiye!": "Hold fast! Get into cover!",
        # P.o_dig
        "Okopat'sya!": "Dig in!",
        # P.o_move
        "Vpered! Bystro!": "Forward! Quickly!",
        # P.o_retreat
        "Otkhodim! Nazad!": "Fall back! Back!",
        # P.o_hold_fire
        "Ne strelyat'!": "Hold your fire!",
        # P.o_return_fire
        "Strelyat' tol'ko v otvet!": "Return fire only!",
        # P.o_fire_at_will
        "Ogon' po gotovnosti!": "Fire when ready!",
        # P.o_ambush
        "Lozhis'! Bez komandy ne strelyat'!": "Get down! Nobody fires without the order!",
        # P.o_suppress
        "Prizhmi ikh ognyom!": "Pin them down with fire!",
        # P.o_regroup
        "Ko mne! Sobrat'sya!": "To me! Form up!",
        # P.o_mount
        "Po mashinam!": "Mount up!",
        # P.o_dismount
        "Speshit'sya!": "Dismount!",
        # P.o_resupply
        "Za boepripasami!": "Go and get ammunition!",
        # P.o_report
        "Doklad!": "Report!",
        # P.t_help
        "Perevyazhi ego!": "Bandage him!",
        # P.t_ammo
        "Podai emu patrony!": "Pass him some ammo!",
        # P.t_gun
        "K pulemyotu!": "Man the machine gun!",
        # P.t_down
        "Lozhis', durak!": "Get down, you fool!",
        # P.t_come
        "Ko mne! Bystro!": "To me! Quick!",
        # P.t_fire
        "Strelyay!": "Shoot!",
        # P.t_dig
        "Okapyvaysya!": "Dig yourself in!",
        # P.t_runner
        "Otnesi emu! Begom!": "Take it to him! On the double!",
        # P.t_fetch
        "Begi za patronami!": "Run and get ammo!",
        # P.t_scout
        "Shodi, posmotri. Tikho.": "Go and take a look. Quietly.",
        # P.t_escort
        "Otvedi plennykh v tyl.": "Take the prisoners to the rear.",
        # P.praise
        "Molodets.": "Good man.",
        "Khorosho.": "Good.",
        # P.rebuke
        "Eto prikaz!": "That's an order!",
        "Ty oglokh?": "Have you gone deaf?",
        # P.ff_rebuke
        "Kuda strelyaesh?!": "What are you shooting at?!",
        # P.arrest
        "Brosay oruzhie!": "Drop your weapon!",
        # P.murder
        "On strelyaet po svoim! Vzyat' ego!": "He's shooting at our own! Seize him!",
        # P.share_ammo
        "Derzhi!": "Here, take it!",
        # C.hit_light
        "Menya zadelo!": "I'm hit!",
        "Chyort! Ranen!": "Damn! I'm wounded!",
        "Yob tvoyu... zadelo!": "Motherf... I'm hit!",
        "Erunda, tsarapina - vperyod!": "It's nothing, just a scratch - forward!",
        # C.hit_bad
        "Tyazhelo ranen!": "I'm badly wounded!",
        "Bozhe moi, bozhe!": "My God, oh God!",
        "Sanitar! SANITAR!": "Medic! MEDIC!",
        "Pomogite! Pomogite mne!": "Help! Help me!",
        # C.part
        "Moya {part}! Moya {part}!": "My {part}! My {part}!",
        "Bozhe, {part}!": "God, my {part}!",
        "{part} - ne chuvstvuyu!": "My {part} - I can't feel it!",
        # C.legs
        "Ne mogu idti!": "I can't walk!",
        "Ne brosaite menya!": "Don't leave me!",
        "Nogi net... nogi net!": "My leg's gone... my leg's gone!",
        # C.gut
        "V zhivot... bozhe...": "In the gut... God...",
        "Vody... dai vody...": "Water... give me water...",
        "Vsyo... v zhivot...": "That's it... in the gut...",
        # C.chest
        "Dyshat' ne mogu... ne mogu!": "I can't breathe... I can't!",
        "V grud'... zadykhayus'!": "In the chest... I'm choking!",
        # C.eyes
        "Glaza! Nichego ne vizhu!": "My eyes! I can't see a thing!",
        "Ya oslep!": "I'm blind!",
        # C.bleeding
        "Istekayu krov'yu! Pomogite!": "I'm bleeding out! Help!",
        "Stol'ko krovi... stol'ko krovi...": "So much blood... so much blood...",
        "Zhgut! Dayte zhgut!": "Tourniquet! Give me a tourniquet!",
        # C.dying
        "Mama... mamochka...": "Mama... dear Mama...",
        "Ne khochu umirat'... ne zdes'...": "I don't want to die... not here...",
        "Skazhite mame...": "Tell my mother...",
        "Kholodno... pochemu tak kholodno...": "Cold... why is it so cold...",
        "Gospodi, pomilui...": "Lord, have mercy...",
        # C.shock
        "Nichego... nichego...": "It's nothing... it's nothing...",
        "Ya prosto otdokhnu...": "I'll just rest a bit...",
        "Temneyet?": "Is it getting dark?",
        # C.buddy_down
        "{name}! {name} ranen!": "{name}! {name}'s wounded!",
        "{name} zadelo!": "{name}'s hit!",
        "Nashego ranili! {name}!": "They've hit one of ours! {name}!",
        "Net! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} ubit!": "{name}'s been killed!",
        "Bozhe... {name}...": "God... {name}...",
        "{name} bol'she net.": "{name}'s gone.",
        "Ubili {name}, svolochi!": "The bastards killed {name}!",
        # C.comfort
        "Derzhis', bratok. Derzhis'.": "Hold on, brother. Hold on.",
        "Sanitar uzhe idyot.": "The medic's on his way.",
        "Smotri na menya! Ne zasypai!": "Look at me! Don't fall asleep!",
        # C.under_fire
        "Otkuda b'yut?!": "Where's it coming from?!",
        "Ne vizhu ikh!": "I can't see them!",
        "Lozhis'! Golovu nizhe!": "Get down! Keep your head down!",
        "Ukrytie!": "Take cover!",
        "Mat' tvoyu!": "Son of a bitch!",
        # C.moving
        "Perebezhka!": "Moving up!",
        "Poshyol!": "Going!",
        "Prikroi!": "Cover me!",
        # C.covering
        "Prikryvayu!": "Covering!",
        "Davai, prikroyu!": "Go on, I'll cover you!",
        # C.out_of_ammo
        "Patronov net!": "I'm out of ammo!",
        "Patrony! Dayte patrony!": "Ammo! Give me ammo!",
        "Posledniy disk!": "Last drum!",
        # C.got_him
        "Est' odin!": "Got one!",
        "Gotov!": "He's done for!",
        "Snyal ego!": "Got him!",
        # C.shelling
        "Vozdukh! Lozhis'!": "Aircraft! Get down!",
        "Minomyoty! Lozhis'!": "Mortars! Get down!",
        "Artobstrel!": "Barrage!",
        # C.panic
        "Ne mogu bol'she!": "I can't take any more!",
        "Vsekh pereb'yut!": "They'll kill us all!",
        "Bezhim!": "Run for it!",
        "Khochu domoi...": "I want to go home...",
        # C.nco_fire
        "Ogon'! Ne prekrashchat'!": "Fire! Don't let up!",
        "Bei ikh!": "Hit them!",
        "Korotkimi!": "Short bursts!",
        "Strelyai, chyort tebya deri!": "Shoot, damn you!",
        # C.nco_spread
        "Rassredotochit'sya!": "Spread out!",
        "Ne kuchkovat'sya!": "Don't bunch up!",
        # C.nco_up
        "Vstat'! Vperyod!": "On your feet! Forward!",
        "Tut nel'zya ostavat'sya!": "We can't stay here!",
        # C.medic_coming
        "Idu! Derzhis'!": "Coming! Hold on!",
        "Seichas!": "Right away!",
        # C.offer_smoke
        "Zakurish'?": "Smoke?",
        "Na, kuri.": "Here, have a smoke.",
        "Mahorochki?": "Bit of tobacco?",
        # C.thanks
        "Spasibo, bratok.": "Thanks, brother.",
        "Vyruchil.": "You saved my life.",
        # C.trade_offer
        "Menyaemsya? {give} na {want}?": "Trade you {give} for {want}?",
        "Est' {want}? U menya {give}.": "You got {want}? I've got {give}.",
        # C.trade_yes
        "Idyot.": "Deal.",
        "Dogovorilis'.": "Agreed.",
        "Lady.": "It's a deal.",
        # C.trade_no
        "Ne poidyot.": "Nothing doing.",
        "Ne, ostav' sebe.": "Nah, keep it.",
        "Na chto mne eto?": "What do I want with that?",
        # C.photo
        "Eto moya {sweet}.": "That's my {sweet}.",
        "Syn. Eshchyo ne videl ego.": "My son. I haven't seen him yet.",
        "Mama s papoi, doma.": "My mother and father, back home.",
        # C.letter_good
        "Zhdyot. Pishet, chto zhdyot.": "She's waiting. She writes that she's waiting.",
        "Mama pishet, vse zhivy.": "Mother writes that everyone's alive.",
        # C.letter_bad
        "...Derevnyu sozhgli.": "...They burned the village.",
        "Brat pogib. Pod Rzhevom.": "My brother's dead. At Rzhev.",
        # C.pray
        "Gospodi, spasi i sokhrani...": "Lord, save and protect me...",
        "Bogoroditse Devo, raduisya...": "Hail, O Virgin Mother of God...",
        # C.mourn
        "Spi spokoino, {name}.": "Sleep in peace, {name}.",
        "Prosti, bratok.": "Forgive me, brother.",
        "Napishu tvoei materi, {name}.": "I'll write to your mother, {name}.",
        # C.souvenir
        "Smotri - trofei!": "Look - a trophy!",
        "Chasy! Tseliye chasy!": "A watch! Not a scratch on it!",
        # C.steady
        "Spokoino. Dyshi. Vsyo budet.": "Easy. Breathe. It'll be all right.",
        "Derzhis' ryadom. Proryomsya.": "Stay close. We'll break through.",
        # C.feet
        "Portyanki perematai! Nogi beregi.": "Rewrap your footcloths! Look after your feet.",
        "Poesh' - eto prikaz.": "Eat - that's an order.",
        "Vintovku pochisti!": "Clean your rifle!",
        # BANTER
        "Pis'mo iz doma bylo?": "Any letter from home?",
        "Mama pishet, chto derevnyu sozhgli.": "Mother writes that they burned the village.",
        "Opyat' kasha.": "Porridge again.",
        "Molchi. Vchera i kashi ne bylo.": "Quiet. Yesterday there wasn't even porridge.",
        "Daleko eshche do Berlina?": "How far is it still to Berlin?",
        "Dal'she, chem do doma.": "Farther than home.",
        "Est' zakurit'?": "Got a smoke?",
        "Makhorka. Poslednyaya.": "Cheap tobacco. The last of it.",
        "Posle voyny poedu na more.": "After the war I'm going to the seaside.",
        "A ya prosto vysplyus'.": "Me, I'm just going to sleep.",
        "Tikho kak-to.": "Awfully quiet.",
        "Ne govori tak. Nikogda.": "Don't say that. Ever.",
        "Nogi uzhe ne chuvstvuyu.": "I can't feel my feet any more.",
        "Znachit, eshche zhivoy.": "Then you're still alive.",
        "Politruk opyat' rechi govorit.": "The commissar's making speeches again.",
        "Pust' govorit. Lish' by ne v ataku.": "Let him talk. As long as it's not an attack.",
        "Kak dumaesh', skoro konets?": "Think it'll be over soon?",
        "Kogda Fritsev vsekh ne stanet.": "When there's no Fritzes left.",
        "Snilsya mne khleb, goryachiy.": "I dreamed of bread. Hot bread.",
        "Ne rasskazyvay. Ne muchay.": "Don't tell me. Don't torture me.",
    },
    # ==================== Japanese (Hepburn romaji)
    "ja": {
        # shouts.attack
        "Tennōheika banzai!": "Long live the Emperor!",
        "Totsugeki!": "Charge!",
        "Susume!": "Advance!",
        "Banzai!": "Banzai!",
        # shouts.grenade
        "Shuryūdan!": "Grenade!",
        "Fusero!": "Get down!",
        # shouts.medic
        "Eisei-hei!": "Medic!",
        "Okāsan!": "Mother!",
        # shouts.reload
        "Sōten!": "Reloading!",
        # shouts.contact
        "Teki da!": "Enemy!",
        "Beihei!": "Americans!",
        "Teki shūrai!": "The enemy's attacking!",
        # shouts.retreat
        "Tettai!": "Withdraw!",
        # shouts.surrender
        "Utsu na!": "Don't shoot!",
        # shouts.tank
        "Sensha da!": "Tank!",
        # shouts.sniper
        "Sogekihei!": "Sniper!",
        # shouts.mg
        "Kikanjū! Fusero!": "Machine gun! Get down!",
        # shouts.pain
        "Guaah!": "Gaaah!",
        "Itai!": "It hurts!",
        "Yarareta!": "I'm hit!",
        # ACK
        "Hai!": "Yes, sir!",
        "Ryōkai!": "Understood!",
        "Wakarimashita!": "Understood, sir!",
        "Hai, {rank}-dono!": "Yes, {rank}!",
        # P.follow_me
        "Ore ga shiki o toru!": "I'm taking command!",
        "Ore ni tsuzuke!": "Follow me!",
        "Tsuzuke!": "Follow!",
        # P.ambush_fire
        "Ute!": "Fire!",
        "Ima da! Ute!": "Now! Fire!",
        # P.seen_fire
        "Mitsukatta! Ute!": "We've been spotted! Fire!",
        # P.fire_control
        "Kikanjū o ute!": "Fire on the machine gun!",
        "Zen'in, kikanjū o nerae!": "Everyone, aim at the machine gun!",
        # P.smoke
        "Enmaku!": "Smoke!",
        "Enmakudan o nagero!": "Throw smoke!",
        # P.flank
        "Sokumen ni maware!": "Get round their flank!",
        "Hidari kara mawarikome!": "Go round from the left!",
        # P.resupplied
        "Minna junbi wa ii ka? Iku zo!": "Everyone ready? Let's go!",
        # P.medic_comfort
        "Shikkari shiro!": "Be strong!",
        "Daijōbu da.": "You're all right.",
        "Ganbare!": "Hang in there!",
        # P.medic_coming
        "Ima iku!": "Coming!",
        "Mattero!": "Wait for me!",
        # P.fire_mission
        "Hōgeki yōsei!": "Request artillery fire!",
        "Hōhei, ute!": "Artillery, fire!",
        # P.ammo
        "Tama!": "Ammo!",
        # P.runner
        "Hai! Itte mairimasu!": "Yes, sir! On my way!",
        # P.senior_now
        "Kisama ga sen'in da. Buntai wa makaseta.": "You're the senior man now. The squad is yours.",
        # P.lt_down
        "Shōtaichō ga yarareta!": "They got the platoon commander!",
        # P.capt_down
        "Chūtaichō ga yarareta!": "They got the company commander!",
        # P.o_hold
        "Koko o mamore! Fuse!": "Hold this position! Get down!",
        # P.o_dig
        "Zangō o hore!": "Dig in!",
        # P.o_move
        "Zenshin! Isoge!": "Advance! Hurry!",
        # P.o_hold_fire
        "Uta na!": "Hold your fire!",
        # P.o_return_fire
        "Uchikaesu dake da!": "Return fire only!",
        # P.o_fire_at_will
        "Kakko ni ute!": "Fire at will!",
        # P.o_ambush
        "Fusero! Meirei made uta na!": "Get down! Don't fire until ordered!",
        # P.o_suppress
        "Ute, osaekome!": "Fire, pin them down!",
        # P.o_regroup
        "Shūgō!": "Assemble!",
        # P.o_mount
        "Jōsha!": "Mount up!",
        # P.o_dismount
        "Kōsha!": "Dismount!",
        # P.o_resupply
        "Dan'yaku o hokyū shiro!": "Replenish your ammunition!",
        # P.o_report
        "Hōkoku seyo!": "Report!",
        # P.t_help
        "Teate shiro!": "Patch him up!",
        # P.t_ammo
        "Tama o motte ike!": "Take him ammo!",
        # P.t_gun
        "Kikanjū ni tsuke!": "Man the machine gun!",
        # P.t_down
        "Fusero, baka!": "Get down, you idiot!",
        # P.t_come
        "Koko ni kaere!": "Come back here!",
        # P.t_fire
        "Ute! Ute!": "Fire! Fire!",
        # P.t_dig
        "Hore!": "Dig!",
        # P.t_runner
        "Kore o todokero! Hashire!": "Deliver this! Run!",
        # P.t_fetch
        "Tama o tottekoi!": "Go and get ammo!",
        # P.t_scout
        "Teisatsu shite koi.": "Go and scout ahead.",
        # P.t_escort
        "Horyo o kōhō e tsurete ike.": "Take the prisoners to the rear.",
        # P.praise
        "Yoku yatta.": "Well done.",
        # P.rebuke
        "Meirei da!": "That's an order!",
        # P.ff_rebuke
        "Doko o utte iru!": "What are you shooting at!",
        # P.arrest
        "Jū o sutero!": "Drop your gun!",
        # P.murder
        "Mikata o utte iru! Tsukamaero!": "He's shooting our own men! Seize him!",
        # P.share_ammo
        "Hora, tore!": "Here, take it!",
        # C.hit_light
        "Kuso! Utareta!": "Shit! I'm shot!",
        "Kasuri kizu da - susume!": "Just a graze - keep moving!",
        # C.hit_bad
        "Omoi zo! Yarareta!": "It's bad! I'm hit!",
        "Eisei-hei! EISEI-HEI!": "Medic! MEDIC!",
        "Tasukete! Dareka!": "Help me! Somebody!",
        # C.part
        "{part} ga! {part} ga!": "My {part}! My {part}!",
        "{part} o yarareta!": "They got me in the {part}!",
        # C.legs
        "Arukenai! Arukenai!": "I can't walk! I can't walk!",
        "Oite ikanaide kure!": "Don't leave me behind!",
        # C.gut
        "Hara o... yarareta...": "In the belly... they got me...",
        "Mizu... mizu o kure...": "Water... give me water...",
        # C.chest
        "Iki ga... iki ga dekinai!": "I can't... I can't breathe!",
        # C.eyes
        "Me ga! Mienai!": "My eyes! I can't see!",
        # C.bleeding
        "Chi ga tomaranai!": "The bleeding won't stop!",
        "Chi ga... konna ni...": "So much... blood...",
        # C.dying
        "Okaa-san... okaa-san...": "Mother... Mother...",
        "Shinitakunai...": "I don't want to die...",
        "Samui... samui...": "Cold... so cold...",
        "Tennōheika... banzai...": "Long live... the Emperor...",
        # C.shock
        "Daijōbu... daijōbu da...": "I'm all right... I'm all right...",
        "Kurai na...": "It's dark...",
        # C.buddy_down
        "{name}! {name} ga yarareta!": "{name}! They got {name}!",
        "{name}! Shikkari shiro!": "{name}! Hang on!",
        # C.buddy_dead
        "{name} ga shinda!": "{name}'s dead!",
        "{name}... {name}...": "{name}... {name}...",
        "Yatsura, {name} o!": "The swine - {name}!",
        # C.comfort
        "Shikkari shiro! Mō sugu eisei-hei ga kuru!": "Hang on! The medic will be here soon!",
        "Ore o miro! Nemuru na!": "Look at me! Don't fall asleep!",
        # C.under_fire
        "Doko kara da?!": "Where's it coming from?!",
        "Mienai! Mienai zo!": "I can't see them! I can't see them!",
        "Fuseru! Atama o sagero!": "Get down! Heads down!",
        # C.moving
        "Susumu!": "Moving!",
        "Iku zo!": "Here I go!",
        "Engo shiro!": "Cover me!",
        # C.covering
        "Engo suru!": "Covering!",
        "Ike! Engo da!": "Go! I'll cover you!",
        # C.out_of_ammo
        "Tamagire da!": "I'm out of ammo!",
        "Tama o kure!": "Give me ammo!",
        # C.got_him
        "Yatta!": "Got him!",
        "Hitori yatta!": "Got one!",
        # C.shelling
        "Hōgeki da! Fuseru!": "Shelling! Get down!",
        "Kuru zo!": "Here it comes!",
        # C.panic
        "Mō dame da!": "It's hopeless!",
        "Minna shinu!": "We'll all die!",
        "Kaeritai...": "I want to go home...",
        # C.nco_fire
        "Ute! Uchitsuzukero!": "Fire! Keep firing!",
        "Nerae! Yoku nerae!": "Aim! Aim carefully!",
        # C.nco_spread
        "Hirake! Katamaru na!": "Spread out! Don't bunch up!",
        # C.nco_up
        "Tate! Susume!": "On your feet! Advance!",
        # C.medic_coming
        "Ima iku! Ganbare!": "Coming! Hang in there!",
        # C.offer_smoke
        "Tabako, dō da?": "Cigarette?",
        "Ippon yaru yo.": "Here, have one.",
        # C.thanks
        "Arigatō.": "Thanks.",
        "Tasukaru.": "You're a lifesaver.",
        # C.trade_offer
        "{give} to {want}, torikaenai ka?": "Trade you {give} for {want}?",
        # C.trade_yes
        "Ii darō.": "All right.",
        "Kimari da.": "It's a deal.",
        # C.trade_no
        "Dame da.": "No good.",
        "Iranai.": "Don't want it.",
        # C.photo
        "Kore ga {sweet} da.": "This is my {sweet}.",
        "Musuko da. Mada atta koto ga nai.": "My son. I've never met him.",
        # C.letter_good
        "Kanai ga matte iru to...": "My wife writes that she's waiting...",
        "Minna genki da sō da.": "They say everyone's well.",
        # C.letter_bad
        "...Ani ga senshi shita.": "...My elder brother was killed in action.",
        "Ie ga yakareta...": "Our house was burned down...",
        # C.pray
        "Namu Amida Butsu...": "Hail Amida Buddha...",
        "Kami-sama...": "Gods, please...",
        # C.mourn
        "{name}... yasuraka ni.": "{name}... rest in peace.",
        "Sumanai, {name}.": "I'm sorry, {name}.",
        # C.souvenir
        "Senrihin da!": "Spoils of war!",
        # C.steady
        "Ochitsuke. Daijōbu da.": "Calm down. You're all right.",
        "Ore to issho ni iro.": "Stay with me.",
        # C.feet
        "Kutsushita o kaero.": "Change your socks.",
        "Nanika kue. Meirei da.": "Eat something. That's an order.",
        # BANTER
        "Kokyō no yume o mita.": "I dreamed of home.",
        "Ore mo da. Haha no ryōri no yume da.": "Me too. I dreamed of my mother's cooking.",
        "Mata imo ka.": "Sweet potatoes again?",
        "Imo ga aru dake mashi da.": "Be glad there are potatoes at all.",
        "Tegami wa kita ka?": "Any letters come?",
        "Mō san-kagetsu mo konai.": "Nothing for three months now.",
        "Shizuka da na.": "Quiet, isn't it.",
        "Sonna koto o iu na.": "Don't say things like that.",
        "Tabako wa aru ka?": "Got a cigarette?",
        "Saigo no ippon da. Wakeyō.": "It's my last one. Let's share it.",
        "Itsu kaereru darō.": "I wonder when we'll get home.",
        "Kaeru to omou na. Sono hō ga raku da.": "Don't think about going home. It's easier that way.",
        "Ashi ga kusatte kita.": "My feet are starting to rot.",
        "Kono ame ja shikata ga nai.": "Can't be helped, in this rain.",
        "Hanchō wa kowai.": "The squad leader scares me.",
        "Teki yori kowai.": "More than the enemy does.",
    },
    # ==================== Italian
    "it": {
        # shouts.attack
        "Avanti!": "Forward!",
        "Savoia!": "For Savoy!",
        "All'attacco!": "Attack!",
        "Forza, ragazzi!": "Come on, boys!",
        # shouts.grenade
        "Bomba a mano!": "Hand grenade!",
        "Granata!": "Grenade!",
        # shouts.medic
        "Portaferiti!": "Stretcher-bearer!",
        "Aiuto!": "Help!",
        "Mamma!": "Mama!",
        # shouts.reload
        "Ricarico!": "Reloading!",
        # shouts.contact
        "Nemico in vista!": "Enemy in sight!",
        "Gli inglesi!": "The English!",
        # shouts.retreat
        "Ritirata!": "Retreat!",
        "Indietro!": "Back!",
        # shouts.surrender
        "Non sparate! Mi arrendo!": "Don't shoot! I surrender!",
        # shouts.tank
        "Carro armato!": "Tank!",
        # shouts.sniper
        "Cecchino!": "Sniper!",
        # shouts.mg
        "Mitragliatrice! A terra!": "Machine gun! Get down!",
        # shouts.pain
        "Ahi!": "Ow!",
        "Madonna!": "Mother of God!",
        "Sono ferito!": "I'm wounded!",
        # ACK
        "Signorsì!": "Yes, sir!",
        "Agli ordini!": "At your orders!",
        "Subito, signor {rank}!": "At once, Signor {rank}!",
        # P.follow_me
        "Comando io adesso!": "I'm in command now!",
        "Con me!": "With me!",
        "Seguitemi!": "Follow me!",
        # P.ambush_fire
        "Fuoco!": "Fire!",
        "Adesso! Fuoco!": "Now! Fire!",
        "Sparate!": "Shoot!",
        # P.seen_fire
        "Ci hanno visti - fuoco!": "They've seen us - fire!",
        # P.fire_control
        "Sulla mitragliatrice - fuoco!": "On the machine gun - fire!",
        "Tutti sulla mitragliatrice!": "Everyone on the machine gun!",
        # P.smoke
        "Fumogeni!": "Smoke!",
        "Cortina di fumo!": "Smokescreen!",
        # P.flank
        "Aggirateli!": "Go round them!",
        "Sul fianco!": "Take the flank!",
        # P.resupplied
        "Tutti riforniti? Andiamo!": "Everyone resupplied? Let's go!",
        # P.medic_comfort
        "Tieni duro, ci sono io.": "Hold on, I'm here.",
        "Te la caverai.": "You'll pull through.",
        "Resta con me!": "Stay with me!",
        # P.medic_coming
        "Arrivo!": "Coming!",
        "Resisti!": "Hold on!",
        "Sto arrivando!": "I'm on my way!",
        # P.fire_mission
        "Fuoco d'artiglieria!": "Artillery fire!",
        "Batteria, fuoco!": "Battery, fire!",
        # P.ammo
        "Munizioni!": "Ammo!",
        # P.runner
        "Vado!": "Going!",
        "Subito!": "Right away!",
        # P.senior_now
        "Ora il più anziano sei tu. La squadra è tua.": "You're the senior man now. The squad's yours.",
        # P.lt_down
        "Il tenente è caduto!": "The lieutenant's been killed!",
        # P.capt_down
        "Il capitano è caduto!": "The captain's been killed!",
        # P.o_hold
        "Tenete la posizione! Al riparo!": "Hold the position! Take cover!",
        # P.o_dig
        "Scavate!": "Dig in!",
        # P.o_move
        "Avanzate! Via!": "Advance! Go!",
        # P.o_hold_fire
        "Non sparate!": "Hold your fire!",
        # P.o_return_fire
        "Rispondete solo al fuoco!": "Return fire only!",
        # P.o_fire_at_will
        "Fuoco a volontà!": "Fire at will!",
        # P.o_ambush
        "Giù! Nessuno spari finché non lo dico io!": "Down! Nobody fires until I say so!",
        # P.o_suppress
        "Fuoco di copertura!": "Covering fire!",
        # P.o_regroup
        "Raggrupparsi!": "Regroup!",
        # P.o_mount
        "Salite a bordo!": "Get aboard!",
        # P.o_dismount
        "Scendete!": "Get out!",
        # P.o_resupply
        "Rifornitevi!": "Resupply!",
        # P.o_report
        "Rapporto!": "Report!",
        # P.t_help
        "Aiutalo! Fascialo!": "Help him! Bandage him!",
        # P.t_ammo
        "Portagli le munizioni!": "Take him the ammo!",
        # P.t_gun
        "Prendi quell'arma!": "Grab that gun!",
        # P.t_down
        "Giù, idiota!": "Get down, you idiot!",
        # P.t_come
        "Torna qui!": "Get back here!",
        # P.t_fire
        "Spara, maledizione!": "Shoot, damn it!",
        # P.t_dig
        "Scava!": "Dig!",
        # P.t_runner
        "Portalo a lui! Corri!": "Take it to him! Run!",
        # P.t_fetch
        "Vai a prendere munizioni!": "Go and get ammo!",
        # P.t_scout
        "Vai a dare un'occhiata.": "Go and have a look.",
        # P.t_escort
        "Porta i prigionieri nelle retrovie.": "Take the prisoners to the rear.",
        # P.praise
        "Bravo.": "Good man.",
        # P.rebuke
        "È un ordine!": "That's an order!",
        # P.ff_rebuke
        "Attento a dove spari!": "Watch where you're shooting!",
        # P.arrest
        "Getta l'arma!": "Drop your weapon!",
        # P.murder
        "Spara ai suoi! Prendetelo!": "He's shooting his own side! Grab him!",
        # P.pow_shot
        "Si era arreso!": "He'd surrendered!",
        # P.share_ammo
        "Tieni!": "Here!",
        # C.hit_light
        "Sono colpito!": "I'm hit!",
        "Porca miseria! Mi hanno preso!": "Damn it! They got me!",
        "È niente - avanti!": "It's nothing - keep going!",
        # C.hit_bad
        "Sono ferito grave!": "I'm badly wounded!",
        "Dio mio, Dio mio!": "My God, my God!",
        "Portaferiti! PORTAFERITI!": "Stretcher-bearer! STRETCHER-BEARER!",
        "Aiuto! Aiutatemi!": "Help! Help me!",
        # C.part
        "La mia {part}! La mia {part}!": "My {part}! My {part}!",
        "Dio, la {part}!": "God, my {part}!",
        # C.legs
        "Non posso camminare!": "I can't walk!",
        "Non lasciatemi qui!": "Don't leave me here!",
        # C.gut
        "Alla pancia... Dio...": "In the belly... God...",
        "Acqua... datemi acqua...": "Water... give me water...",
        # C.chest
        "Non respiro... non respiro!": "I can't breathe... I can't breathe!",
        # C.eyes
        "I miei occhi! Non vedo!": "My eyes! I can't see!",
        # C.bleeding
        "Mi sto dissanguando!": "I'm bleeding to death!",
        "Quanto sangue... quanto sangue...": "So much blood... so much blood...",
        # C.dying
        "Mamma... mamma mia...": "Mama... oh, Mama...",
        "Non voglio morire...": "I don't want to die...",
        "Dite alla mamma...": "Tell my mother...",
        "Ho freddo... tanto freddo...": "I'm cold... so cold...",
        "Ave Maria, piena di grazia...": "Hail Mary, full of grace...",
        # C.shock
        "Sto bene... sto bene...": "I'm all right... I'm all right...",
        "Si fa buio...": "It's getting dark...",
        # C.buddy_down
        "{name}! Hanno preso {name}!": "{name}! They got {name}!",
        "{name} è ferito!": "{name}'s wounded!",
        "No! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} è morto!": "{name}'s dead!",
        "Dio... {name}...": "God... {name}...",
        "Hanno ammazzato {name}!": "They've killed {name}!",
        # C.comfort
        "Tieni duro, amico.": "Hang on, pal.",
        "Arriva il portaferiti.": "The stretcher-bearer's coming.",
        "Guardami! Resta con me!": "Look at me! Stay with me!",
        # C.under_fire
        "Da dove sparano?!": "Where are they shooting from?!",
        "Non li vedo!": "I can't see them!",
        "Giù! Tutti giù!": "Down! Everybody down!",
        # C.moving
        "Avanzo!": "Moving up!",
        "Coprimi!": "Cover me!",
        # C.covering
        "Ti copro!": "I've got you covered!",
        "Vai, ti copro!": "Go, I'll cover you!",
        # C.out_of_ammo
        "Sono senza munizioni!": "I'm out of ammo!",
        # C.got_him
        "Preso!": "Got him!",
        "Uno in meno!": "One less!",
        # C.shelling
        "Arrivano! Giù!": "Incoming! Get down!",
        "Mortai! A terra!": "Mortars! Get down!",
        # C.panic
        "Non ce la faccio!": "I can't take it!",
        "Moriremo tutti!": "We're all going to die!",
        "Voglio tornare a casa...": "I want to go home...",
        # C.nco_fire
        "Continuate a sparare!": "Keep firing!",
        "Fuoco! Fuoco!": "Fire! Fire!",
        "Raffiche brevi!": "Short bursts!",
        # C.nco_spread
        "Allargatevi!": "Spread out!",
        "Non fate mucchio!": "Don't bunch up!",
        # C.nco_up
        "Su! Muovetevi!": "Up! Get moving!",
        # C.medic_coming
        "Arrivo! Resisti!": "Coming! Hold on!",
        # C.offer_smoke
        "Una sigaretta?": "A cigarette?",
        "Tieni, fuma.": "Here, have a smoke.",
        # C.thanks
        "Grazie, amico.": "Thanks, pal.",
        "Sei un angelo.": "You're an angel.",
        # C.trade_offer
        "Scambiamo? {give} per {want}?": "Trade you {give} for {want}?",
        # C.trade_yes
        "Affare fatto.": "It's a deal.",
        "D'accordo.": "All right.",
        # C.trade_no
        "Neanche per sogno.": "Not on your life.",
        "Tienitelo.": "Keep it.",
        # C.photo
        "Questa è la mia {sweet}.": "That's my {sweet}.",
        "Mio figlio. Non l'ho mai visto.": "My son. I've never seen him.",
        # C.letter_good
        "Mi aspetta. Scrive che mi aspetta.": "She's waiting for me. She writes that she's waiting.",
        # C.letter_bad
        "...Mio fratello è disperso in Russia.": "...My brother's missing in Russia.",
        # C.pray
        "Signore, proteggimi...": "Lord, protect me...",
        # C.mourn
        "Riposa in pace, {name}.": "Rest in peace, {name}.",
        "Scusami, amico.": "Forgive me, pal.",
        # C.souvenir
        "Guarda qua!": "Look at this!",
        # C.steady
        "Calma. Respira. Ce la facciamo.": "Easy. Breathe. We'll make it.",
        # C.feet
        "Cambia le calze.": "Change your socks.",
        "Mangia qualcosa. È un ordine.": "Eat something. That's an order.",
        # BANTER
        "Quanto vorrei un piatto di pasta vera.": "What I'd give for a plate of real pasta.",
        "Smettila, mi fai piangere.": "Stop it, you'll make me cry.",
        "Hai notizie da casa?": "Any news from home?",
        "Mia madre dice che è arrivato il fratello di Rosa. Senza gamba.": "My mother says Rosa's brother came home. Minus a leg.",
        "Dove siamo, secondo te?": "Where do you reckon we are?",
        "Chiedilo al tenente. Nemmeno lui lo sa.": "Ask the lieutenant. He doesn't know either.",
        "Hai una sigaretta?": "Got a cigarette?",
        "L'ultima. Facciamo a metà.": "My last one. Let's go halves.",
        "C'è troppo silenzio.": "It's too quiet.",
        "Non dirlo. Porta sfortuna.": "Don't say it. It's bad luck.",
        "Dopo la guerra apro un'osteria.": "After the war I'm opening a tavern.",
        "Io vengo tutte le sere.": "I'll be in every night.",
    },
    # ==================== French
    "fr": {
        # shouts.attack
        "En avant!": "Forward!",
        "Allez, allez!": "Come on, come on!",
        "À l'attaque!": "Attack!",
        "Baïonnette au canon!": "Fix bayonets!",
        # shouts.grenade
        "Grenade!": "Grenade!",
        # shouts.medic
        "Brancardier!": "Stretcher-bearer!",
        "Infirmier!": "Medic!",
        "Maman!": "Mama!",
        # shouts.reload
        "Je recharge!": "Reloading!",
        # shouts.contact
        "Les Boches!": "The Boche!",
        "Ennemi en vue!": "Enemy in sight!",
        # shouts.retreat
        "Repliez-vous!": "Fall back!",
        "Sauve qui peut!": "Every man for himself!",
        # shouts.surrender
        "Ne tirez pas!": "Don't shoot!",
        # shouts.tank
        "Char! Char ennemi!": "Tank! Enemy tank!",
        # shouts.sniper
        "Tireur!": "Sniper!",
        # shouts.mg
        "Mitrailleuse!": "Machine gun!",
        # shouts.pain
        "Aïe!": "Ow!",
        "Merde!": "Shit!",
        "Je suis touché!": "I'm hit!",
        # ACK
        "À vos ordres, mon {rank}!": "At your orders, mon {rank}!",
        "Compris!": "Understood!",
        "Bien, mon {rank}.": "Very good, mon {rank}.",
        # P.follow_me
        "Je prends le commandement!": "I'm taking command!",
        "Avec moi!": "With me!",
        "Suivez-moi!": "Follow me!",
        # P.ambush_fire
        "Feu!": "Fire!",
        "Maintenant! Feu!": "Now! Fire!",
        "Tirez!": "Shoot!",
        # P.seen_fire
        "Ils nous ont vus - feu à volonté!": "They've seen us - fire at will!",
        # P.fire_control
        "Sur la mitrailleuse - feu!": "On the machine gun - fire!",
        "Tous sur la mitrailleuse!": "Everyone on the machine gun!",
        # P.smoke
        "Fumigènes!": "Smoke!",
        "De la fumée devant!": "Smoke out front!",
        # P.flank
        "Débordez-les!": "Outflank them!",
        "Par le flanc!": "By the flank!",
        # P.resupplied
        "Tout le monde est servi? On y va!": "Everyone sorted? Let's go!",
        # P.medic_comfort
        "Tiens bon, je suis là.": "Hold on, I'm here.",
        "Ça va aller.": "It'll be all right.",
        "Reste avec moi!": "Stay with me!",
        # P.medic_coming
        "J'arrive!": "Coming!",
        "Tiens bon!": "Hold on!",
        "Reste couché, j'arrive!": "Stay down, I'm coming!",
        # P.fire_mission
        "Mission de tir!": "Fire mission!",
        "Batterie, feu!": "Battery, fire!",
        # P.ammo
        "Munitions!": "Ammo!",
        # P.runner
        "J'y vais!": "On my way!",
        "Tout de suite!": "Right away!",
        # P.senior_now
        "Tu es le plus gradé maintenant. Le groupe est à toi.": "You're the ranking man now. The squad's yours.",
        # P.lt_down
        "Le lieutenant est touché!": "The lieutenant's hit!",
        # P.capt_down
        "Le capitaine est touché!": "The captain's hit!",
        # P.o_hold
        "Tenez la position! À couvert!": "Hold the position! Take cover!",
        # P.o_dig
        "Creusez! On reste ici.": "Dig in! We're staying here.",
        # P.o_move
        "En avant! Allez!": "Forward! Go!",
        # P.o_hold_fire
        "Cessez le feu!": "Cease fire!",
        # P.o_return_fire
        "Ripostez seulement!": "Return fire only!",
        # P.o_fire_at_will
        "Feu à volonté!": "Fire at will!",
        # P.o_ambush
        "À terre! Personne ne tire avant mon ordre!": "Get down! Nobody fires till I give the order!",
        # P.o_suppress
        "Tir de suppression!": "Suppressing fire!",
        # P.o_regroup
        "Regroupez-vous!": "Regroup!",
        # P.o_mount
        "Embarquez!": "Get aboard!",
        # P.o_dismount
        "Débarquez!": "Get out!",
        # P.o_resupply
        "Allez vous ravitailler!": "Go and resupply!",
        # P.o_report
        "Au rapport!": "Report!",
        # P.t_help
        "Occupe-toi de lui! Panse-le!": "See to him! Dress his wound!",
        # P.t_ammo
        "Apporte-lui des munitions!": "Take him some ammo!",
        # P.t_gun
        "Prends cette arme!": "Take that gun!",
        # P.t_down
        "À terre, imbécile!": "Get down, you idiot!",
        # P.t_come
        "Reviens ici!": "Come back here!",
        # P.t_fire
        "Tire, bon sang!": "Shoot, damn it!",
        # P.t_dig
        "Creuse!": "Dig!",
        # P.t_runner
        "Porte ça! Cours!": "Take this! Run!",
        # P.t_fetch
        "Va chercher des munitions!": "Go and get ammo!",
        # P.t_scout
        "Va jeter un œil là-bas.": "Go and take a look over there.",
        # P.t_escort
        "Emmène les prisonniers à l'arrière.": "Take the prisoners to the rear.",
        # P.praise
        "Bien joué.": "Well done.",
        # P.rebuke
        "C'est un ordre!": "That's an order!",
        # P.ff_rebuke
        "Attention à tes tirs!": "Watch your fire!",
        # P.arrest
        "Lâche ton arme!": "Drop your weapon!",
        # P.murder
        "Il tire sur les nôtres! Attrapez-le!": "He's shooting at our own men! Grab him!",
        # P.pow_shot
        "Il s'était rendu!": "He'd surrendered!",
        # P.share_ammo
        "Tiens, prends ça!": "Here, take this!",
        # C.hit_light
        "Merde! Touché!": "Shit! I'm hit!",
        "C'est rien - on continue!": "It's nothing - keep going!",
        # C.hit_bad
        "Je suis gravement touché!": "I'm hit bad!",
        "Mon Dieu, mon Dieu!": "My God, my God!",
        "Infirmier! INFIRMIER!": "Medic! MEDIC!",
        "À l'aide! Aidez-moi!": "Help! Help me!",
        # C.part
        "Ma {part}! Ma {part}!": "My {part}! My {part}!",
        "Mon Dieu, ma {part}!": "My God, my {part}!",
        # C.legs
        "Je peux plus marcher!": "I can't walk any more!",
        "Me laissez pas là!": "Don't leave me here!",
        # C.gut
        "Au ventre... mon Dieu...": "In the belly... my God...",
        "De l'eau... donnez-moi de l'eau...": "Water... give me water...",
        # C.chest
        "J'arrive pas à respirer!": "I can't breathe!",
        # C.eyes
        "Mes yeux! J'y vois plus!": "My eyes! I can't see!",
        # C.bleeding
        "Je me vide de mon sang!": "I'm bleeding out!",
        "Tout ce sang... tout ce sang...": "All this blood... all this blood...",
        # C.dying
        "Maman... maman...": "Mama... Mama...",
        "Je veux pas mourir...": "I don't want to die...",
        "Dites à ma mère...": "Tell my mother...",
        "J'ai froid... si froid...": "I'm cold... so cold...",
        # C.shock
        "Ça va... ça va...": "I'm all right... I'm all right...",
        "Il fait sombre...": "It's getting dark...",
        # C.buddy_down
        "{name}! {name} est touché!": "{name}! {name}'s hit!",
        "Ils ont eu {name}!": "They got {name}!",
        "Non! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} est mort!": "{name}'s dead!",
        "Mon Dieu... {name}...": "My God... {name}...",
        "Ils ont tué {name}, les salauds!": "The bastards killed {name}!",
        # C.comfort
        "Tiens bon, mon vieux.": "Hang on, old pal.",
        "L'infirmier arrive.": "The medic's coming.",
        "Reste avec moi! Regarde-moi!": "Stay with me! Look at me!",
        # C.under_fire
        "D'où ça tire?!": "Where's it coming from?!",
        "Je les vois pas!": "I can't see them!",
        "À terre! Baissez la tête!": "Get down! Heads down!",
        "Nom de Dieu!": "God damn it!",
        # C.moving
        "J'avance!": "Moving up!",
        "Couvre-moi!": "Cover me!",
        # C.covering
        "Je te couvre!": "I've got you covered!",
        "Vas-y, je couvre!": "Go on, I'm covering!",
        # C.out_of_ammo
        "Plus de munitions!": "I'm out of ammo!",
        "Des munitions!": "I need ammo!",
        # C.got_him
        "Je l'ai eu!": "Got him!",
        "Un de moins!": "One less!",
        # C.shelling
        "Obus! À terre!": "Shells! Get down!",
        "Mortiers! Couchez-vous!": "Mortars! Get down!",
        # C.panic
        "J'en peux plus!": "I can't take any more!",
        "On va tous crever!": "We're all gonna croak!",
        "Je veux rentrer...": "I want to go home...",
        # C.nco_fire
        "Continuez le feu!": "Keep firing!",
        "Tirez, bon Dieu!": "Fire, for God's sake!",
        "Rafales courtes!": "Short bursts!",
        # C.nco_spread
        "Écartez-vous!": "Spread out!",
        "Pas en paquet!": "Don't bunch up!",
        # C.nco_up
        "Debout! En avant!": "On your feet! Forward!",
        # C.medic_coming
        "J'arrive! Tiens bon!": "Coming! Hold on!",
        # C.offer_smoke
        "Une cigarette?": "Cigarette?",
        "Tiens, fume.": "Here, have a smoke.",
        # C.thanks
        "Merci, mon vieux.": "Thanks, old pal.",
        "T'es un frère.": "You're a real brother.",
        # C.trade_offer
        "On échange? {give} contre {want}?": "Trade you {give} for {want}?",
        # C.trade_yes
        "Marché conclu.": "It's a deal.",
        "D'accord.": "All right.",
        # C.trade_no
        "Pas question.": "No way.",
        "Garde-le.": "Keep it.",
        # C.photo
        "C'est ma {sweet}.": "That's my {sweet}.",
        "Mon fils. Je l'ai jamais vu.": "My son. I've never seen him.",
        # C.letter_good
        "Elle m'attend. Elle dit qu'elle m'attend.": "She's waiting for me. She says she's waiting.",
        # C.letter_bad
        "...Mon frère est prisonnier en Allemagne.": "...My brother's a prisoner in Germany.",
        # C.pray
        "Je vous salue, Marie...": "Hail Mary...",
        "Seigneur, protège-moi...": "Lord, protect me...",
        # C.mourn
        "Repose en paix, {name}.": "Rest in peace, {name}.",
        "Pardon, mon vieux.": "Sorry, old pal.",
        # C.souvenir
        "Regarde ça!": "Look at this!",
        # C.steady
        "Du calme. Respire. On va s'en sortir.": "Easy. Breathe. We'll get out of this.",
        # C.feet
        "Change tes chaussettes.": "Change your socks.",
        "Mange quelque chose. C'est un ordre.": "Eat something. That's an order.",
        # BANTER
        "Qu'est-ce que je donnerais pour un vrai café.": "What I'd give for a real coffee.",
        "Moi, pour un vrai lit.": "Me, for a real bed.",
        "Tu as des nouvelles de chez toi?": "Any news from home?",
        "Rien depuis des semaines.": "Nothing for weeks.",
        "On est où, à ton avis?": "Where do you reckon we are?",
        "Demande au lieutenant. Il ne sait pas non plus.": "Ask the lieutenant. He doesn't know either.",
        "T'as une clope?": "Got a smoke?",
        "La dernière. On partage.": "My last one. We'll share it.",
        "C'est calme.": "It's quiet.",
        "Ne dis pas ça. Jamais.": "Don't say that. Ever.",
        "Après la guerre, j'ouvre un bistrot.": "After the war, I'm opening a bistro.",
        "Je serai ton premier client.": "I'll be your first customer.",
    },
    # ==================== Polish
    "pl": {
        # shouts.attack
        "Naprzód!": "Forward!",
        "Hurra!": "Hurrah!",
        "Za Polskę!": "For Poland!",
        "Do ataku!": "Attack!",
        # shouts.grenade
        "Granat!": "Grenade!",
        # shouts.medic
        "Sanitariusz!": "Medic!",
        "Ratunku!": "Help!",
        "Mamo!": "Mama!",
        # shouts.reload
        "Przeładowuję!": "Reloading!",
        # shouts.contact
        "Szwaby!": "Krauts!",
        "Nieprzyjaciel!": "Enemy!",
        # shouts.retreat
        "Odwrót!": "Retreat!",
        # shouts.surrender
        "Nie strzelać!": "Don't shoot!",
        # shouts.tank
        "Czołg!": "Tank!",
        # shouts.sniper
        "Snajper!": "Sniper!",
        # shouts.mg
        "Karabin maszynowy!": "Machine gun!",
        # shouts.pain
        "Aaa!": "Aaah!",
        "Cholera!": "Damn it!",
        # ACK
        "Tak jest!": "Yes, sir!",
        "Rozkaz!": "At your command!",
        "Tak jest, panie {rank}!": "Yes, {rank}, sir!",
        # P.follow_me
        "Przejmuję dowodzenie!": "I'm taking command!",
        "Do mnie!": "To me!",
        "Za mną!": "Follow me!",
        # P.ambush_fire
        "Ognia!": "Fire!",
        "Teraz! Ognia!": "Now! Fire!",
        # P.seen_fire
        "Zauważyli nas - ognia!": "They've spotted us - fire!",
        # P.fire_control
        "Cel: karabin maszynowy - ognia!": "Target, the machine gun - fire!",
        "Wszyscy na kaem!": "Everyone on the machine gun!",
        # P.smoke
        "Dym! Rzucać dym!": "Smoke! Throw smoke!",
        # P.flank
        "Oskrzydlić!": "Outflank them!",
        "Z flanki!": "From the flank!",
        # P.resupplied
        "Wszyscy mają? Idziemy!": "Everyone got some? Let's go!",
        # P.medic_comfort
        "Trzymaj się, mam cię.": "Hold on, I've got you.",
        "Będzie dobrze.": "It'll be all right.",
        "Zostań ze mną!": "Stay with me!",
        # P.medic_coming
        "Idę!": "Coming!",
        "Trzymaj się!": "Hold on!",
        "Leż, idę!": "Stay down, I'm coming!",
        # P.fire_mission
        "Wsparcie artylerii!": "Artillery support!",
        "Bateria, ognia!": "Battery, fire!",
        # P.ammo
        "Amunicja!": "Ammo!",
        # P.runner
        "Już biegnę!": "On my way!",
        # P.senior_now
        "Teraz ty jesteś starszy. Drużyna jest twoja.": "You're senior now. The squad's yours.",
        # P.lt_down
        "Porucznik padł!": "The lieutenant's been killed!",
        # P.capt_down
        "Kapitan padł!": "The captain's been killed!",
        # P.o_hold
        "Utrzymać pozycję! Kryć się!": "Hold the position! Take cover!",
        # P.o_dig
        "Okopać się!": "Dig in!",
        # P.o_move
        "Naprzód! Szybko!": "Forward! Quickly!",
        # P.o_retreat
        "Wycofać się!": "Fall back!",
        # P.o_return_fire
        "Tylko odpowiadać ogniem!": "Return fire only!",
        # P.o_fire_at_will
        "Ognia według uznania!": "Fire at will!",
        # P.o_ambush
        "Padnij! Nikt nie strzela bez rozkazu!": "Get down! Nobody fires without orders!",
        # P.o_suppress
        "Przydusić ich ogniem!": "Pin them down with fire!",
        # P.o_regroup
        "Zbiórka!": "Fall in!",
        # P.o_mount
        "Wsiadać!": "Mount up!",
        # P.o_dismount
        "Wysiadać!": "Dismount!",
        # P.o_resupply
        "Uzupełnić amunicję!": "Replenish ammunition!",
        # P.o_report
        "Meldunek!": "Report!",
        # P.t_help
        "Opatrz go!": "Dress his wounds!",
        # P.t_ammo
        "Podaj mu amunicję!": "Pass him some ammo!",
        # P.t_gun
        "Do karabinu!": "Man the gun!",
        # P.t_down
        "Padnij, idioto!": "Get down, you idiot!",
        # P.t_fire
        "Strzelaj!": "Shoot!",
        # P.t_dig
        "Okop się!": "Dig in!",
        # P.t_runner
        "Zanieś mu to! Biegiem!": "Take this to him! On the double!",
        # P.t_fetch
        "Przynieś amunicję!": "Fetch ammo!",
        # P.t_scout
        "Idź zobacz. Cicho.": "Go and look. Quietly.",
        # P.t_escort
        "Odprowadź jeńców na tyły.": "Take the prisoners to the rear.",
        # P.praise
        "Dobra robota.": "Good work.",
        # P.rebuke
        "To rozkaz!": "That's an order!",
        # P.ff_rebuke
        "Uważaj, gdzie strzelasz!": "Watch where you're shooting!",
        # P.arrest
        "Rzuć broń!": "Drop your weapon!",
        # P.murder
        "Strzela do swoich! Brać go!": "He's shooting at his own! Get him!",
        # P.pow_shot
        "On się poddał!": "He'd surrendered!",
        # P.share_ammo
        "Masz, łap!": "Here, catch!",
        # C.hit_light
        "Dostałem!": "I'm hit!",
        "Cholera! Trafili mnie!": "Damn it! They got me!",
        # C.hit_bad
        "Sanitariusz! SANITARIUSZ!": "Medic! MEDIC!",
        "Pomocy! Ratunku!": "Help me! Help!",
        "O Boże, o Boże!": "Oh God, oh God!",
        # C.part
        "Moja {part}!": "My {part}!",
        "{part}! Moja {part}!": "My {part}! Oh, my {part}!",
        # C.legs
        "Nie mogę iść!": "I can't walk!",
        "Nie zostawiajcie mnie!": "Don't leave me!",
        # C.gut
        "W brzuch... Boże...": "In the belly... God...",
        "Wody... dajcie wody...": "Water... give me water...",
        # C.bleeding
        "Wykrwawiam się!": "I'm bleeding to death!",
        "Tyle krwi...": "So much blood...",
        # C.dying
        "Mamo... mamusiu...": "Mama... dear Mama...",
        "Nie chcę umierać...": "I don't want to die...",
        "Zdrowaś Maryjo...": "Hail Mary...",
        # C.buddy_down
        "{name}! {name} dostał!": "{name}! {name}'s hit!",
        "Nie! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} nie żyje!": "{name}'s dead!",
        "Zabili {name}!": "They've killed {name}!",
        # C.comfort
        "Trzymaj się, bracie.": "Hold on, brother.",
        "Sanitariusz już idzie.": "The medic's on his way.",
        # C.under_fire
        "Skąd strzelają?!": "Where are they shooting from?!",
        "Padnij!": "Get down!",
        "Nie widzę ich!": "I can't see them!",
        # C.moving
        "Osłaniaj!": "Cover me!",
        # C.covering
        "Osłaniam!": "Covering!",
        # C.out_of_ammo
        "Nie mam amunicji!": "I'm out of ammo!",
        # C.got_him
        "Mam go!": "Got him!",
        # C.shelling
        "Ostrzał! Padnij!": "Shelling! Get down!",
        # C.panic
        "Nie dam rady!": "I can't do it!",
        "Wszyscy zginiemy!": "We're all going to die!",
        # C.nco_fire
        "Ognia! Nie przerywać!": "Fire! Don't stop!",
        # BANTER
        "Masz jakieś wieści z domu?": "Any news from home?",
        "Żadnych. Od miesięcy.": "None. Not for months.",
        "Znowu ta zupa.": "This soup again.",
        "Ciesz się, że jest jakakolwiek.": "Be glad there's any at all.",
        "Masz papierosa?": "Got a cigarette?",
        "Ostatni. Podzielimy się.": "My last one. We'll share it.",
        "Cicho jakoś.": "Awfully quiet.",
        "Nie mów tak. Nigdy.": "Don't say that. Ever.",
        "Po wojnie wracam do Warszawy.": "After the war I'm going back to Warsaw.",
        "Jeśli coś z niej zostanie.": "If there's anything left of it.",
    },
    # ==================== Finnish
    "fi": {
        # shouts.attack
        "Eteenpäin!": "Forward!",
        "Hyökkää!": "Attack!",
        "Hurraa!": "Hurrah!",
        # shouts.grenade
        "Kranaatti!": "Grenade!",
        "Maahan!": "Get down!",
        # shouts.medic
        "Lääkintämies!": "Medic!",
        "Apua!": "Help!",
        "Äiti!": "Mother!",
        # shouts.reload
        "Lataan!": "Reloading!",
        # shouts.contact
        "Ryssiä!": "Russkies!",
        "Vihollinen!": "Enemy!",
        # shouts.retreat
        "Perääntykää!": "Fall back!",
        # shouts.surrender
        "Älä ammu!": "Don't shoot!",
        # shouts.tank
        "Panssarivaunu!": "Tank!",
        # shouts.sniper
        "Tarkka-ampuja!": "Sniper!",
        # shouts.mg
        "Konekivääri!": "Machine gun!",
        # shouts.pain
        "Perkele!": "Damn it to hell!",
        "Aah!": "Aah!",
        # ACK
        "Selvä!": "Understood!",
        "Käsky!": "Yes, sir!",
        "Kyllä, herra {rank}!": "Yes, {rank}, sir!",
        # P.follow_me
        "Minä johdan nyt!": "I'm in command now!",
        "Perään!": "After me!",
        "Seuratkaa minua!": "Follow me!",
        # P.ambush_fire
        "Tulta!": "Fire!",
        "Nyt! Tulta!": "Now! Fire!",
        # P.seen_fire
        "Meidät huomattiin - tulta!": "We've been spotted - fire!",
        # P.fire_control
        "Konekivääriä kohti - tulta!": "At the machine gun - fire!",
        "Kaikki konekiväärin kimppuun!": "Everybody, get that machine gun!",
        # P.smoke
        "Savua!": "Smoke!",
        "Savukranaatti!": "Smoke grenade!",
        # P.flank
        "Sivustaan!": "Flank them!",
        "Kiertäkää vasemmalta!": "Go round on the left!",
        # P.resupplied
        "Kaikilla on? Mennään!": "Everyone got some? Let's go!",
        # P.medic_comfort
        "Kestä, minä autan.": "Hang on, I'll help you.",
        "Kyllä se siitä.": "You'll be fine.",
        "Pysy hereillä!": "Stay awake!",
        # P.medic_coming
        "Tulossa!": "Coming!",
        "Kestä!": "Hang on!",
        # P.fire_mission
        "Tulikomento!": "Fire mission!",
        "Patteri, tulta!": "Battery, fire!",
        # P.ammo
        "Ammuksia!": "Ammo!",
        # P.runner
        "Menen!": "Going!",
        # P.senior_now
        "Olet nyt vanhempi. Ryhmä on sinun.": "You're senior now. The squad's yours.",
        # P.lt_down
        "Luutnantti kaatui!": "The lieutenant's been killed!",
        # P.capt_down
        "Kapteeni kaatui!": "The captain's been killed!",
        # P.o_hold
        "Pitäkää asema! Suojaan!": "Hold the position! Take cover!",
        # P.o_dig
        "Kaivautukaa!": "Dig in!",
        # P.o_move
        "Eteenpäin! Nopeasti!": "Forward! Quickly!",
        # P.o_hold_fire
        "Älkää ampuko!": "Hold your fire!",
        # P.o_return_fire
        "Vastatkaa vain tuleen!": "Return fire only!",
        # P.o_fire_at_will
        "Vapaa tuli!": "Fire at will!",
        # P.o_ambush
        "Maahan! Kukaan ei ammu ennen käskyä!": "Get down! Nobody fires before the order!",
        # P.o_suppress
        "Pitäkää heidät maassa!": "Keep them pinned down!",
        # P.o_regroup
        "Kokoontukaa!": "Regroup!",
        # P.o_mount
        "Kyytiin!": "Mount up!",
        # P.o_dismount
        "Ulos!": "Everybody out!",
        # P.o_resupply
        "Hakekaa ammuksia!": "Go and get ammo!",
        # P.o_report
        "Ilmoittakaa!": "Report!",
        # P.t_help
        "Sido hänet!": "Bandage him!",
        # P.t_ammo
        "Vie hänelle ammuksia!": "Take him some ammo!",
        # P.t_gun
        "Ota se ase!": "Take that gun!",
        # P.t_down
        "Maahan, idiootti!": "Get down, you idiot!",
        # P.t_come
        "Tänne! Heti!": "Over here! Now!",
        # P.t_fire
        "Ammu!": "Shoot!",
        # P.t_dig
        "Kaiva!": "Dig!",
        # P.t_runner
        "Vie tämä hänelle! Juokse!": "Take this to him! Run!",
        # P.t_fetch
        "Hae ammuksia!": "Fetch ammo!",
        # P.t_scout
        "Käy katsomassa.": "Go and have a look.",
        # P.t_escort
        "Vie vangit taakse.": "Take the prisoners to the rear.",
        # P.praise
        "Hyvä.": "Good.",
        # P.rebuke
        "Se oli käsky!": "That was an order!",
        # P.ff_rebuke
        "Varo mihin ammut!": "Watch where you're shooting!",
        # P.arrest
        "Pudota aseesi!": "Drop your weapon!",
        # P.murder
        "Hän ampuu omiaan! Ottakaa kiinni!": "He's shooting his own men! Grab him!",
        # P.pow_shot
        "Hän antautui!": "He'd surrendered!",
        # P.share_ammo
        "Tässä, ota!": "Here, take it!",
        # C.hit_light
        "Osui!": "I'm hit!",
        "Perkele! Osuma!": "Damn it to hell! I'm hit!",
        # C.hit_bad
        "Lääkintämies! LÄÄKINTÄMIES!": "Medic! MEDIC!",
        "Apua! Auttakaa!": "Help! Help me!",
        # C.part
        "{part}! Minun {part}!": "My {part}! Oh, my {part}!",
        # C.legs
        "En pysty kävelemään!": "I can't walk!",
        "Älkää jättäkö minua!": "Don't leave me!",
        # C.dying
        "Äiti... äiti...": "Mother... Mother...",
        "En halua kuolla...": "I don't want to die...",
        # C.buddy_down
        "{name}! {name} haavoittui!": "{name}! {name}'s wounded!",
        "Ei! {name}!": "No! {name}!",
        # C.buddy_dead
        "{name} kaatui!": "{name}'s been killed!",
        "{name}... voi ei...": "{name}... oh no...",
        # C.under_fire
        "Mistä ne ampuu?!": "Where are they shooting from?!",
        "En näe niitä!": "I can't see them!",
        # C.moving
        "Liikkeelle!": "Moving!",
        "Suojaa!": "Cover me!",
        # C.covering
        "Suojaan!": "Covering!",
        # C.out_of_ammo
        "Patruunat loppu!": "I'm out of ammo!",
        # C.got_him
        "Sain sen!": "Got him!",
        # C.shelling
        "Tykistöä! Maahan!": "Artillery! Get down!",
        # C.panic
        "En kestä!": "I can't take it!",
        "Kaikki kuolee!": "We're all going to die!",
        # C.nco_fire
        "Ampukaa! Ampukaa!": "Shoot! Shoot!",
        # BANTER
        "Onko kotoa tullut kirjettä?": "Any letter from home?",
        "Äiti kirjoitti, että lehmä poikii.": "Mother wrote that the cow's calving.",
        "Taas hernekeittoa.": "Pea soup again.",
        "Parempi kuin ei mitään.": "Better than nothing.",
        "Onko tupakkaa?": "Got any tobacco?",
        "Viimeinen. Jaetaan.": "My last one. We'll share it.",
        "Hiljaista.": "Quiet.",
        "Älä sano noin.": "Don't say that.",
        "Sodan jälkeen menen saunaan viikoksi.": "After the war I'm going to sit in the sauna for a week.",
        "Minä tulen mukaan.": "I'm coming with you.",
    },
    # ==================== Hungarian
    "hu": {
        # shouts.attack
        "Előre!": "Forward!",
        "Rajta!": "At 'em!",
        "Hajrá!": "Come on!",
        # shouts.grenade
        "Kézigránát!": "Hand grenade!",
        # shouts.medic
        "Szanitéc!": "Medic!",
        "Segítség!": "Help!",
        "Anyám!": "Mother!",
        # shouts.reload
        "Töltök!": "Reloading!",
        # shouts.contact
        "Ellenség!": "Enemy!",
        "Oroszok!": "Russians!",
        # shouts.retreat
        "Vissza!": "Fall back!",
        # shouts.surrender
        "Ne lőjetek!": "Don't shoot!",
        # shouts.tank
        "Tank!": "Tank!",
        # shouts.sniper
        "Mesterlövész!": "Sniper!",
        # shouts.mg
        "Géppuska!": "Machine gun!",
        # shouts.pain
        "Jaj!": "Ow!",
        "Aaah!": "Aaah!",
        # ACK
        "Igenis!": "Yes, sir!",
        "Értettem!": "Understood!",
        "Parancs!": "At your command!",
        # P.follow_me
        "Én vezetek!": "I'm in charge!",
        "Utánam!": "After me!",
        "Kövessetek!": "Follow me!",
        # P.ambush_fire
        "Tűz!": "Fire!",
        "Most! Tűz!": "Now! Fire!",
        # P.seen_fire
        "Észrevettek - tűz!": "They've spotted us - fire!",
        # P.fire_control
        "Célpont a géppuska - tűz!": "Target, the machine gun - fire!",
        # P.smoke
        "Füstöt!": "Smoke!",
        # P.flank
        "Oldalról!": "From the flank!",
        "Kerüljétek meg!": "Go round them!",
        # P.resupplied
        "Mindenki megvan? Gyerünk!": "Everyone set? Let's go!",
        # P.medic_comfort
        "Tarts ki, itt vagyok.": "Hold on, I'm here.",
        "Minden rendben lesz.": "Everything will be all right.",
        # P.medic_coming
        "Jövök!": "Coming!",
        "Tarts ki!": "Hold on!",
        # P.fire_mission
        "Tüzérségi tüzet!": "Artillery fire!",
        "Üteg, tűz!": "Battery, fire!",
        # P.ammo
        "Lőszert!": "Ammo!",
        # P.runner
        "Megyek!": "Going!",
        # P.senior_now
        "Most te vagy a rangidős. Tiéd a raj.": "You're the senior man now. The squad's yours.",
        # P.lt_down
        "A hadnagy elesett!": "The lieutenant's been killed!",
        # P.capt_down
        "A százados elesett!": "The captain's been killed!",
        # P.o_hold
        "Tartsátok az állást! Fedezékbe!": "Hold the position! Take cover!",
        # P.o_dig
        "Ássátok be magatokat!": "Dig yourselves in!",
        # P.o_move
        "Előre! Gyorsan!": "Forward! Quickly!",
        # P.o_return_fire
        "Csak viszonozzátok a tüzet!": "Return fire only!",
        # P.o_fire_at_will
        "Szabad tüzelés!": "Fire at will!",
        # P.o_ambush
        "Le! Senki nem lő parancs nélkül!": "Down! Nobody fires without orders!",
        # P.o_suppress
        "Lefogó tüzet!": "Suppressing fire!",
        # P.o_regroup
        "Gyülekező!": "Regroup!",
        # P.o_mount
        "Beszállás!": "Mount up!",
        # P.o_dismount
        "Kiszállás!": "Dismount!",
        # P.o_resupply
        "Lőszerfeltöltés!": "Resupply ammunition!",
        # P.o_report
        "Jelentést!": "Report!",
        # P.t_help
        "Kötözd be!": "Bandage him!",
        # P.t_ammo
        "Vigyél neki lőszert!": "Take him some ammo!",
        # P.t_gun
        "A géppuskához!": "Man the machine gun!",
        # P.t_down
        "Le, te idióta!": "Get down, you idiot!",
        # P.t_come
        "Gyere vissza!": "Come back!",
        # P.t_fire
        "Lőj már!": "Shoot, will you!",
        # P.t_dig
        "Áss!": "Dig!",
        # P.t_runner
        "Vidd el neki! Fuss!": "Take it to him! Run!",
        # P.t_fetch
        "Hozz lőszert!": "Bring ammo!",
        # P.t_scout
        "Nézz körül odaát.": "Go and look around over there.",
        # P.t_escort
        "Vidd hátra a foglyokat.": "Take the prisoners to the rear.",
        # P.praise
        "Szép munka.": "Nice work.",
        # P.rebuke
        "Ez parancs!": "That's an order!",
        # P.ff_rebuke
        "Vigyázz, hová lősz!": "Watch where you're shooting!",
        # P.arrest
        "Dobd el a fegyvert!": "Drop your weapon!",
        # P.murder
        "A sajátjainkra lő! Fogjátok el!": "He's shooting at our own! Seize him!",
        # P.share_ammo
        "Tessék, fogd!": "Here, take it!",
        # C.hit_light
        "Eltaláltak!": "I'm hit!",
        "A francba! Megsebesültem!": "Damn it! I'm wounded!",
        # C.hit_bad
        "Szanitéc! SZANITÉC!": "Medic! MEDIC!",
        "Segítség! Segítsetek!": "Help! Help me!",
        "Istenem, Istenem!": "My God, my God!",
        # C.part
        "A {part}m! A {part}m!": "My {part}! My {part}!",
        # C.dying
        "Anyám... anyám...": "Mother... Mother...",
        "Nem akarok meghalni...": "I don't want to die...",
        # C.buddy_down
        "{name}! {name} megsebesült!": "{name}! {name}'s wounded!",
        # C.buddy_dead
        "{name} meghalt!": "{name}'s dead!",
        # C.under_fire
        "Honnan lőnek?!": "Where are they shooting from?!",
        "Földre!": "Get down!",
        # C.shelling
        "Tüzérség! Földre!": "Artillery! Get down!",
        # BANTER
        "Jött levél otthonról?": "Any letter from home?",
        "Semmi. Hónapok óta semmi.": "Nothing. Nothing for months.",
        "Van egy cigid?": "Got a smoke?",
        "Az utolsó. Megfelezzük.": "My last one. We'll split it.",
        "Túl nagy a csend.": "It's too quiet.",
        "Ne mondd ezt.": "Don't say that.",
        "Mikor megyünk haza?": "When are we going home?",
        "Ha lesz még hova.": "If there's still a home to go to.",
    },
    # ==================== Romanian
    "ro": {
        # shouts.attack
        "Înainte!": "Forward!",
        "Ura!": "Hurrah!",
        "La atac!": "Attack!",
        # shouts.grenade
        "Grenadă!": "Grenade!",
        # shouts.medic
        "Sanitar!": "Medic!",
        "Ajutor!": "Help!",
        "Mamă!": "Mama!",
        # shouts.reload
        "Reîncarc!": "Reloading!",
        # shouts.contact
        "Inamicul!": "The enemy!",
        "Rușii!": "The Russians!",
        # shouts.retreat
        "Retragerea!": "Retreat!",
        # shouts.surrender
        "Nu trageți!": "Don't shoot!",
        # shouts.tank
        "Tanc!": "Tank!",
        # shouts.sniper
        "Lunetist!": "Sniper!",
        # shouts.mg
        "Mitralieră!": "Machine gun!",
        # shouts.pain
        "Au!": "Ow!",
        "Aaah!": "Aaah!",
        # ACK
        "Să trăiți!": "Yes, sir!",
        "Am înțeles!": "Understood!",
        "Ordonați!": "Your orders, sir!",
        # P.follow_me
        "Preiau comanda!": "I'm taking command!",
        "După mine!": "After me!",
        "Urmați-mă!": "Follow me!",
        # P.ambush_fire
        "Foc!": "Fire!",
        "Acum! Foc!": "Now! Fire!",
        # P.seen_fire
        "Ne-au văzut - foc!": "They've seen us - fire!",
        # P.fire_control
        "Ținta, mitraliera - foc!": "Target, the machine gun - fire!",
        # P.smoke
        "Fum!": "Smoke!",
        # P.flank
        "Pe flanc!": "Take the flank!",
        "Încercuiți-i!": "Surround them!",
        # P.resupplied
        "Toată lumea are? Să mergem!": "Everyone got some? Let's go!",
        # P.medic_comfort
        "Rezistă, sunt aici.": "Hold on, I'm here.",
        "O să fie bine.": "It'll be all right.",
        # P.medic_coming
        "Vin!": "Coming!",
        "Rezistă!": "Hold on!",
        # P.fire_mission
        "Foc de artilerie!": "Artillery fire!",
        "Bateria, foc!": "Battery, fire!",
        # P.ammo
        "Muniție!": "Ammo!",
        # P.runner
        "Plec!": "Going!",
        "Imediat!": "Right away!",
        # P.senior_now
        "Acum tu ești cel mai mare în grad. Grupa e a ta.": "You're the ranking man now. The squad's yours.",
        # P.lt_down
        "Locotenentul a căzut!": "The lieutenant's been killed!",
        # P.capt_down
        "Căpitanul a căzut!": "The captain's been killed!",
        # P.o_hold
        "Țineți poziția! La adăpost!": "Hold the position! Take cover!",
        # P.o_dig
        "Săpați-vă!": "Dig in!",
        # P.o_move
        "Înainte! Repede!": "Forward! Quickly!",
        # P.o_return_fire
        "Doar ripostați!": "Return fire only!",
        # P.o_fire_at_will
        "Foc la liber!": "Fire at will!",
        # P.o_ambush
        "Jos! Nimeni nu trage până nu zic eu!": "Down! Nobody fires till I say so!",
        # P.o_suppress
        "Foc de acoperire!": "Covering fire!",
        # P.o_regroup
        "Adunarea!": "Regroup!",
        # P.o_mount
        "Îmbarcarea!": "Mount up!",
        # P.o_dismount
        "Debarcarea!": "Dismount!",
        # P.o_resupply
        "Aprovizionarea!": "Resupply!",
        # P.o_report
        "Raportul!": "Report!",
        # P.t_help
        "Pansează-l!": "Bandage him!",
        # P.t_ammo
        "Du-i muniție!": "Take him some ammo!",
        # P.t_gun
        "La armă!": "Man the gun!",
        # P.t_down
        "Jos, idiotule!": "Get down, you idiot!",
        # P.t_come
        "Vino înapoi!": "Come back!",
        # P.t_fire
        "Trage!": "Shoot!",
        # P.t_dig
        "Sapă!": "Dig!",
        # P.t_runner
        "Du-i asta! Fugi!": "Take him this! Run!",
        # P.t_fetch
        "Adu muniție!": "Bring ammo!",
        # P.t_scout
        "Du-te și vezi.": "Go and see.",
        # P.t_escort
        "Du prizonierii în spate.": "Take the prisoners to the rear.",
        # P.praise
        "Bravo.": "Well done.",
        # P.rebuke
        "E un ordin!": "That's an order!",
        # P.ff_rebuke
        "Atenție unde tragi!": "Watch where you're shooting!",
        # P.arrest
        "Aruncă arma!": "Drop your weapon!",
        # P.murder
        "Trage în ai noștri! Prindeți-l!": "He's shooting at our own! Grab him!",
        # P.share_ammo
        "Poftim, ia!": "Here, take it!",
        # C.hit_light
        "Sunt lovit!": "I'm hit!",
        "La naiba! M-au lovit!": "Damn it! They got me!",
        # C.hit_bad
        "Sanitar! SANITAR!": "Medic! MEDIC!",
        "Ajutor! Ajutați-mă!": "Help! Help me!",
        "Doamne, Doamne!": "God, oh God!",
        # C.part
        "{part}! {part} mea!": "My {part}! Oh, my {part}!",
        # C.dying
        "Mamă... mamă...": "Mama... Mama...",
        "Nu vreau să mor...": "I don't want to die...",
        # C.buddy_down
        "{name}! L-au lovit pe {name}!": "{name}! They got {name}!",
        # C.buddy_dead
        "{name} a murit!": "{name}'s dead!",
        # C.under_fire
        "De unde trag?!": "Where are they shooting from?!",
        "La pământ!": "Get down!",
        # C.shelling
        "Artileria! La pământ!": "Artillery! Get down!",
        # BANTER
        "Ai primit scrisoare de acasă?": "Any letter from home?",
        "Nimic. De luni de zile.": "Nothing. Not for months.",
        "Ai o țigară?": "Got a cigarette?",
        "Ultima. O împărțim.": "My last one. We'll share it.",
        "E prea liniște.": "It's too quiet.",
        "Nu spune asta.": "Don't say that.",
        "Când mergem acasă?": "When are we going home?",
        "Când se termină. Dacă se termină.": "When it's over. If it's ever over.",
    },
    # ==================== Chinese (pinyin)
    "zh": {
        # shouts.attack
        "Chōng a!": "Charge!",
        "Shā!": "Kill!",
        "Forward!": "Forward!",
        # shouts.grenade
        "Shǒuliúdàn!": "Grenade!",
        # shouts.medic
        "Wèishēngbīng!": "Medic!",
        "Jiù mìng!": "Help!",
        # shouts.reload
        "Huàn dànjiā!": "Changing clips!",
        # shouts.contact
        "Rìběn guǐzi!": "Japanese devils!",
        "Enemy!": "Enemy!",
        # shouts.retreat
        "Chèntuì!": "Retreat!",
        # shouts.surrender
        "Bié kāi qiāng!": "Don't shoot!",
        # shouts.tank
        "Tǎnkè!": "Tank!",
        # shouts.sniper
        "Jūjī shǒu!": "Sniper!",
        # shouts.mg
        "Jīqiāng!": "Machine gun!",
        # shouts.pain
        "Āiyō!": "Ow!",
        "Aaa!": "Aaah!",
        # ACK
        "Shì!": "Yes, sir!",
        "Míngbai!": "Understood!",
        "Zūnmìng!": "As you command!",
        # P.follow_me
        "Tīng wǒ zhǐhuī!": "Take my orders!",
        "Gēn wǒ lái!": "Follow me!",
        # P.ambush_fire
        "Kāi huǒ!": "Open fire!",
        "Dǎ!": "Let them have it!",
        # P.seen_fire
        "Bèi fāxiàn le, kāi huǒ!": "We've been spotted - open fire!",
        # P.fire_control
        "Dǎ nà tǐng jīqiāng!": "Hit that machine gun!",
        # P.smoke
        "Fàng yānwù!": "Lay smoke!",
        # P.flank
        "Cóng cèyì bāochāo!": "Hit them from the flank!",
        "Rào guòqù!": "Go round!",
        # P.resupplied
        "Dōu bǔjǐ hǎo le ma? Zǒu!": "Everyone resupplied? Move!",
        # P.medic_comfort
        "Tǐng zhù!": "Hold on!",
        "Méi shì de.": "You'll be all right.",
        # P.medic_coming
        "Wǒ lái le!": "I'm coming!",
        # P.fire_mission
        "Pàobīng zhīyuán!": "Artillery support!",
        # P.ammo
        "Dànyào!": "Ammo!",
        # P.runner
        "Shì! Mǎshàng qù!": "Yes, sir! Going now!",
        # P.senior_now
        "Xiànzài nǐ zuì zīshēn. Zhège bān guī nǐ le.": "You're the most senior now. The squad's yours.",
        # P.lt_down
        "Páizhǎng xīshēng le!": "The platoon leader has fallen!",
        # P.capt_down
        "Liánzhǎng xīshēng le!": "The company commander has fallen!",
        # P.o_hold
        "Shǒu zhù! Duǒ hǎo!": "Hold here! Get under cover!",
        # P.o_dig
        "Wā zhànhào!": "Dig trenches!",
        # P.o_move
        "Qiánjìn! Kuài!": "Advance! Quick!",
        # P.o_return_fire
        "Zhǐ néng huánjī!": "Return fire only!",
        # P.o_fire_at_will
        "Zìyóu kāi huǒ!": "Fire at will!",
        # P.o_ambush
        "Pā xià! Méi mìnglìng bù xǔ kāi qiāng!": "Get down! Nobody fires without orders!",
        # P.o_suppress
        "Huǒlì yāzhì!": "Suppressing fire!",
        # P.o_regroup
        "Jíhé!": "Fall in!",
        # P.o_mount
        "Shàng chē!": "Mount up!",
        # P.o_dismount
        "Xià chē!": "Dismount!",
        # P.o_resupply
        "Qù lǐng dànyào!": "Go and draw ammunition!",
        # P.o_report
        "Huìbào!": "Report!",
        # P.t_help
        "Gěi tā bāozā!": "Bandage him!",
        # P.t_ammo
        "Gěi tā sòng dànyào!": "Take him some ammo!",
        # P.t_gun
        "Qù ná nà tǐng qiāng!": "Go and grab that gun!",
        # P.t_down
        "Pā xià, bèndàn!": "Get down, you idiot!",
        # P.t_come
        "Huí lái!": "Come back!",
        # P.t_fire
        "Kāi qiāng a!": "Shoot, will you!",
        # P.t_dig
        "Wā!": "Dig!",
        # P.t_runner
        "Bǎ zhège sòng guòqù! Kuài pǎo!": "Take this over there! Run!",
        # P.t_fetch
        "Qù ná dànyào!": "Go and get ammo!",
        # P.t_scout
        "Qù zhēnchá yīxià.": "Go and scout around.",
        # P.t_escort
        "Bǎ fúlǔ dài dào hòufāng.": "Take the prisoners to the rear.",
        # P.praise
        "Hǎo yàng de.": "Good man.",
        # P.rebuke
        "Zhè shì mìnglìng!": "That's an order!",
        # P.ff_rebuke
        "Kàn zhǔn le zài dǎ!": "Look before you shoot!",
        # P.arrest
        "Fàng xià wǔqì!": "Put down your weapon!",
        # P.murder
        "Tā dǎ zìjǐ rén! Zhuā zhù tā!": "He's shooting our own! Grab him!",
        # P.share_ammo
        "Gěi, ná zhe!": "Here, take it!",
        # C.hit_light
        "Wǒ zhòng dàn le!": "I'm hit!",
        "Tā mā de! Zhòng dàn le!": "Goddamn it! I'm hit!",
        # C.hit_bad
        "Wèishēngbīng! WÈISHĒNGBĪNG!": "Medic! MEDIC!",
        "Jiùmìng! Jiù jiù wǒ!": "Help! Save me!",
        # C.part
        "Wǒ de {part}! Wǒ de {part}!": "My {part}! My {part}!",
        # C.dying
        "Mā... mā...": "Ma... Ma...",
        "Wǒ bù xiǎng sǐ...": "I don't want to die...",
        # C.buddy_down
        "{name}! {name} zhòng dàn le!": "{name}! {name}'s hit!",
        # C.buddy_dead
        "{name} xīshēng le!": "{name} has fallen!",
        # C.under_fire
        "Cóng nǎlǐ dǎ lái de?!": "Where's it coming from?!",
        "Wò dǎo!": "Get down!",
        # C.shelling
        "Pàojī! Wò dǎo!": "Shells! Get down!",
        # BANTER
        "Jiā li lái xìn le ma?": "Any letter from home?",
        "Méiyǒu. Hǎo jǐ ge yuè le.": "No. Not for months now.",
        "Yòu shì xīfàn.": "Thin gruel again.",
        "Yǒu chī de jiù bù cuò le.": "Be glad there's anything to eat.",
        "Yǒu yān ma?": "Got a smoke?",
        "Zuìhòu yī gēn. Yīrén yī kǒu.": "My last one. A drag each.",
        "Tài ānjìng le.": "It's too quiet.",
        "Bié zhème shuō.": "Don't say that.",
        "Dǎ wán zhàng wǒ jiù huí jiā zhòng dì.": "When the war's over I'm going home to farm.",
        "Wǒ bāng nǐ.": "I'll help you.",
    },
}

# the native body-part words of chatter.PART (what {part} is filled with), in English
PART_EN = {
    "de": {"Kopf": "head", "Brust": "chest", "Arm": "arm", "Bein": "leg"},
    "ru": {"golova": "head", "grud'": "chest", "ruka": "arm", "noga": "leg"},
    "ja": {"atama": "head", "mune": "chest", "ude": "arm", "ashi": "leg"},
    "it": {"testa": "head", "petto": "chest", "braccio": "arm", "gamba": "leg"},
    "fr": {"tête": "head", "poitrine": "chest", "bras": "arm", "jambe": "leg"},
    "pl": {"głowa": "head", "pierś": "chest", "ręka": "arm", "noga": "leg"},
    "fi": {"pää": "head", "rinta": "chest", "käsi": "arm", "jalka": "leg"},
    "hu": {"fej": "head", "mell": "chest", "kar": "arm", "láb": "leg"},
    "ro": {"capul": "head", "pieptul": "chest", "mâna": "arm", "piciorul": "leg"},
    "zh": {"tóu": "head", "xiōng": "chest", "gēbo": "arm", "tuǐ": "leg"},
}
