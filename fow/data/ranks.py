"""Full rank ladders, private to five-star, on a common 19-grade scale.

Grade:  0 private  1 private 1st class  2 corporal  3 sergeant  4 staff sergeant
        5 platoon sergeant  6 first/master sergeant  7 sergeant major / warrant
        8 2nd lieutenant  9 lieutenant  10 captain  11 major  12 lieutenant colonel
        13 colonel  14 brigadier (1*)  15 major general (2*)  16 lieutenant general (3*)
        17 general (4*)  18 general of the army / field marshal (5*)
"""
from __future__ import annotations

PRIVATE, PFC, CORPORAL, SERGEANT, STAFF_SGT, PLATOON_SGT, FIRST_SGT, SGT_MAJOR = range(8)
LT2, LT, CAPTAIN, MAJOR, LT_COL, COLONEL, BRIGADIER, MAJ_GEN, LT_GEN, GENERAL, MARSHAL = range(8, 19)

STARS = {14: "*", 15: "**", 16: "***", 17: "****", 18: "*****"}

# what each grade commands
COMMAND_LEVEL = {
    2: "fire team", 3: "squad", 4: "squad", 5: "platoon (second in command)", 6: "company (senior NCO)",
    7: "battalion (senior NCO)", 8: "platoon", 9: "platoon", 10: "company", 11: "battalion (executive)",
    12: "battalion", 13: "regiment", 14: "brigade", 15: "division", 16: "corps", 17: "army", 18: "army group",
}

