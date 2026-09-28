"""Who commanded what, and when: the top of every soldier's chain of command.

NATIONAL: each nation's high command, from the army's chief up to the head of state,
by date.  FORMATIONS: for each battle, the historical army groups, armies, corps and
divisions (and a few regiments and battalions) with their commanders - and what
became of them.  Grades are on the common 0-18 scale (see ranks.py); a string is a
title instead (heads of state, admirals).

Holders: (from, to, grade or title, name, fate).  Dates are (y, m, d); None is open.
The fate describes how the holding ended: "killed", "wounded", "relieved", ...
"""
from __future__ import annotations

# grade shorthands (1* .. 5*)
B1, S2, S3, S4, S5 = 14, 15, 16, 17, 18
COL, LTC, MAJ = 13, 12, 11

NATIONAL = {
    "usa": [
        ("Army Chief of Staff", [((1939, 9, 1), None, S4, "George C. Marshall", None)]),
        ("Commander-in-Chief (the President)", [(None, (1945, 4, 12), "President", "Franklin D. Roosevelt",
                                                 "died at Warm Springs"),
                                                ((1945, 4, 12), None, "President", "Harry S. Truman", None)]),
    ],
    "uk": [
        ("Chief of the Imperial General Staff", [(None, (1940, 5, 27), S4, "Edmund Ironside", "replaced"),
                                                 ((1940, 5, 27), (1941, 12, 25), S4, "John Dill", "replaced"),
                                                 ((1941, 12, 25), None, S4, "Alan Brooke", None)]),
        ("Prime Minister", [(None, (1940, 5, 10), "Prime Minister", "Neville Chamberlain", "resigned"),
                            ((1940, 5, 10), (1945, 7, 26), "Prime Minister", "Winston Churchill", "voted out"),
                            ((1945, 7, 26), None, "Prime Minister", "Clement Attlee", None)]),
        ("The King", [(None, None, "King", "George VI", None)]),
    ],
    "canada": [
        ("Prime Minister", [(None, None, "Prime Minister", "W. L. Mackenzie King", None)]),
        ("The King", [(None, None, "King", "George VI", None)]),
    ],
    "australia": [
        ("Prime Minister", [(None, (1941, 8, 29), "Prime Minister", "Robert Menzies", "resigned"),
                            ((1941, 8, 29), (1941, 10, 7), "Prime Minister", "Arthur Fadden", "lost office"),
                            ((1941, 10, 7), (1945, 7, 5), "Prime Minister", "John Curtin", "died in office"),
                            ((1945, 7, 6), (1945, 7, 13), "Prime Minister", "Frank Forde", "replaced"),
                            ((1945, 7, 13), None, "Prime Minister", "Ben Chifley", None)]),
        ("The King", [(None, None, "King", "George VI", None)]),
    ],
    "newzealand": [
        ("Prime Minister", [(None, (1940, 3, 27), "Prime Minister", "Michael Joseph Savage", "died in office"),
                            ((1940, 3, 27), None, "Prime Minister", "Peter Fraser", None)]),
        ("The King", [(None, None, "King", "George VI", None)]),
    ],
    "india": [
        ("Commander-in-Chief, India", [(None, (1941, 1, 27), S4, "Robert Cassels", "retired"),
                                       ((1941, 1, 27), (1941, 7, 5), S4, "Claude Auchinleck", "posted to Cairo"),
                                       ((1941, 7, 5), (1943, 6, 20), S4, "Archibald Wavell", "made Viceroy"),
                                       ((1943, 6, 20), None, S4, "Claude Auchinleck", None)]),
        ("Viceroy", [(None, (1943, 10, 1), "Viceroy", "Lord Linlithgow", "term ended"),
                     ((1943, 10, 1), None, "Viceroy", "Lord Wavell", None)]),
        ("The King-Emperor", [(None, None, "King-Emperor", "George VI", None)]),
    ],
    "ussr": [
        ("Chief of the General Staff", [(None, (1940, 8, 10), S5, "Boris Shaposhnikov", "replaced"),
                                        ((1940, 8, 10), (1941, 1, 14), S4, "Kirill Meretskov", "replaced"),
                                        ((1941, 1, 14), (1941, 7, 29), S4, "Georgy Zhukov", "sent to the front"),
                                        ((1941, 7, 29), (1942, 5, 11), S5, "Boris Shaposhnikov", "ill health"),
                                        ((1942, 5, 11), (1945, 2, 18), S5, "Aleksandr Vasilevsky", "sent to the front"),
                                        ((1945, 2, 18), None, S4, "Aleksei Antonov", None)]),
        ("Supreme Commander-in-Chief", [(None, (1941, 8, 8), "General Secretary", "Joseph Stalin", None),
                                        ((1941, 8, 8), None, "Supreme Commander", "Joseph Stalin", None)]),
    ],
    "france": [
        ("Commander-in-Chief", [(None, (1940, 5, 19), S4, "Maurice Gamelin", "dismissed"),
                                ((1940, 5, 19), (1940, 6, 25), S4, "Maxime Weygand", "armistice"),
                                ((1944, 8, 1), None, S4, "Alphonse Juin", None)]),
        ("Head of Government", [(None, (1940, 3, 21), "Président du Conseil", "Édouard Daladier", "resigned"),
                                ((1940, 3, 21), (1940, 6, 16), "Président du Conseil", "Paul Reynaud", "resigned"),
                                ((1940, 6, 16), (1944, 6, 3), "Head of the French State", "Philippe Pétain",
                                 "fled with the Germans"),
                                ((1944, 6, 3), None, "Head of the Provisional Government", "Charles de Gaulle", None)]),
    ],
    "poland": [
        ("Commander-in-Chief", [(None, (1939, 11, 7), S5, "Edward Rydz-Śmigły", "fled to Romania"),
                                ((1939, 11, 7), (1943, 7, 4), S4, "Władysław Sikorski",
                                 "killed when his aircraft crashed off Gibraltar"),
                                ((1943, 7, 8), (1944, 9, 30), S4, "Kazimierz Sosnkowski", "dismissed"),
                                ((1944, 9, 30), None, S4, "Tadeusz Bór-Komorowski", None)]),
        ("President", [(None, (1939, 9, 30), "President", "Ignacy Mościcki", "interned in Romania"),
                       ((1939, 9, 30), None, "President (in exile)", "Władysław Raczkiewicz", None)]),
    ],
    "china": [
        ("Chief of the General Staff", [(None, (1944, 12, 1), S4, "He Yingqin", "replaced"),
                                        ((1944, 12, 1), None, S4, "Chen Cheng", None)]),
        ("Chairman of the National Military Council", [(None, None, "Generalissimo", "Chiang Kai-shek", None)]),
    ],
    "germany": [
        ("Chief of the Army General Staff", [(None, (1942, 9, 24), S4, "Franz Halder", "dismissed"),
                                             ((1942, 9, 24), (1944, 7, 10), S4, "Kurt Zeitzler", "reported sick"),
                                             ((1944, 7, 21), (1945, 3, 28), S4, "Heinz Guderian", "dismissed"),
                                             ((1945, 4, 1), (1945, 5, 2), S3, "Hans Krebs", "shot himself")]),
        ("Commander-in-Chief of the Army", [(None, (1941, 12, 19), S5, "Walther von Brauchitsch", "dismissed"),
                                            ((1941, 12, 19), (1945, 4, 30), "Führer", "Adolf Hitler", None),
                                            ((1945, 4, 30), None, S5, "Ferdinand Schörner", None)]),
        ("Chief of the OKW", [(None, None, S5, "Wilhelm Keitel", None)]),
        ("Führer and Supreme Commander", [(None, (1945, 4, 30), "Führer", "Adolf Hitler",
                                           "shot himself in the bunker"),
                                          ((1945, 4, 30), None, "Reichspräsident", "Karl Dönitz", None)]),
    ],
    "italy": [
        ("Chief of the Supreme General Staff", [(None, (1940, 12, 4), S5, "Pietro Badoglio", "resigned"),
                                                ((1940, 12, 6), (1943, 2, 1), S5, "Ugo Cavallero", "dismissed"),
                                                ((1943, 2, 1), None, S4, "Vittorio Ambrosio", None)]),
        ("Head of Government", [(None, (1943, 7, 25), "Duce", "Benito Mussolini", "deposed and arrested"),
                                ((1943, 7, 25), (1944, 6, 9), "Prime Minister", "Pietro Badoglio", "resigned"),
                                ((1944, 6, 18), None, "Prime Minister", "Ivanoe Bonomi", None)]),
        ("The King", [(None, None, "King", "Victor Emmanuel III", None)]),
    ],
    "japan": [
        ("Chief of the Army General Staff", [(None, (1940, 10, 3), S5, "Prince Kan'in", "retired"),
                                             ((1940, 10, 3), (1944, 2, 21), S4, "Hajime Sugiyama", "replaced"),
                                             ((1944, 2, 21), (1944, 7, 18), S4, "Hideki Tojo", "resigned"),
                                             ((1944, 7, 18), None, S4, "Yoshijirō Umezu", None)]),
        ("Prime Minister", [(None, (1940, 7, 22), "Prime Minister", "Mitsumasa Yonai", "resigned"),
                            ((1940, 7, 22), (1941, 10, 18), "Prime Minister", "Fumimaro Konoe", "resigned"),
                            ((1941, 10, 18), (1944, 7, 22), "Prime Minister", "Hideki Tojo",
                             "resigned after Saipan"),
                            ((1944, 7, 22), (1945, 4, 7), "Prime Minister", "Kuniaki Koiso", "resigned"),
                            ((1945, 4, 7), None, "Prime Minister", "Kantarō Suzuki", None)]),
        ("The Emperor", [(None, None, "Emperor", "Hirohito", None)]),
    ],
    "finland": [
        ("Commander-in-Chief", [(None, None, S5, "C. G. E. Mannerheim", None)]),
        ("President", [(None, (1940, 12, 19), "President", "Kyösti Kallio", "resigned, and died that day"),
                       ((1940, 12, 19), (1944, 8, 4), "President", "Risto Ryti", "resigned"),
                       ((1944, 8, 4), None, "President", "C. G. E. Mannerheim", None)]),
    ],
    "hungary": [
        ("Chief of the General Staff", [(None, (1941, 9, 6), S4, "Henrik Werth", "dismissed"),
                                        ((1941, 9, 6), (1944, 4, 19), S4, "Ferenc Szombathelyi", "dismissed"),
                                        ((1944, 4, 19), None, S4, "János Vörös", None)]),
        ("Head of State", [(None, (1944, 10, 16), "Regent", "Miklós Horthy", "overthrown by the Germans"),
                           ((1944, 10, 16), None, "Leader of the Nation", "Ferenc Szálasi", None)]),
    ],
    "romania": [
        ("Conducător", [((1940, 9, 14), (1944, 8, 23), S5, "Ion Antonescu", "arrested by the King")]),
        ("The King", [(None, (1940, 9, 6), "King", "Carol II", "abdicated"),
                      ((1940, 9, 6), None, "King", "Michael I", None)]),
    ],
}