LADDERS = {
    "usa": [("Private", "Pvt."), ("Private First Class", "PFC"), ("Corporal", "Cpl."), ("Sergeant", "Sgt."),
            ("Staff Sergeant", "SSgt."), ("Technical Sergeant", "TSgt."), ("First Sergeant", "1st Sgt."),
            ("Master Sergeant", "MSgt."), ("Second Lieutenant", "2nd Lt."), ("First Lieutenant", "1st Lt."),
            ("Captain", "Capt."), ("Major", "Maj."), ("Lieutenant Colonel", "Lt. Col."), ("Colonel", "Col."),
            ("Brigadier General", "Brig. Gen."), ("Major General", "Maj. Gen."),
            ("Lieutenant General", "Lt. Gen."), ("General", "Gen."), ("General of the Army", "GA")],
    "uk": [("Private", "Pte."), ("Lance Corporal", "L/Cpl."), ("Corporal", "Cpl."), ("Sergeant", "Sgt."),
           ("Staff Sergeant", "S/Sgt."), ("Colour Sergeant", "C/Sgt."), ("Company Sergeant Major", "CSM"),
           ("Regimental Sergeant Major", "RSM"), ("Second Lieutenant", "2/Lt."), ("Lieutenant", "Lt."),
           ("Captain", "Capt."), ("Major", "Maj."), ("Lieutenant Colonel", "Lt. Col."), ("Colonel", "Col."),
           ("Brigadier", "Brig."), ("Major General", "Maj. Gen."), ("Lieutenant General", "Lt. Gen."),
           ("General", "Gen."), ("Field Marshal", "FM")],
    "ussr": [("Krasnoarmeyets", "Kr."), ("Yefreytor", "Yefr."), ("Mladshiy Serzhant", "Ml.Sgt."),
             ("Serzhant", "Sgt."), ("Starshiy Serzhant", "St.Sgt."), ("Starshina", "Stsh."),
             ("Starshina", "Stsh."), ("Starshina", "Stsh."), ("Mladshiy Leytenant", "Ml.Lt."),
             ("Leytenant", "Lt."), ("Kapitan", "Kpt."), ("Mayor", "Maj."), ("Podpolkovnik", "Ppolk."),
             ("Polkovnik", "Polk."), ("General-Mayor", "Gen-Maj."), ("General-Leytenant", "Gen-Lt."),
             ("General-Polkovnik", "Gen-Polk."), ("General Armii", "Gen.Arm."),
             ("Marshal Sovetskogo Soyuza", "Marshal")],
    "germany": [("Grenadier", "Gren."), ("Obergrenadier", "OGren."), ("Gefreiter", "Gefr."),
                ("Unteroffizier", "Uffz."), ("Unterfeldwebel", "Ufw."), ("Feldwebel", "Fw."),
                ("Oberfeldwebel", "Ofw."), ("Stabsfeldwebel", "Stfw."), ("Leutnant", "Lt."),
                ("Oberleutnant", "Oblt."), ("Hauptmann", "Hptm."), ("Major", "Maj."),
                ("Oberstleutnant", "Obstlt."), ("Oberst", "Oberst"), ("Generalmajor", "GenMaj."),
                ("Generalleutnant", "GenLt."), ("General der Infanterie", "Gen.d.Inf."),
                ("Generaloberst", "GenOberst"), ("Generalfeldmarschall", "GFM")],
    "italy": [("Soldato", "Sol."), ("Caporale", "Cap."), ("Caporal Maggiore", "C.le Magg."),
              ("Sergente", "Serg."), ("Sergente Maggiore", "Serg.Magg."), ("Maresciallo Ordinario", "Mar.Ord."),
              ("Maresciallo Capo", "Mar.Capo"), ("Maresciallo Maggiore", "Mar.Magg."), ("Sottotenente", "S.Ten."),
              ("Tenente", "Ten."), ("Capitano", "Cap.no"), ("Maggiore", "Magg."), ("Tenente Colonnello", "Ten.Col."),
              ("Colonnello", "Col."), ("Generale di Brigata", "Gen.B."), ("Generale di Divisione", "Gen.D."),
              ("Generale di Corpo d'Armata", "Gen.C.A."), ("Generale d'Armata", "Gen.A."),
              ("Maresciallo d'Italia", "Mar.d'It.")],
    "japan": [("Nitōhei", "Pvt.2"), ("Jōtōhei", "Sup.Pvt."), ("Heichō", "L/Cpl."), ("Gochō", "Cpl."),
              ("Gunsō", "Sgt."), ("Gunsō", "Sgt."), ("Sōchō", "Sgt.Maj."), ("Jun'i", "WO"), ("Shōi", "2Lt."),
              ("Chūi", "1Lt."), ("Taii", "Capt."), ("Shōsa", "Maj."), ("Chūsa", "Lt.Col."), ("Taisa", "Col."),
              ("Shōshō", "Maj.Gen."), ("Chūjō", "Lt.Gen."), ("Chūjō", "Lt.Gen."), ("Taishō", "Gen."),
              ("Gensui", "Gensui")],
    "france": [("Soldat", "Sdt."), ("Caporal", "Cpl."), ("Caporal-chef", "Cpl-C."), ("Sergent", "Sgt."),
               ("Sergent-chef", "Sgt-C."), ("Adjudant", "Adj."), ("Adjudant-chef", "Adj-C."),
               ("Adjudant-chef", "Adj-C."), ("Sous-lieutenant", "S/Lt."), ("Lieutenant", "Lt."),
               ("Capitaine", "Cne."), ("Commandant", "Cdt."), ("Lieutenant-colonel", "Lt-Col."),
               ("Colonel", "Col."), ("Général de brigade", "Gén.B."), ("Général de division", "Gén.D."),
               ("Général de corps d'armée", "Gén.C.A."), ("Général d'armée", "Gén.A."),
               ("Maréchal de France", "Mal.")],
    "poland": [("Szeregowiec", "Szer."), ("Starszy Szeregowiec", "St.Szer."), ("Kapral", "Kpr."),
               ("Plutonowy", "Plut."), ("Sierżant", "Sierż."), ("Starszy Sierżant", "St.Sierż."),
               ("Chorąży", "Chor."), ("Starszy Chorąży", "St.Chor."), ("Podporucznik", "Ppor."),
               ("Porucznik", "Por."), ("Kapitan", "Kpt."), ("Major", "Mjr"), ("Podpułkownik", "Ppłk"),
               ("Pułkownik", "Płk"), ("Generał Brygady", "Gen.Bryg."), ("Generał Dywizji", "Gen.Dyw."),
               ("Generał Broni", "Gen.Broni"), ("Generał Broni", "Gen.Broni"), ("Marszałek Polski", "Marsz.")],
    "china": [("Private", "Pvt."), ("Private First Class", "PFC"), ("Corporal", "Cpl."), ("Sergeant", "Sgt."),
              ("Sergeant First Class", "SFC"), ("Sergeant Major", "SgtMaj."), ("Sergeant Major", "SgtMaj."),
              ("Warrant Officer", "WO"), ("Second Lieutenant", "2Lt."), ("First Lieutenant", "1Lt."),
              ("Captain", "Capt."), ("Major", "Maj."), ("Lieutenant Colonel", "Lt.Col."), ("Colonel", "Col."),
              ("Major General", "Maj.Gen."), ("Lieutenant General", "Lt.Gen."), ("General (2nd class)", "Gen."),
              ("General (1st class)", "Gen."), ("Generalissimo", "Generalissimo")],
    "finland": [("Sotamies", "Stm."), ("Korpraali", "Kprl."), ("Alikersantti", "Alik."), ("Kersantti", "Kers."),
                ("Ylikersantti", "Ylik."), ("Vääpeli", "Vääp."), ("Sotilasmestari", "Sotm."),
                ("Sotilasmestari", "Sotm."), ("Vänrikki", "Vänr."), ("Luutnantti", "Ltn."),
                ("Kapteeni", "Kapt."), ("Majuri", "Maj."), ("Everstiluutnantti", "Evl."), ("Eversti", "Ev."),
                ("Kenraalimajuri", "Kenrm."), ("Kenraaliluutnantti", "Kenrl."), ("Jalkaväenkenraali", "Jv.kenr."),
                ("Sotamarsalkka", "Sotamarsalkka"), ("Suomen Marsalkka", "Marsalkka")],
    "hungary": [("Honvéd", "Hv."), ("Őrvezető", "Őrv."), ("Tizedes", "Tiz."), ("Szakaszvezető", "Szkv."),
                ("Őrmester", "Őrm."), ("Törzsőrmester", "Törzsőrm."), ("Főtörzsőrmester", "Ftörzsőrm."),
                ("Zászlós", "Zls."), ("Hadnagy", "Hdgy."), ("Főhadnagy", "Fhdgy."), ("Százados", "Szds."),
                ("Őrnagy", "Őrgy."), ("Alezredes", "Alez."), ("Ezredes", "Ezr."), ("Tábornok", "Tbk."),
                ("Altábornagy", "Altbgy."), ("Gyalogsági tábornok", "Gy.tbk."), ("Vezérezredes", "Vezds."),
                ("Tábornagy", "Tbgy.")],
    "romania": [("Soldat", "Sold."), ("Fruntaș", "Frt."), ("Caporal", "Cap."), ("Sergent", "Serg."),
                ("Plutonier", "Plt."), ("Plutonier-major", "Plt.Maj."), ("Plutonier-adjutant", "Plt.Adj."),
                ("Plutonier-adjutant", "Plt.Adj."), ("Sublocotenent", "Slt."), ("Locotenent", "Lt."),
                ("Căpitan", "Cpt."), ("Maior", "Mr."), ("Locotenent-colonel", "Lt.Col."), ("Colonel", "Col."),
                ("General de brigadă", "Gen.Bg."), ("General de divizie", "Gen.Div."),
                ("General de corp de armată", "Gen.C.A."), ("General de armată", "Gen.Arm."), ("Mareșal", "Mar.")],
    "india": [("Sepoy", "Sep."), ("Lance Naik", "L/Nk."), ("Naik", "Nk."), ("Havildar", "Hav."),
              ("Havildar", "Hav."), ("Company Havildar Major", "CHM"), ("Jemadar", "Jem."), ("Subedar", "Sub."),
              ("Second Lieutenant", "2/Lt."), ("Lieutenant", "Lt."), ("Captain", "Capt."), ("Major", "Maj."),
              ("Lieutenant Colonel", "Lt. Col."), ("Colonel", "Col."), ("Brigadier", "Brig."),
              ("Major General", "Maj. Gen."), ("Lieutenant General", "Lt. Gen."), ("General", "Gen."),
              ("Field Marshal", "FM")],
}
for _n in ("canada", "australia", "newzealand"):
    LADDERS[_n] = LADDERS["uk"]

MEDALS = {
    "usa": ["Purple Heart", "Bronze Star", "Silver Star", "Distinguished Service Cross", "Medal of Honor"],
    "uk": ["Wound Stripe", "Military Medal", "Military Cross", "Distinguished Service Order", "Victoria Cross"],
    "canada": ["Wound Stripe", "Military Medal", "Military Cross", "Distinguished Service Order", "Victoria Cross"],
    "australia": ["Wound Stripe", "Military Medal", "Military Cross", "Distinguished Service Order", "Victoria Cross"],
    "newzealand": ["Wound Stripe", "Military Medal", "Military Cross", "Distinguished Service Order", "Victoria Cross"],
    "india": ["Wound Stripe", "Indian Distinguished Service Medal", "Military Cross", "Distinguished Service Order",
              "Victoria Cross"],
    "ussr": ["Wound Stripe", "Medal 'For Courage'", "Order of the Red Star", "Order of the Red Banner",
             "Hero of the Soviet Union"],
    "germany": ["Verwundetenabzeichen", "Eisernes Kreuz II. Klasse", "Eisernes Kreuz I. Klasse",
                "Deutsches Kreuz in Gold", "Ritterkreuz des Eisernen Kreuzes"],
    "italy": ["Distintivo per Ferita", "Croce di Guerra", "Medaglia di Bronzo al Valor Militare",
              "Medaglia d'Argento al Valor Militare", "Medaglia d'Oro al Valor Militare"],
    "japan": ["Wound Badge", "Order of the Sacred Treasure", "Order of the Rising Sun",
              "Order of the Golden Kite (5th class)", "Order of the Golden Kite (1st class)"],
    "france": ["Insigne des blessés", "Croix de Guerre", "Médaille militaire", "Légion d'honneur (chevalier)",
               "Légion d'honneur (officier)"],
    "poland": ["Odznaka za Rany", "Krzyż Walecznych", "Srebrny Krzyż Zasługi", "Virtuti Militari (srebrny)",
               "Virtuti Militari (złoty)"],
    "china": ["Wound Badge", "Order of the Cloud and Banner", "Order of Loyalty and Diligence",
              "Order of the Precious Tripod", "Order of Blue Sky and White Sun"],
    "finland": ["Haavamerkki", "Vapaudenmitali", "Vapaudenristi IV lk", "Vapaudenristi III lk",
                "Mannerheim-risti"],
    "hungary": ["Sebesülési érem", "Nagy ezüst vitézségi érem", "Magyar Érdemrend", "Signum Laudis",
                "Arany vitézségi érem"],
    "romania": ["Semnul Onoarei", "Crucea de Merit", "Ordinul Coroana României", "Ordinul Steaua României",
                "Ordinul Mihai Viteazul"],
}