# a different high command in a particular battle (the Polish People's Army at Berlin; Mussolini's republic)
NATIONAL_OVERRIDE = {
    "berlin45": {"poland": [
        ("Commander-in-Chief, Polish Army", [(None, None, S4, "Michał Rola-Żymierski", None)]),
        ("Chairman of the State National Council", [(None, None, "Chairman", "Bolesław Bierut", None)]),
    ]},
}

# formation records: (nations, echelon, name, parent name, holders)
F = {}


def _f(theatre, nations, echelon, name, parent, holders):
    F.setdefault(theatre, []).append((tuple(nations) if isinstance(nations, (list, tuple)) else (nations,),
                                      echelon, name, parent, holders))


# ------------------------------------------------------------------ 1939-40
_f("poland39", "germany", "army group", "Heeresgruppe Süd", None, [(None, None, S4, "Gerd von Rundstedt", None)])
_f("poland39", "germany", "army", "8. Armee", "Heeresgruppe Süd", [(None, None, S3, "Johannes Blaskowitz", None)])
_f("poland39", "germany", "division", "30. Infanterie-Division", "8. Armee", [(None, None, S2, "Kurt von Briesen", None)])
_f("poland39", "germany", "division", "24. Infanterie-Division", "8. Armee", [(None, None, S2, "Friedrich Olbricht", None)])
_f("poland39", "germany", "division", "1. Panzer-Division", "Heeresgruppe Süd", [(None, None, S2, "Rudolf Schmidt", None)])
_f("poland39", "germany", "division", "SS-Leibstandarte", "8. Armee", [(None, None, S3, "Sepp Dietrich", None)])
_f("poland39", "poland", "army", "Armia Poznań", None, [(None, None, S2, "Tadeusz Kutrzeba", None)])
_f("poland39", "poland", "division", "14th Infantry Division", "Armia Poznań", [(None, None, B1, "Franciszek Wład", None)])
_f("poland39", "poland", "division", "25th Infantry Division", "Armia Poznań", [(None, None, B1, "Franciszek Alter", None)])
_f("poland39", "poland", "brigade", "Podolska Cavalry Brigade", "Armia Poznań", [(None, None, COL, "Leon Strzelecki", None)])

_f("france40", "germany", "army group", "Heeresgruppe A", None, [(None, None, S4, "Gerd von Rundstedt", None)])
_f("france40", "germany", "army", "Panzergruppe Kleist", "Heeresgruppe A", [(None, None, S3, "Ewald von Kleist", None)])
_f("france40", "germany", "corps", "XIX. Armeekorps (mot.)", "Panzergruppe Kleist", [(None, None, S3, "Heinz Guderian", None)])
_f("france40", "germany", "division", "1. Panzer-Division", "XIX. Armeekorps (mot.)", [(None, None, S2, "Friedrich Kirchner", None)])
_f("france40", "germany", "division", "10. Panzer-Division", "XIX. Armeekorps (mot.)", [(None, None, S2, "Ferdinand Schaal", None)])
_f("france40", "germany", "regiment", "Infanterie-Regiment Großdeutschland", "XIX. Armeekorps (mot.)",
   [(None, None, COL, "Gerhard Graf von Schwerin", None)])
_f("france40", ("france", "uk"), "army group", "1er Groupe d'Armées", None,
   [(None, (1940, 5, 23), S4, "Gaston Billotte", "killed in a car crash"),
    ((1940, 5, 25), None, S4, "Georges Blanchard", None)])
_f("france40", "france", "army", "2e Armée", "1er Groupe d'Armées", [(None, None, S4, "Charles Huntziger", None)])
_f("france40", "france", "corps", "10e Corps d'Armée", "2e Armée", [(None, None, S3, "Pierre Grandsard", None)])
_f("france40", "france", "division", "55e Division d'Infanterie", "10e Corps d'Armée", [(None, None, B1, "Henri Lafontaine", None)])
_f("france40", "france", "division", "71e Division d'Infanterie", "10e Corps d'Armée", [(None, None, B1, "Joseph Baudet", None)])
_f("france40", "france", "division", "3e Division Cuirassée", "2e Armée",
   [(None, (1940, 5, 18), B1, "Antoine Brocard", "relieved"), ((1940, 5, 18), None, B1, "Louis Buisson", None)])
_f("france40", "uk", "army", "British Expeditionary Force", "1er Groupe d'Armées", [(None, None, S4, "Lord Gort", None)])

# ------------------------------------------------------------------ 1941
_f("crete41", "germany", "corps", "XI. Fliegerkorps", None, [(None, None, S3, "Kurt Student", None)])
_f("crete41", "germany", "division", "7. Flieger-Division", "XI. Fliegerkorps",
   [(None, (1941, 5, 20), S2, "Wilhelm Süßmann", "killed when his glider broke up"),
    ((1941, 5, 20), None, COL, "Richard Heidrich", None)])
_f("crete41", "germany", "regiment", "Luftlande-Sturm-Regiment", "XI. Fliegerkorps",
   [(None, (1941, 5, 20), B1, "Eugen Meindl", "badly wounded at Maleme"),
    ((1941, 5, 21), None, COL, "Hermann-Bernhard Ramcke", None)])