# the rank a squad (section) leader actually held
SQUAD_LEADER_GRADE = {"usa": STAFF_SGT, "uk": CORPORAL, "canada": CORPORAL, "australia": CORPORAL,
                      "newzealand": CORPORAL, "india": CORPORAL, "finland": CORPORAL, "ussr": SERGEANT,
                      "germany": SERGEANT, "italy": SERGEANT, "japan": SERGEANT, "france": SERGEANT,
                      "poland": SERGEANT, "china": SERGEANT, "hungary": SERGEANT, "romania": SERGEANT}

# armies that would take orders from each other's officers below general rank
COALITION = {"uk": "cw", "canada": "cw", "australia": "cw", "newzealand": "cw", "india": "cw"}

ACK = {
    "usa": ["Yes, sir!", "Wilco.", "Roger that, sir.", "On it!", "You got it, sir."],
    "uk": ["Sir!", "Right you are, sir.", "Very good, sir.", "Wilco.", "Understood, sir."],
    "ussr": ["Tak tochno!", "Est'!", "Slushayus', tovarishch komandir!", "Ponyal!"],
    "germany": ["Jawohl, Herr {rank}!", "Zu Befehl!", "Verstanden!", "Jawohl!"],
    "italy": ["Signorsì!", "Agli ordini!", "Subito, signor {rank}!"],
    "japan": ["Hai!", "Ryōkai!", "Wakarimashita!", "Hai, {rank}-dono!"],
    "france": ["À vos ordres, mon {rank}!", "Compris!", "Bien, mon {rank}."],
    "poland": ["Tak jest!", "Rozkaz!", "Tak jest, panie {rank}!"],
    "finland": ["Selvä!", "Käsky!", "Kyllä, herra {rank}!"],
    "hungary": ["Igenis!", "Értettem!", "Parancs!"],
    "romania": ["Să trăiți!", "Am înțeles!", "Ordonați!"],
    "china": ["Shì!", "Míngbai!", "Zūnmìng!"],
}
REFUSE = {
    "usa": ["We can't, sir - we'll be cut to pieces!", "Sir, we're pinned! Nobody's moving!",
            "Are you crazy? That's suicide!"],
    "uk": ["Can't be done, sir, not under this fire!", "We're pinned, sir! Give us a minute!",
           "With respect, sir - no bloody way."],
    "germany": ["Unmöglich, Herr {rank}! Wir sind festgenagelt!", "Das ist Selbstmord!"],
    "ussr": ["Nevozmozhno, tovarishch komandir! Prizhali!", "Nas vsekh tut polozhat!"],
}
for _n in ("canada", "australia", "newzealand", "india"):
    ACK[_n] = ACK["uk"]
    REFUSE[_n] = REFUSE["uk"]