_f("crete41", "germany", "division", "5. Gebirgs-Division", "XI. Fliegerkorps", [(None, None, S2, "Julius Ringel", None)])
_f("crete41", ("newzealand", "uk", "australia"), "theatre", "Middle East Command", None,
   [(None, None, S4, "Archibald Wavell", None)])
_f("crete41", ("newzealand", "uk", "australia"), "corps", "Creforce", "Middle East Command",
   [(None, None, S2, "Bernard Freyberg", None)])
_f("crete41", ("newzealand", "uk", "australia"), "division", "2nd New Zealand Division", "Creforce",
   [(None, None, B1, "Edward Puttick", None)])
_f("crete41", "newzealand", "battalion", "22nd Battalion", "2nd New Zealand Division", [(None, None, LTC, "Leslie Andrew", None)])
_f("crete41", "newzealand", "battalion", "23rd Battalion", "2nd New Zealand Division", [(None, None, LTC, "Douglas Leckie", None)])
_f("crete41", "newzealand", "battalion", "28th (Maori) Battalion", "2nd New Zealand Division",
   [(None, None, LTC, "George Dittmer", None)])

_f("barbarossa41", "germany", "army group", "Heeresgruppe Mitte", None, [(None, None, S5, "Fedor von Bock", None)])
_f("barbarossa41", "germany", "army", "Panzergruppe 2", "Heeresgruppe Mitte", [(None, None, S4, "Heinz Guderian", None)])
_f("barbarossa41", "germany", "army", "Panzergruppe 3", "Heeresgruppe Mitte", [(None, None, S4, "Hermann Hoth", None)])
_f("barbarossa41", "germany", "division", "17. Panzer-Division", "Panzergruppe 2",
   [(None, (1941, 6, 27), S2, "Hans-Jürgen von Arnim", "wounded"),
    ((1941, 6, 27), (1941, 7, 18), S2, "Karl Ritter von Weber", "mortally wounded by a shell"),
    ((1941, 7, 18), None, S2, "Wilhelm von Thoma", None)])
_f("barbarossa41", "germany", "division", "29. Infanterie-Division (mot.)", "Panzergruppe 2",
   [(None, None, S2, "Walter von Boltenstern", None)])
_f("barbarossa41", "germany", "division", "7. Panzer-Division", "Panzergruppe 3", [(None, None, S2, "Hans von Funck", None)])
_f("barbarossa41", "ussr", "front", "Western Front", None,
   [(None, (1941, 6, 30), S4, "Dmitry Pavlov", "arrested - later shot"),
    ((1941, 6, 30), (1941, 7, 2), S3, "Andrei Yeryomenko", "superseded"),
    ((1941, 7, 2), (1941, 9, 12), S5, "Semyon Timoshenko", "sent south"),
    ((1941, 9, 12), None, S3, "Ivan Konev", None)])
_f("barbarossa41", "ussr", "army", "16th Army", "Western Front", [(None, None, S2, "Mikhail Lukin", None)])
_f("barbarossa41", "ussr", "army", "20th Army", "Western Front", [(None, None, S2, "Pavel Kurochkin", None)])
_f("barbarossa41", "ussr", "division", "1st Moscow Motor Rifle Division", "20th Army",
   [(None, None, COL, "Yakov Kreizer", None)])

_f("moscow41", "ussr", "front", "Western Front", None, [(None, None, S4, "Georgy Zhukov", None)])
_f("moscow41", "ussr", "front", "Kalinin Front", None, [(None, None, S3, "Ivan Konev", None)])
_f("moscow41", "ussr", "division", "78th Rifle Division (Siberian)", "Western Front",
   [(None, None, B1, "Afanasy Beloborodov", None)])
_f("moscow41", "ussr", "division", "316th Rifle Division (Panfilov)", "Western Front",
   [(None, (1941, 11, 18), B1, "Ivan Panfilov", "killed by a mortar bomb"),
    ((1941, 11, 19), None, COL, "Vasily Revyakin", None)])
_f("moscow41", "ussr", "corps", "1st Guards Cavalry Corps", "Western Front", [(None, None, B1, "Pavel Belov", None)])
_f("moscow41", "germany", "army group", "Heeresgruppe Mitte", None,
   [(None, (1941, 12, 18), S5, "Fedor von Bock", "relieved 'on grounds of health'"),
    ((1941, 12, 18), None, S5, "Günther von Kluge", None)])
_f("moscow41", "germany", "army", "2. Panzerarmee", "Heeresgruppe Mitte",
   [(None, (1941, 12, 26), S4, "Heinz Guderian", "dismissed for retreating"),
    ((1941, 12, 26), None, S4, "Rudolf Schmidt", None)])
_f("moscow41", "germany", "division", "2. Panzer-Division", "Heeresgruppe Mitte", [(None, None, S2, "Rudolf Veiel", None)])
_f("moscow41", "germany", "division", "SS-Division Das Reich", "Heeresgruppe Mitte",
   [(None, (1941, 10, 14), S3, "Paul Hausser", "badly wounded - lost an eye"),
    ((1941, 10, 14), None, B1, "Wilhelm Bittrich", None)])
_f("moscow41", "germany", "division", "106. Infanterie-Division", "Heeresgruppe Mitte", [(None, None, S2, "Ernst Dehner", None)])

_f("changsha41", "china", "theatre", "9th War Area", None, [(None, None, S3, "Xue Yue", None)])
_f("changsha41", "china", "army", "74th Army", "9th War Area", [(None, None, S2, "Wang Yaowu", None)])
_f("changsha41", "china", "army", "10th Army", "9th War Area", [(None, None, S2, "Li Yutang", None)])
_f("changsha41", "japan", "theatre", "China Expeditionary Army", None, [(None, None, S4, "Shunroku Hata", None)])
_f("changsha41", "japan", "army", "11th Army", "China Expeditionary Army", [(None, None, S2, "Korechika Anami", None)])

# ------------------------------------------------------------------ 1942
_f("alamein42", ("uk", "australia", "newzealand", "india"), "theatre", "Middle East Command", None, [(None, None, S4, "Harold Alexander", None)])
_f("alamein42", ("uk", "australia", "newzealand", "india"), "army", "Eighth Army", "Middle East Command", [(None, None, S3, "Bernard Montgomery", None)])
_f("alamein42", ("uk", "australia", "newzealand", "india"), "corps", "XXX Corps", "Eighth Army", [(None, None, S3, "Oliver Leese", None)])
_f("alamein42", ("uk", "australia", "newzealand", "india"), "corps", "X Corps", "Eighth Army", [(None, None, S3, "Herbert Lumsden", None)])
_f("alamein42", "uk", "division", "51st Highland Division", "XXX Corps", [(None, None, S2, "Douglas Wimberley", None)])
_f("alamein42", "uk", "division", "7th Armoured Division", "Eighth Army", [(None, None, S2, "John Harding", None)])
_f("alamein42", "uk", "division", "1st Armoured Division", "X Corps", [(None, None, S2, "Raymond Briggs", None)])
_f("alamein42", ("germany", "italy"), "army", "Deutsch-Italienische Panzerarmee", None,
   [(None, (1942, 9, 22), S5, "Erwin Rommel", "flown home sick"),
    ((1942, 9, 22), (1942, 10, 24), S3, "Georg Stumme", "died of a heart attack under fire"),
    ((1942, 10, 24), (1942, 10, 25), S3, "Wilhelm von Thoma", "Rommel returned"),
    ((1942, 10, 25), None, S5, "Erwin Rommel", None)])
_f("alamein42", "germany", "corps", "Deutsches Afrikakorps", "Deutsch-Italienische Panzerarmee",
   [(None, (1942, 11, 4), S3, "Wilhelm von Thoma", "captured at Tel el Mampsra"), ((1942, 11, 4), None, COL, "Fritz Bayerlein", None)])
_f("alamein42", "germany", "division", "15. Panzer-Division", "Deutsches Afrikakorps", [(None, None, S2, "Gustav von Vaerst", None)])
_f("alamein42", "germany", "division", "164. leichte Afrika-Division", "Deutsch-Italienische Panzerarmee",
   [(None, None, S2, "Carl-Hans Lungershausen", None)])
_f("alamein42", "germany", "brigade", "Fallschirmjäger-Brigade Ramcke", "Deutsch-Italienische Panzerarmee",
   [(None, None, S2, "Hermann-Bernhard Ramcke", None)])
_f("alamein42", "italy", "division", "Divisione Folgore", "Deutsch-Italienische Panzerarmee", [(None, None, S2, "Enrico Frattini", None)])
_f("alamein42", "italy", "division", "Divisione Ariete", "Deutsch-Italienische Panzerarmee", [(None, None, B1, "Francesco Arena", None)])
_f("alamein42", "italy", "division", "Divisione Trento", "Deutsch-Italienische Panzerarmee", [(None, None, B1, "Giorgio Masina", None)])

_f("stalingrad42", "ussr", "front", "Stalingrad Front", None, [(None, None, S3, "Andrei Yeryomenko", None)])
_f("stalingrad42", "ussr", "army", "62nd Army", "Stalingrad Front", [(None, None, S2, "Vasily Chuikov", None)])
_f("stalingrad42", "ussr", "division", "13th Guards Rifle Division", "62nd Army", [(None, None, B1, "Aleksandr Rodimtsev", None)])
_f("stalingrad42", "ussr", "division", "284th Rifle Division", "62nd Army", [(None, None, COL, "Nikolai Batyuk", None)])
_f("stalingrad42", "ussr", "division", "37th Guards Rifle Division", "62nd Army", [(None, None, B1, "Viktor Zholudev", None)])
_f("stalingrad42", "germany", "army group", "Heeresgruppe B", None, [(None, None, S4, "Maximilian von Weichs", None)])
_f("stalingrad42", "germany", "army", "6. Armee", "Heeresgruppe B",
   [(None, (1943, 1, 31), S4, "Friedrich Paulus", "surrendered to the Red Army")])
_f("stalingrad42", "germany", "corps", "LI. Armeekorps", "6. Armee", [(None, None, S3, "Walther von Seydlitz-Kurzbach", None)])
_f("stalingrad42", "germany", "division", "14. Panzer-Division", "LI. Armeekorps",
   [(None, (1942, 11, 1), S2, "Ferdinand Heim", "given a corps"), ((1942, 11, 16), None, B1, "Martin Lattmann", None)])
_f("stalingrad42", "germany", "division", "305. Infanterie-Division", "LI. Armeekorps",
   [(None, (1942, 11, 1), S2, "Kurt Oppenländer", "replaced"), ((1942, 11, 1), None, B1, "Bernhard Steinmetz", None)])
_f("stalingrad42", "germany", "division", "389. Infanterie-Division", "LI. Armeekorps",
   [(None, (1942, 11, 1), S2, "Erwin Jaenecke", "given a corps"), ((1942, 11, 1), None, B1, "Erich Magnus", None)])

_f("uranus42", "ussr", "front", "Southwestern Front", None, [(None, None, S2, "Nikolai Vatutin", None)])
_f("uranus42", "ussr", "front", "Don Front", None, [(None, None, S2, "Konstantin Rokossovsky", None)])
_f("uranus42", "ussr", "army", "5th Tank Army", "Southwestern Front", [(None, None, S2, "Prokofy Romanenko", None)])
_f("uranus42", "ussr", "army", "21st Army", "Southwestern Front", [(None, None, B1, "Ivan Chistyakov", None)])
_f("uranus42", "ussr", "corps", "4th Tank Corps", "21st Army", [(None, None, B1, "Andrei Kravchenko", None)])
_f("uranus42", "romania", "army group", "Heeresgruppe B", None, [(None, None, S4, "Maximilian von Weichs", None)])
_f("uranus42", "romania", "army", "3rd Army", "Heeresgruppe B", [(None, None, S4, "Petre Dumitrescu", None)])
_f("uranus42", "romania", "division", "1st Armoured Division 'Romania Mare'", "3rd Army",
   [(None, None, B1, "Gheorghe Radu", None)])
_f("uranus42", "romania", "division", "15th Infantry Division", "3rd Army",
   [(None, (1942, 11, 22), B1, "Ion Sion", "killed in the encirclement")])

_f("guadalcanal42", "usa", "theatre", "Pacific Ocean Areas", None, [(None, None, "Adm.", "Chester Nimitz", None)])
_f("guadalcanal42", "usa", "army", "South Pacific Area", "Pacific Ocean Areas",
   [(None, (1942, 10, 18), "V.Adm.", "Robert Ghormley", "relieved"),
    ((1942, 10, 18), None, "V.Adm.", "William Halsey", None)])
_f("guadalcanal42", "usa", "division", "1st Marine Division", "South Pacific Area", [(None, None, S2, "Alexander Vandegrift", None)])
_f("guadalcanal42", "usa", "battalion", "1st Marine Raider Battalion", "1st Marine Division", [(None, None, COL, "Merritt Edson", None)])
_f("guadalcanal42", "usa", "regiment", "5th Marines", "1st Marine Division",
   [(None, (1942, 9, 21), COL, "LeRoy Hunt", "replaced"), ((1942, 9, 21), None, COL, "Merritt Edson", None)])
_f("guadalcanal42", "japan", "army", "17th Army", None, [(None, None, S2, "Harukichi Hyakutake", None)])
_f("guadalcanal42", "japan", "brigade", "Kawaguchi Detachment", "17th Army", [(None, None, B1, "Kiyotake Kawaguchi", None)])
_f("guadalcanal42", "japan", "regiment", "124th Infantry Regiment", "Kawaguchi Detachment", [(None, None, COL, "Akinosuke Oka", None)])
_f("guadalcanal42", "japan", "regiment", "Ichiki Detachment", "17th Army",
   [(None, (1942, 8, 21), COL, "Kiyonao Ichiki", "killed at the Tenaru")])

# ------------------------------------------------------------------ 1943
_f("tunisia43", "usa", "theatre", "Allied Force Headquarters", None, [(None, None, S4, "Dwight D. Eisenhower", None)])
_f("tunisia43", "usa", "army group", "18th Army Group", "Allied Force Headquarters", [((1943, 2, 20), None, S4, "Harold Alexander", None)])
_f("tunisia43", "usa", "corps", "II Corps", "18th Army Group",
   [(None, (1943, 3, 6), S2, "Lloyd Fredendall", "relieved after Kasserine"), ((1943, 3, 6), None, S3, "George S. Patton", None)])
_f("tunisia43", "usa", "division", "1st Armored Division", "II Corps",
   [(None, (1943, 4, 5), S2, "Orlando Ward", "relieved"), ((1943, 4, 5), None, S2, "Ernest Harmon", None)])
_f("tunisia43", "usa", "regiment", "26th Infantry Regiment", "II Corps", [(None, None, COL, "Alexander Stark", None)])
_f("tunisia43", "usa", "regiment", "19th Engineers", "II Corps", [(None, None, COL, "Anderson Moore", None)])
_f("tunisia43", ("germany", "italy"), "army group", "Heeresgruppe Afrika", None,
   [((1943, 2, 23), (1943, 3, 9), S5, "Erwin Rommel", "flown out of Africa"),
    ((1943, 3, 9), (1943, 5, 12), S4, "Hans-Jürgen von Arnim", "captured")])
_f("tunisia43", "germany", "army", "5. Panzerarmee", "Heeresgruppe Afrika",
   [(None, (1943, 3, 9), S4, "Hans-Jürgen von Arnim", "given the army group"), ((1943, 3, 9), None, S3, "Gustav von Vaerst", None)])
_f("tunisia43", "germany", "division", "10. Panzer-Division", "5. Panzerarmee",
   [(None, (1943, 2, 1), S2, "Wolfgang Fischer", "killed by a mine"), ((1943, 2, 1), None, S2, "Friedrich von Broich", None)])
_f("tunisia43", "germany", "division", "21. Panzer-Division", "Heeresgruppe Afrika", [(None, None, S2, "Hans-Georg Hildebrandt", None)])
_f("tunisia43", "italy", "division", "Divisione Centauro", "Heeresgruppe Afrika", [(None, None, B1, "Giorgio Calvi di Bergolo", None)])