# radio callsigns: companies, and the word for "commander"
CALLSIGNS = {
    "usa": (["Able", "Baker", "Charlie", "Dog", "Easy", "Fox", "George", "How"], "Six"),
    "uk": (["Apple", "Beer", "Charlie", "Don", "Edward", "Freddie"], "Sunray"),
    "germany": (["Adler", "Bussard", "Condor", "Drossel", "Elster", "Falke"], "Chef"),
    "ussr": (["Berezka", "Volga", "Granit", "Dnepr", "Zarya", "Kama"], "Pervyy"),
    "japan": (["Matsu", "Take", "Ume", "Sakura", "Kiku", "Fuji"], "Taichō"),
    "italy": (["Aquila", "Leone", "Falco", "Lupo", "Orso"], "Comandante"),
    "france": (["Alpha", "Bravo", "Castor", "Dauphin", "Esope"], "Autorité"),
}
for _n in ("canada", "australia", "newzealand", "india", "poland"):
    CALLSIGNS[_n] = CALLSIGNS["uk"]

# what each army called its sub-units: (platoon, company, battalion, regiment, division)
UNIT_WORDS = {
    "usa": ("Platoon", "Company", "Battalion", "Infantry Regiment", "Division"),
    "uk": ("Platoon", "Company", "Battalion", "Brigade", "Division"),
    "germany": ("Zug", "Kompanie", "Bataillon", "Grenadier-Regiment", "Division"),
    "ussr": ("vzvod", "rota", "batal'on", "strelkovyy polk", "diviziya"),
    "japan": ("shōtai", "chūtai", "daitai", "rentai", "shidan"),
    "italy": ("Plotone", "Compagnia", "Battaglione", "Reggimento", "Divisione"),
    "france": ("section", "compagnie", "bataillon", "régiment", "division"),
    "poland": ("pluton", "kompania", "batalion", "pułk", "dywizja"),
    "finland": ("joukkue", "komppania", "pataljoona", "rykmentti", "divisioona"),
}
for _n in ("canada", "australia", "newzealand", "india"):
    UNIT_WORDS[_n] = UNIT_WORDS["uk"]