_f("don43", "hungary", "army group", "Heeresgruppe B", None, [(None, None, S4, "Maximilian von Weichs", None)])
_f("don43", "hungary", "army", "2nd Hungarian Army", "Heeresgruppe B", [(None, None, S4, "Gusztáv Jány", None)])
_f("don43", "ussr", "front", "Voronezh Front", None, [(None, None, S3, "Filipp Golikov", None)])
_f("don43", "ussr", "army", "40th Army", "Voronezh Front", [(None, None, S2, "Kirill Moskalenko", None)])
_f("don43", "ussr", "army", "3rd Tank Army", "Voronezh Front", [(None, None, S2, "Pavel Rybalko", None)])

_f("kursk43", "germany", "army group", "Heeresgruppe Mitte", None, [(None, None, S5, "Günther von Kluge", None)])
_f("kursk43", "germany", "army", "9. Armee", "Heeresgruppe Mitte", [(None, None, S4, "Walter Model", None)])
_f("kursk43", "germany", "corps", "XLVII. Panzerkorps", "9. Armee", [(None, None, S3, "Joachim Lemelsen", None)])
_f("kursk43", "germany", "corps", "XLI. Panzerkorps", "9. Armee", [(None, None, S3, "Josef Harpe", None)])
_f("kursk43", "germany", "corps", "XLVI. Panzerkorps", "9. Armee", [(None, None, S3, "Hans Zorn", None)])
_f("kursk43", "germany", "corps", "XXIII. Armeekorps", "9. Armee", [(None, None, S3, "Johannes Frießner", None)])
_f("kursk43", "germany", "corps", "XX. Armeekorps", "9. Armee", [(None, None, S3, "Rudolf von Roman", None)])
_f("kursk43", "germany", "division", "292. Infanterie-Division", "XLI. Panzerkorps", [(None, None, S2, "Wolfgang von Kluge", None)])
_f("kursk43", "germany", "battalion", "schwere Panzerjäger-Abteilung 654", "9. Armee", [(None, None, MAJ, "Karl-Heinz Noak", None)])
_f("kursk43", "germany", "army group", "Heeresgruppe Süd", None, [(None, None, S5, "Erich von Manstein", None)])
_f("kursk43", "germany", "army", "4. Panzerarmee", "Heeresgruppe Süd", [(None, None, S4, "Hermann Hoth", None)])
_f("kursk43", "germany", "corps", "II. SS-Panzerkorps", "4. Panzerarmee", [(None, None, S4, "Paul Hausser", None)])
_f("kursk43", "germany", "division", "SS-Panzergrenadier-Division Totenkopf", "II. SS-Panzerkorps",
   [(None, None, B1, "Hermann Priess", None)])
_f("kursk43", "ussr", "front", "Central Front", None, [(None, None, S4, "Konstantin Rokossovsky", None)])
_f("kursk43", "ussr", "front", "Voronezh Front", None, [(None, None, S4, "Nikolai Vatutin", None)])
_f("kursk43", "ussr", "army", "13th Army", "Central Front", [(None, None, S2, "Nikolai Pukhov", None)])
_f("kursk43", "ussr", "army", "2nd Tank Army", "Central Front", [(None, None, S2, "Aleksei Rodin", None)])
_f("kursk43", "ussr", "army", "5th Guards Tank Army", "Voronezh Front", [(None, None, S2, "Pavel Rotmistrov", None)])
_f("kursk43", "ussr", "division", "307th Rifle Division", "13th Army", [(None, None, B1, "Mikhail Yenshin", None)])

_f("sicily43", "usa", "theatre", "Allied Force Headquarters", None, [(None, None, S4, "Dwight D. Eisenhower", None)])
_f("sicily43", "usa", "army group", "15th Army Group", "Allied Force Headquarters", [(None, None, S4, "Harold Alexander", None)])
_f("sicily43", "usa", "army", "Seventh Army", "15th Army Group", [(None, None, S3, "George S. Patton", None)])
_f("sicily43", "usa", "corps", "II Corps", "Seventh Army", [(None, None, S3, "Omar Bradley", None)])
_f("sicily43", "usa", "division", "1st Infantry Division", "II Corps",
   [(None, (1943, 8, 7), S2, "Terry de la Mesa Allen", "relieved"), ((1943, 8, 7), None, S2, "Clarence Huebner", None)])
_f("sicily43", "usa", "division", "82nd Airborne Division", "Seventh Army", [(None, None, S2, "Matthew Ridgway", None)])
_f("sicily43", "usa", "division", "45th Infantry Division", "II Corps", [(None, None, S2, "Troy Middleton", None)])
_f("sicily43", ("italy", "germany"), "theatre", "Oberbefehlshaber Süd", None, [(None, None, S5, "Albert Kesselring", None)])
_f("sicily43", "italy", "army", "6ª Armata", "Oberbefehlshaber Süd", [(None, None, S4, "Alfredo Guzzoni", None)])
_f("sicily43", "italy", "division", "Divisione Livorno", "6ª Armata", [(None, None, S2, "Domenico Chirieleison", None)])
_f("sicily43", "germany", "corps", "XIV. Panzerkorps", "6ª Armata", [((1943, 7, 17), None, S3, "Hans-Valentin Hube", None)])
_f("sicily43", "germany", "division", "Fallschirm-Panzer-Division Hermann Göring", "6ª Armata", [(None, None, S2, "Paul Conrath", None)])

# ------------------------------------------------------------------ 1944
_f("cassino44", ("uk", "poland", "newzealand", "india"), "army group", "Allied Armies in Italy", None,
   [(None, None, S4, "Harold Alexander", None)])
_f("cassino44", ("uk", "poland", "newzealand", "india"), "army", "Eighth Army", "Allied Armies in Italy",
   [(None, None, S3, "Oliver Leese", None)])
_f("cassino44", "poland", "corps", "II Polish Corps", "Eighth Army", [(None, None, S2, "Władysław Anders", None)])
_f("cassino44", "poland", "division", "3rd Carpathian Rifle Division", "II Polish Corps", [(None, None, S2, "Bolesław Duch", None)])
_f("cassino44", "poland", "division", "5th Kresowa Infantry Division", "II Polish Corps", [(None, None, S2, "Nikodem Sulik", None)])
_f("cassino44", "newzealand", "division", "2nd New Zealand Division", "Eighth Army", [(None, None, S3, "Bernard Freyberg", None)])
_f("cassino44", "india", "division", "4th Indian Division", "Eighth Army", [(None, None, S2, "Arthur Holworthy", None)])
_f("cassino44", "germany", "army group", "Heeresgruppe C", None, [(None, None, S5, "Albert Kesselring", None)])
_f("cassino44", "germany", "army", "10. Armee", "Heeresgruppe C", [(None, None, S4, "Heinrich von Vietinghoff", None)])
_f("cassino44", "germany", "corps", "LI. Gebirgskorps", "10. Armee", [(None, None, S3, "Valentin Feuerstein", None)])
_f("cassino44", "germany", "division", "1. Fallschirmjäger-Division", "LI. Gebirgskorps", [(None, None, S2, "Richard Heidrich", None)])

NORMANDY = ("normandy_airborne44", "omaha44", "bocage44")
for _t in NORMANDY:
    _f(_t, ("usa", "uk", "canada"), "theatre", "SHAEF", None, [(None, None, S4, "Dwight D. Eisenhower", None)])
    _f(_t, ("usa", "uk", "canada"), "army group", "21st Army Group", "SHAEF",
       [(None, (1944, 9, 1), S4, "Bernard Montgomery", "promoted Field Marshal"),
        ((1944, 9, 1), None, S5, "Bernard Montgomery", None)])
    _f(_t, "usa", "army group", "12th Army Group", "SHAEF", [((1944, 8, 1), None, S3, "Omar Bradley", None)])
    # the Americans were under Montgomery's 21st Army Group until 12th Army Group took over on 1 August
    _f(_t, "usa", "army", "First Army", [(None, (1944, 8, 1), "21st Army Group"), ((1944, 8, 1), None, "12th Army Group")],
       [(None, (1944, 8, 1), S3, "Omar Bradley", "given 12th Army Group"), ((1944, 8, 1), None, S3, "Courtney Hodges", None)])
    _f(_t, "usa", "corps", "V Corps", "First Army", [(None, None, S2, "Leonard Gerow", None)])
    _f(_t, "usa", "corps", "VII Corps", "First Army", [(None, None, S2, "J. Lawton Collins", None)])
    _f(_t, "usa", "corps", "XIX Corps", "First Army", [(None, None, S2, "Charles Corlett", None)])
    _f(_t, "usa", "division", "82nd Airborne Division", "VII Corps",
       [(None, (1944, 8, 27), S2, "Matthew Ridgway", "given a corps"), ((1944, 8, 27), None, B1, "James Gavin", None)])
    _f(_t, "usa", "division", "101st Airborne Division", "VII Corps", [(None, None, S2, "Maxwell Taylor", None)])
    _f(_t, "usa", "division", "29th Infantry Division", "V Corps" if _t != "bocage44" else "XIX Corps",
       [(None, None, S2, "Charles Gerhardt", None)])
    _f(_t, "usa", "division", "1st Infantry Division", "V Corps", [(None, None, S2, "Clarence Huebner", None)])
    _f(_t, "usa", "battalion", "2nd Ranger Battalion", "V Corps", [(None, None, LTC, "James Earl Rudder", None)])
    _f(_t, "usa", "division", "2nd Armored Division", "VII Corps", [(None, None, S2, "Edward Brooks", None)])
    _f(_t, "usa", "division", "30th Infantry Division", "XIX Corps", [(None, None, S2, "Leland Hobbs", None)])
    _f(_t, "uk", "army", "Second Army", "21st Army Group", [(None, None, S3, "Miles Dempsey", None)])
    _f(_t, "uk", "corps", "XXX Corps", "Second Army",
       [(None, (1944, 8, 2), S3, "Gerard Bucknall", "relieved"), ((1944, 8, 4), None, S3, "Brian Horrocks", None)])
    _f(_t, "uk", "corps", "VIII Corps", "Second Army", [(None, None, S3, "Richard O'Connor", None)])
    _f(_t, "uk", "division", "43rd (Wessex) Division", "XXX Corps", [(None, None, S2, "Ivor Thomas", None)])
    _f(_t, "uk", "division", "7th Armoured Division", "XXX Corps",
       [(None, (1944, 8, 4), S2, "George Erskine", "relieved"), ((1944, 8, 4), None, S2, "Gerald Verney", None)])
    _f(_t, "uk", "division", "15th (Scottish) Division", "VIII Corps", [(None, None, S2, "Gordon MacMillan", None)])
    _f(_t, "canada", "army", "First Canadian Army", "21st Army Group", [((1944, 7, 23), None, S3, "Harry Crerar", None)])
    _f(_t, "canada", "corps", "II Canadian Corps", "First Canadian Army", [(None, None, S3, "Guy Simonds", None)])
    _f(_t, "canada", "division", "3rd Canadian Infantry Division", "II Canadian Corps",
       [(None, (1944, 8, 8), S2, "Rod Keller", "badly wounded when American bombers hit his HQ"),
        ((1944, 8, 18), None, S2, "Daniel Spry", None)])
    _f(_t, "germany", "theatre", "Oberbefehlshaber West", None,
       [(None, (1944, 7, 2), S5, "Gerd von Rundstedt", "relieved ('Make peace, you fools!')"),
        ((1944, 7, 3), (1944, 8, 17), S5, "Günther von Kluge", "relieved - poisoned himself on the way home"),
        ((1944, 8, 17), (1944, 9, 5), S5, "Walter Model", "superseded"),
        ((1944, 9, 5), None, S5, "Gerd von Rundstedt", None)])
    _f(_t, "germany", "army group", "Heeresgruppe B", "Oberbefehlshaber West",
       [(None, (1944, 7, 17), S5, "Erwin Rommel", "badly wounded when a fighter strafed his car"),
        ((1944, 7, 17), (1944, 8, 17), S5, "Günther von Kluge", "relieved"),
        ((1944, 8, 17), None, S5, "Walter Model", None)])
    _f(_t, "germany", "army", "7. Armee", "Heeresgruppe B",
       [(None, (1944, 6, 28), S4, "Friedrich Dollmann", "died - officially a heart attack"),
        ((1944, 6, 29), (1944, 8, 20), S4, "Paul Hausser", "badly wounded breaking out of Falaise"),
        ((1944, 8, 21), (1944, 8, 31), S3, "Heinrich Eberbach", "captured"),
        ((1944, 9, 3), None, S3, "Erich Brandenberger", None)])
    _f(_t, "germany", "corps", "LXXXIV. Armeekorps", "7. Armee",
       [(None, (1944, 6, 12), S3, "Erich Marcks", "killed by a fighter-bomber"),
        ((1944, 6, 18), (1944, 7, 28), S3, "Dietrich von Choltitz", "sent to Paris"),
        ((1944, 7, 28), (1944, 8, 20), S2, "Otto Elfeldt", "captured at Falaise")])
    _f(_t, "germany", "corps", "II. Fallschirmkorps", "7. Armee", [(None, None, S3, "Eugen Meindl", None)])
    _f(_t, "germany", "corps", "I. SS-Panzerkorps", "Heeresgruppe B", [(None, None, S4, "Sepp Dietrich", None)])
    _f(_t, "germany", "division", "91. Luftlande-Division", "LXXXIV. Armeekorps",
       [(None, (1944, 6, 6), S2, "Wilhelm Falley", "killed by American paratroopers driving back to his HQ"),
        ((1944, 6, 10), None, COL, "Eugen König", None)])
    _f(_t, "germany", "division", "709. Infanterie-Division", "LXXXIV. Armeekorps",
       [(None, (1944, 6, 26), S2, "Karl-Wilhelm von Schlieben", "captured at Cherbourg")])
    _f(_t, "germany", "regiment", "Fallschirmjäger-Regiment 6", "LXXXIV. Armeekorps",
       [(None, None, LTC, "Friedrich August von der Heydte", None)])
    _f(_t, "germany", "division", "352. Infanterie-Division", "LXXXIV. Armeekorps",
       [(None, (1944, 8, 2), S2, "Dietrich Kraiss", "mortally wounded near Saint-Lô")])
    _f(_t, "germany", "division", "716. Infanterie-Division", "LXXXIV. Armeekorps", [(None, None, S2, "Wilhelm Richter", None)])
    _f(_t, "germany", "division", "Panzer-Lehr-Division", "LXXXIV. Armeekorps", [(None, None, S2, "Fritz Bayerlein", None)])
    _f(_t, "germany", "division", "12. SS-Panzer-Division Hitlerjugend", "I. SS-Panzerkorps",
       [(None, (1944, 6, 14), B1, "Fritz Witt", "killed by naval gunfire at his HQ"),
        ((1944, 6, 14), (1944, 9, 6), COL, "Kurt Meyer", "captured"), ((1944, 9, 6), None, LTC, "Hubert Meyer", None)])
    _f(_t, "germany", "division", "3. Fallschirmjäger-Division", "II. Fallschirmkorps",
       [(None, (1944, 8, 20), S2, "Richard Schimpf", "wounded at Falaise")])
    _f(_t, "germany", "division", "2. SS-Panzer-Division Das Reich", "LXXXIV. Armeekorps",
       [(None, (1944, 7, 24), B1, "Heinz Lammerding", "wounded"),
        ((1944, 7, 24), (1944, 7, 28), LTC, "Christian Tychsen", "killed by an American patrol"),
        ((1944, 7, 28), None, COL, "Otto Baum", None)])