# ---------------------------------------------------------------- the other services, on the same 0-18 scale
NAVY = {
    "usa": [("Seaman Second Class", "S2c"), ("Seaman First Class", "S1c"), ("Petty Officer Third Class", "PO3"),
            ("Petty Officer Second Class", "PO2"), ("Petty Officer First Class", "PO1"), ("Chief Petty Officer", "CPO"),
            ("Chief Petty Officer", "CPO"), ("Chief Warrant Officer", "CWO"), ("Ensign", "Ens."),
            ("Lieutenant (junior grade)", "Lt(jg)"), ("Lieutenant", "Lt."), ("Lieutenant Commander", "LtCdr."),
            ("Commander", "Cdr."), ("Captain", "Capt."), ("Commodore", "Cdre."), ("Rear Admiral", "RAdm."),
            ("Vice Admiral", "VAdm."), ("Admiral", "Adm."), ("Fleet Admiral", "FAdm.")],
    "uk": [("Ordinary Seaman", "OS"), ("Able Seaman", "AB"), ("Leading Seaman", "LS"), ("Petty Officer", "PO"),
           ("Petty Officer", "PO"), ("Chief Petty Officer", "CPO"), ("Chief Petty Officer", "CPO"),
           ("Warrant Officer", "WO"), ("Midshipman", "Mid."), ("Sub-Lieutenant", "S/Lt."), ("Lieutenant", "Lt."),
           ("Lieutenant-Commander", "Lt.Cdr."), ("Commander", "Cdr."), ("Captain", "Capt."), ("Commodore", "Cdre."),
           ("Rear-Admiral", "R.Adm."), ("Vice-Admiral", "V.Adm."), ("Admiral", "Adm."),
           ("Admiral of the Fleet", "AoF")],
    "germany": [("Matrose", "Mt."), ("Obermatrose", "OMt."), ("Maat", "Mt."), ("Obermaat", "OMaat"),
                ("Bootsmann", "Btsm."), ("Oberbootsmann", "OBtsm."), ("Stabsbootsmann", "StBtsm."),
                ("Stabsoberbootsmann", "StOBtsm."), ("Leutnant zur See", "Lt.z.S."), ("Oberleutnant zur See", "Oblt.z.S."),
                ("Kapitänleutnant", "Kptlt."), ("Korvettenkapitän", "KKpt."), ("Fregattenkapitän", "FKpt."),
                ("Kapitän zur See", "Kpt.z.S."), ("Kommodore", "Kom."), ("Konteradmiral", "KAdm."),
                ("Vizeadmiral", "VAdm."), ("Admiral", "Adm."), ("Großadmiral", "GAdm.")],
    "japan": [("Nitō Suihei", "Sea.2"), ("Ittō Suihei", "Sea.1"), ("Suihei-chō", "L.Sea."), ("Nitō Heisō", "PO2"),
              ("Ittō Heisō", "PO1"), ("Jōtō Heisō", "CPO"), ("Heisō-chō", "SCPO"), ("Heisō-chō", "SCPO"),
              ("Shōi", "Ens."), ("Chūi", "Lt(jg)"), ("Tai-i", "Lt."), ("Shōsa", "LtCdr."), ("Chūsa", "Cdr."),
              ("Taisa", "Capt."), ("Shōshō", "RAdm."), ("Chūjō", "VAdm."), ("Chūjō", "VAdm."), ("Taishō", "Adm."),
              ("Gensui Kaigun Taishō", "FAdm.")],
    "ussr": [("Krasnoflotets", "Krfl."), ("Starshiy Krasnoflotets", "St.Krfl."), ("Starshina 2 stat'i", "Stsh.2"),
             ("Starshina 1 stat'i", "Stsh.1"), ("Glavny Starshina", "Gl.Stsh."), ("Michman", "Mich."),
             ("Michman", "Mich."), ("Michman", "Mich."), ("Mladshiy Leytenant", "Ml.Lt."), ("Leytenant", "Lt."),
             ("Starshiy Leytenant", "St.Lt."), ("Kapitan-Leytenant", "Kpt-Lt."), ("Kapitan 3 ranga", "Kpt.3"),
             ("Kapitan 2 ranga", "Kpt.2"), ("Kapitan 1 ranga", "Kpt.1"), ("Kontr-Admiral", "K-Adm."),
             ("Vitse-Admiral", "V-Adm."), ("Admiral", "Adm."), ("Admiral Flota", "Adm.Fl.")],
    "italy": [("Marinaio", "Mar."), ("Comune di 1ª classe", "Com.1"), ("Sottocapo", "Sottoc."), ("Sergente", "Serg."),
              ("Secondo Capo", "2°Capo"), ("Capo di 3ª classe", "Capo3"), ("Capo di 2ª classe", "Capo2"),
              ("Capo di 1ª classe", "Capo1"), ("Guardiamarina", "GM"), ("Sottotenente di Vascello", "S.T.V."),
              ("Tenente di Vascello", "T.V."), ("Capitano di Corvetta", "C.C."), ("Capitano di Fregata", "C.F."),
              ("Capitano di Vascello", "C.V."), ("Contrammiraglio", "C.Amm."), ("Ammiraglio di Divisione", "Amm.D."),
              ("Ammiraglio di Squadra", "Amm.Sq."), ("Ammiraglio d'Armata", "Amm.A."), ("Grande Ammiraglio", "G.Amm.")],
    "france": [("Matelot", "Mat."), ("Quartier-maître de 2e classe", "QM2"), ("Quartier-maître de 1re classe", "QM1"),
               ("Second-maître", "2e M."), ("Maître", "M."), ("Premier maître", "1er M."), ("Maître principal", "M.P."),
               ("Maître principal", "M.P."), ("Enseigne de vaisseau de 2e classe", "EV2"),
               ("Enseigne de vaisseau de 1re classe", "EV1"), ("Lieutenant de vaisseau", "LV"),
               ("Capitaine de corvette", "CC"), ("Capitaine de frégate", "CF"), ("Capitaine de vaisseau", "CV"),
               ("Contre-amiral", "CA"), ("Vice-amiral", "VA"), ("Vice-amiral d'escadre", "VAE"), ("Amiral", "Am."),
               ("Amiral de la flotte", "AF")],
}
AIR = {
    "uk": [("Aircraftman 2nd Class", "AC2"), ("Leading Aircraftman", "LAC"), ("Corporal", "Cpl."),
           ("Sergeant", "Sgt."), ("Flight Sergeant", "F/Sgt."), ("Flight Sergeant", "F/Sgt."), ("Warrant Officer", "W/O"),
           ("Warrant Officer", "W/O"), ("Pilot Officer", "P/O"), ("Flying Officer", "F/O"),
           ("Flight Lieutenant", "F/Lt."), ("Squadron Leader", "S/Ldr."), ("Wing Commander", "W/Cdr."),
           ("Group Captain", "G/Capt."), ("Air Commodore", "A/Cdre."), ("Air Vice-Marshal", "AVM"),
           ("Air Marshal", "AM"), ("Air Chief Marshal", "ACM"), ("Marshal of the Royal Air Force", "MRAF")],
    "germany": [("Flieger", "Flg."), ("Obergefreiter", "OGefr."), ("Gefreiter", "Gefr."), ("Unteroffizier", "Uffz."),
                ("Unterfeldwebel", "Ufw."), ("Feldwebel", "Fw."), ("Oberfeldwebel", "Ofw."), ("Stabsfeldwebel", "Stfw."),
                ("Leutnant", "Lt."), ("Oberleutnant", "Oblt."), ("Hauptmann", "Hptm."), ("Major", "Maj."),
                ("Oberstleutnant", "Obstlt."), ("Oberst", "Oberst"), ("Generalmajor", "GenMaj."),
                ("Generalleutnant", "GenLt."), ("General der Flieger", "Gen.d.Fl."), ("Generaloberst", "GenOberst"),
                ("Reichsmarschall", "RM")],
    "italy": [("Aviere", "Av."), ("Aviere scelto", "Av.sc."), ("Primo aviere", "1°Av."), ("Sergente", "Serg."),
              ("Sergente maggiore", "Serg.M."), ("Maresciallo di 3ª classe", "Mar.3"), ("Maresciallo di 2ª classe", "Mar.2"),
              ("Maresciallo di 1ª classe", "Mar.1"), ("Sottotenente", "S.Ten."), ("Tenente", "Ten."),
              ("Capitano", "Cap."), ("Maggiore", "Magg."), ("Tenente Colonnello", "Ten.Col."), ("Colonnello", "Col."),
              ("Generale di Brigata Aerea", "Gen.B.A."), ("Generale di Divisione Aerea", "Gen.D.A."),
              ("Generale di Squadra Aerea", "Gen.S.A."), ("Generale d'Armata Aerea", "Gen.A.A."),
              ("Maresciallo dell'Aria", "Mar.dell'Aria")],
}
AIR["canada"] = AIR["australia"] = AIR["newzealand"] = AIR["india"] = AIR["uk"]
NAVY["canada"] = NAVY["australia"] = NAVY["newzealand"] = NAVY["india"] = NAVY["uk"]
for _n in ("poland",):
    NAVY[_n] = NAVY["uk"]


def ladder(nation: str, service: str = "army"):
    if service == "ss":
        from .special import SS_LADDER
        return SS_LADDER
    if service == "navy" and nation in NAVY:
        return NAVY[nation]
    if service == "air" and nation in AIR:
        return AIR[nation]          # (the USAAF, the VVS and the Japanese army and navy air arms used their own
    return LADDERS.get(nation, LADDERS["usa"])     # service's ranks: army or navy)


def rank_title(nation: str, grade: int, short: bool = True, service: str = "army") -> str:
    lad = ladder(nation, service)
    r = lad[max(0, min(grade, len(lad) - 1))]
    return r[1] if short else r[0]


def address(nation: str, grade: int) -> str:
    """How a subordinate addresses someone of this grade ('Leutnant', 'lieutenant')."""
    full = rank_title(nation, grade, False)
    return full.split()[-1] if nation in ("germany", "italy", "poland", "finland") else full.split()[-1].lower()


def stars(grade: int) -> str:
    return STARS.get(grade, "")


def same_army(a: str, b: str) -> bool:
    return a == b or (COALITION.get(a) is not None and COALITION.get(a) == COALITION.get(b))


def words(nation: str):
    return UNIT_WORDS.get(nation, UNIT_WORDS["usa"])