_f("arnhem44", ("uk", "poland"), "army group", "21st Army Group", None, [(None, None, S5, "Bernard Montgomery", None)])
_f("arnhem44", ("uk", "poland"), "army", "First Allied Airborne Army", "21st Army Group", [(None, None, S3, "Lewis Brereton", None)])
_f("arnhem44", ("uk", "poland"), "corps", "I Airborne Corps", "First Allied Airborne Army", [(None, None, S3, "Frederick Browning", None)])
_f("arnhem44", "uk", "division", "1st Airborne Division", "I Airborne Corps", [(None, None, S2, "Roy Urquhart", None)])
_f("arnhem44", "uk", "battalion", "2nd Parachute Battalion", "1st Airborne Division",
   [(None, (1944, 9, 20), LTC, "John Frost", "wounded and captured at the bridge")])
_f("arnhem44", "uk", "brigade", "1st Airlanding Brigade", "1st Airborne Division", [(None, None, B1, "Philip Hicks", None)])
_f("arnhem44", "poland", "brigade", "1st Independent Parachute Brigade", "I Airborne Corps",
   [(None, None, S2, "Stanisław Sosabowski", None)])
_f("arnhem44", "germany", "army group", "Heeresgruppe B", None, [(None, None, S5, "Walter Model", None)])
_f("arnhem44", "germany", "corps", "II. SS-Panzerkorps", "Heeresgruppe B", [(None, None, S3, "Wilhelm Bittrich", None)])
_f("arnhem44", "germany", "division", "9. SS-Panzer-Division Hohenstaufen", "II. SS-Panzerkorps", [(None, None, LTC, "Walter Harzer", None)])
_f("arnhem44", "germany", "division", "10. SS-Panzer-Division Frundsberg", "II. SS-Panzerkorps", [(None, None, B1, "Heinz Harmel", None)])
_f("arnhem44", "germany", "battalion", "Kampfgruppe Spindler", "9. SS-Panzer-Division Hohenstaufen", [(None, None, MAJ, "Ludwig Spindler", None)])

_f("hurtgen44", "usa", "army group", "12th Army Group", None, [(None, None, S3, "Omar Bradley", None)])
_f("hurtgen44", "usa", "army", "First Army", "12th Army Group", [(None, None, S3, "Courtney Hodges", None)])
_f("hurtgen44", "usa", "corps", "V Corps", "First Army", [(None, None, S2, "Leonard Gerow", None)])
_f("hurtgen44", "usa", "corps", "VII Corps", "First Army", [(None, None, S2, "J. Lawton Collins", None)])
_f("hurtgen44", "usa", "division", "28th Infantry Division", "V Corps", [(None, None, S2, "Norman Cota", None)])
_f("hurtgen44", "usa", "division", "4th Infantry Division", "VII Corps", [(None, None, S2, "Raymond Barton", None)])
_f("hurtgen44", "usa", "division", "9th Infantry Division", "VII Corps", [(None, None, S2, "Louis Craig", None)])
_f("hurtgen44", "germany", "army group", "Heeresgruppe B", None, [(None, None, S5, "Walter Model", None)])
_f("hurtgen44", "germany", "army", "7. Armee", "Heeresgruppe B", [(None, None, S3, "Erich Brandenberger", None)])
_f("hurtgen44", "germany", "corps", "LXXIV. Armeekorps", "7. Armee", [(None, None, S3, "Erich Straube", None)])
_f("hurtgen44", "germany", "division", "275. Infanterie-Division", "LXXIV. Armeekorps", [(None, None, S2, "Hans Schmidt", None)])
_f("hurtgen44", "germany", "division", "89. Infanterie-Division", "LXXIV. Armeekorps", [(None, None, B1, "Walter Bruns", None)])
_f("hurtgen44", "germany", "division", "116. Panzer-Division", "LXXIV. Armeekorps", [(None, None, S2, "Siegfried von Waldenburg", None)])

_f("bastogne44", "usa", "army", "Third Army", None, [(None, None, S3, "George S. Patton", None)])
_f("bastogne44", "usa", "corps", "VIII Corps", "Third Army", [(None, None, S2, "Troy Middleton", None)])
_f("bastogne44", "usa", "division", "101st Airborne Division", "VIII Corps",
   [(None, (1944, 12, 17), S2, "Maxwell Taylor", "away in Washington"),
    ((1944, 12, 17), (1944, 12, 27), B1, "Anthony McAuliffe", "Taylor returned ('Nuts!')"),
    ((1944, 12, 27), None, S2, "Maxwell Taylor", None)])
_f("bastogne44", "usa", "division", "10th Armored Division (Team SNAFU)", "VIII Corps", [(None, None, S2, "William Morris", None)])
_f("bastogne44", "germany", "theatre", "Oberbefehlshaber West", None, [(None, None, S5, "Gerd von Rundstedt", None)])
_f("bastogne44", "germany", "army group", "Heeresgruppe B", "Oberbefehlshaber West", [(None, None, S5, "Walter Model", None)])
_f("bastogne44", "germany", "army", "5. Panzerarmee", "Heeresgruppe B", [(None, None, S3, "Hasso von Manteuffel", None)])
_f("bastogne44", "germany", "corps", "XLVII. Panzerkorps", "5. Panzerarmee", [(None, None, S3, "Heinrich von Lüttwitz", None)])
_f("bastogne44", "germany", "division", "26. Volksgrenadier-Division", "XLVII. Panzerkorps", [(None, None, COL, "Heinz Kokott", None)])
_f("bastogne44", "germany", "division", "Panzer-Lehr-Division", "XLVII. Panzerkorps", [(None, None, S2, "Fritz Bayerlein", None)])
_f("bastogne44", "germany", "division", "15. Panzergrenadier-Division", "XLVII. Panzerkorps", [(None, None, COL, "Wolfgang Maucke", None)])

_f("kohima44", ("uk", "india"), "theatre", "South East Asia Command", None, [(None, None, "Adm.", "Lord Louis Mountbatten", None)])
_f("kohima44", ("uk", "india"), "army", "Fourteenth Army", "South East Asia Command", [(None, None, S3, "William Slim", None)])
_f("kohima44", ("uk", "india"), "corps", "XXXIII Corps", "Fourteenth Army", [(None, None, S3, "Montagu Stopford", None)])
_f("kohima44", "uk", "division", "2nd Division", "XXXIII Corps",
   [(None, (1944, 7, 5), S2, "John Grover", "relieved"), ((1944, 7, 5), None, S2, "Cameron Nicholson", None)])
_f("kohima44", ("uk", "india"), "brigade", "161st Indian Brigade", "XXXIII Corps", [(None, None, B1, "Dermot Warren", None)])
_f("kohima44", "uk", "battalion", "4th Bn Royal West Kent Regiment", "161st Indian Brigade", [(None, None, LTC, "John Laverty", None)])
_f("kohima44", "india", "battalion", "Assam Regiment", "161st Indian Brigade", [(None, None, LTC, "William Brown", None)])
_f("kohima44", "japan", "theatre", "Burma Area Army", None, [(None, None, S2, "Masakazu Kawabe", None)])
_f("kohima44", "japan", "army", "15th Army", "Burma Area Army", [(None, None, S2, "Renya Mutaguchi", None)])
_f("kohima44", "japan", "division", "31st Division", "15th Army",
   [(None, (1944, 7, 7), S2, "Kōtoku Satō", "relieved for retreating without orders")])
_f("kohima44", "japan", "regiment", "58th Infantry Regiment", "31st Division", [(None, None, COL, "Utata Fukunaga", None)])

_f("karelia44", "finland", "army", "Kannaksen Armeija", None, [((1944, 6, 15), None, S2, "Karl Lennart Oesch", None)])
_f("karelia44", "finland", "corps", "IV Armeijakunta", "Kannaksen Armeija", [(None, None, S2, "Taavetti Laatikainen", None)])
_f("karelia44", "finland", "division", "Panssaridivisioona", "IV Armeijakunta", [(None, None, B1, "Ruben Lagus", None)])
_f("karelia44", "finland", "division", "6. Divisioona", "IV Armeijakunta", [(None, None, B1, "Einar Vihma", None)])
_f("karelia44", "finland", "division", "18. Divisioona", "IV Armeijakunta", [(None, None, COL, "Paavo Paalu", None)])
_f("karelia44", "ussr", "front", "Leningrad Front", None, [(None, None, S5, "Leonid Govorov", None)])
_f("karelia44", "ussr", "army", "21st Army", "Leningrad Front", [(None, None, S2, "Dmitri Gusev", None)])
_f("karelia44", "ussr", "corps", "30th Guards Rifle Corps", "21st Army", [(None, None, S2, "Nikolai Simoniak", None)])

# ------------------------------------------------------------------ 1945
_f("iwojima45", "usa", "theatre", "Pacific Ocean Areas", None, [(None, None, "Fleet Adm.", "Chester Nimitz", None)])
_f("iwojima45", "usa", "army", "Fifth Fleet", "Pacific Ocean Areas", [(None, None, "Adm.", "Raymond Spruance", None)])
_f("iwojima45", "usa", "army", "Expeditionary Troops", "Fifth Fleet", [(None, None, S3, "Holland M. Smith", None)])
_f("iwojima45", "usa", "corps", "V Amphibious Corps", "Expeditionary Troops", [(None, None, S2, "Harry Schmidt", None)])
_f("iwojima45", "usa", "division", "4th Marine Division", "V Amphibious Corps", [(None, None, S2, "Clifton Cates", None)])
_f("iwojima45", "usa", "division", "5th Marine Division", "V Amphibious Corps", [(None, None, S2, "Keller Rockey", None)])
_f("iwojima45", "usa", "division", "3rd Marine Division", "V Amphibious Corps", [(None, None, S2, "Graves Erskine", None)])
_f("iwojima45", "japan", "division", "109th Division", None,
   [(None, (1945, 3, 26), S2, "Tadamichi Kuribayashi", "killed - probably leading the last attack")])
_f("iwojima45", "japan", "regiment", "145th Infantry Regiment", "109th Division", [(None, None, COL, "Masuo Ikeda", None)])

_f("berlin45", "ussr", "front", "1st Belorussian Front", None, [(None, None, S5, "Georgy Zhukov", None)])
_f("berlin45", "ussr", "army", "8th Guards Army", "1st Belorussian Front", [(None, None, S3, "Vasily Chuikov", None)])
_f("berlin45", "ussr", "army", "3rd Shock Army", "1st Belorussian Front", [(None, None, S3, "Vasily Kuznetsov", None)])
_f("berlin45", "ussr", "corps", "79th Rifle Corps", "3rd Shock Army", [(None, None, B1, "Semyon Perevertkin", None)])
_f("berlin45", "ussr", "division", "150th Rifle Division", "79th Rifle Corps", [(None, None, B1, "Vasily Shatilov", None)])
_f("berlin45", "ussr", "division", "171st Rifle Division", "79th Rifle Corps", [(None, None, COL, "Aleksei Negoda", None)])
_f("berlin45", "poland", "army", "1st Polish Army", "1st Belorussian Front", [(None, None, S2, "Stanisław Popławski", None)])
_f("berlin45", "poland", "division", "1st Tadeusz Kościuszko Infantry Division", "1st Polish Army",
   [(None, None, B1, "Wojciech Bewziuk", None)])
_f("berlin45", "germany", "army group", "Heeresgruppe Weichsel", None,
   [(None, (1945, 4, 29), S4, "Gotthard Heinrici", "relieved for refusing to hold at all costs"),
    ((1945, 4, 29), None, S4, "Kurt Student", None)])
_f("berlin45", "germany", "corps", "Verteidigungsbereich Berlin", "Heeresgruppe Weichsel",
   [((1945, 4, 23), (1945, 5, 2), S3, "Helmuth Weidling", "surrendered the city")])
_f("berlin45", "germany", "division", "SS-Division Nordland", "Verteidigungsbereich Berlin",
   [(None, (1945, 4, 25), S2, "Joachim Ziegler", "relieved"), ((1945, 4, 25), None, S2, "Gustav Krukenberg", None)])
_f("berlin45", "germany", "division", "Division Müncheberg", "Verteidigungsbereich Berlin", [(None, None, S2, "Werner Mummert", None)])
_f("berlin45", "germany", "division", "Hitlerjugend", "Verteidigungsbereich Berlin", [(None, None, "Reichsjugendführer", "Artur Axmann", None)])

_f("okinawa45", "usa", "army", "Fifth Fleet", None, [(None, None, "Adm.", "Raymond Spruance", None)])
_f("okinawa45", "usa", "army", "Tenth Army", "Fifth Fleet",
   [(None, (1945, 6, 18), S3, "Simon Bolivar Buckner Jr.", "killed by an artillery shell on the front line"),
    ((1945, 6, 18), (1945, 6, 23), S3, "Roy Geiger", "relieved by Stilwell"),
    ((1945, 6, 23), None, S4, "Joseph Stilwell", None)])
_f("okinawa45", "usa", "corps", "III Amphibious Corps", "Tenth Army", [(None, None, S3, "Roy Geiger", None)])
_f("okinawa45", "usa", "corps", "XXIV Corps", "Tenth Army", [(None, None, S3, "John Hodge", None)])
_f("okinawa45", "usa", "division", "6th Marine Division", "III Amphibious Corps", [(None, None, S2, "Lemuel Shepherd", None)])
_f("okinawa45", "usa", "division", "1st Marine Division", "III Amphibious Corps", [(None, None, S2, "Pedro del Valle", None)])
_f("okinawa45", "usa", "division", "96th Infantry Division", "XXIV Corps", [(None, None, S2, "James Bradley", None)])
_f("okinawa45", "japan", "army", "32nd Army", None,
   [(None, (1945, 6, 22), S2, "Mitsuru Ushijima", "ritual suicide as the army died")])
_f("okinawa45", "japan", "division", "62nd Division", "32nd Army", [(None, None, S2, "Takeo Fujioka", None)])
_f("okinawa45", "japan", "division", "24th Division", "32nd Army", [(None, None, S2, "Tatsumi Amamiya", None)])


# ------------------------------------------------------------------ the notable divisions' commanders (data/notable.py)
_f("tunisia43", "usa", "division", "1st Infantry Division", "II Corps", [(None, None, S2, "Terry Allen", None)])
_f("tunisia43", "usa", "division", "9th Infantry Division", "II Corps", [(None, None, S2, "Manton Eddy", None)])
_f("sicily43", "usa", "division", "2nd Armored Division", "Seventh Army", [(None, None, S2, "Hugh Gaffey", None)])
_f("sicily43", ("uk", "canada"), "army", "Eighth Army", "15th Army Group", [(None, None, S4, "Bernard Montgomery", None)])
_f("sicily43", ("uk", "canada"), "corps", "XXX Corps", "Eighth Army", [(None, None, S3, "Oliver Leese", None)])
_f("sicily43", "uk", "division", "51st Highland Division", "XXX Corps", [(None, None, S2, "Douglas Wimberley", None)])
_f("sicily43", "canada", "division", "1st Canadian Infantry Division", "XXX Corps",
   [(None, None, S2, "Guy Simonds", None)])
_f("bastogne44", "usa", "division", "10th Armored Division", "VIII Corps", [(None, None, S2, "William Morris", None)])
_f("arnhem44", "uk", "corps", "XXX Corps", "21st Army Group", [(None, None, S3, "Brian Horrocks", None)])
_f("arnhem44", "uk", "division", "43rd (Wessex) Division", "XXX Corps", [(None, None, S2, "Ivor Thomas", None)])
_f("alamein42", "australia", "division", "9th Australian Division", "XXX Corps",
   [(None, None, S3, "Leslie Morshead", None)])
_f("alamein42", "newzealand", "division", "2nd New Zealand Division", "XXX Corps",
   [(None, None, S3, "Bernard Freyberg", None)])
_f("alamein42", "india", "division", "4th Indian Division", "Eighth Army", [(None, None, S2, "Francis Tuker", None)])
_f("kursk43", "germany", "corps", "XLVIII. Panzerkorps", "4. Panzerarmee",
   [(None, None, S3, "Otto von Knobelsdorff", None)])
_f("kursk43", "germany", "division", "Panzergrenadier-Division Großdeutschland", "XLVIII. Panzerkorps",
   [(None, None, S2, "Walter Hörnlein", None)])
_f("guadalcanal42", "japan", "division", "2nd Division (Sendai)", "17th Army", [(None, None, S2, "Masao Maruyama", None)])
