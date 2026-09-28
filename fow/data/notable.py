"""Notable regular units: the divisions (and a few brigades, regiments and battalions) that fought each battle -
for you to serve in, and for everyone who does to carry the right regiments on their papers.

Each: the army, its name as its own men wrote it (and, where a battle knew it by another, `div_by`), what it was
called, the regiments or battalions that really served in it (designations are drawn from these: a man of the
Big Red One is in the 16th, 18th or 26th Infantry, not an invented 742nd), the battles here it fought, and a
line of its history.  `regiments` None: the army's usual numbering (where the record isn't certain enough to
name them).  `veteran`: long service before this battle - the men know their business (a little skill and
nerve).  Elite parachute, commando and SS formations are in special.py.
"""
from __future__ import annotations

NOTABLE = {
    # ================================================================== the United States
    "us_1id": dict(nation="usa", div="1st Infantry Division", nick="The Big Red One",
                   theatres=["tunisia43", "sicily43", "omaha44"], veteran=True,
                   regiments=["16th Infantry Regiment", "18th Infantry Regiment", "26th Infantry Regiment"],
                   desc="North Africa, Sicily - then the first wave at Omaha, on Easy Red and Fox Green. 'No mission "
                        "too difficult, no sacrifice too great. Duty first.'"),
    "us_29id": dict(nation="usa", div="29th Infantry Division", nick="Blue and Gray", theatres=["omaha44", "bocage44"],
                    regiments=["115th Infantry Regiment", "116th Infantry Regiment", "175th Infantry Regiment"],
                    desc="National Guardsmen from Virginia and Maryland. The 116th landed on Dog Green in the first "
                         "wave; then the hedgerows, all the way to Saint-Lô. 'Twenty-nine, let's go!'"),
    "us_30id": dict(nation="usa", div="30th Infantry Division", nick="Old Hickory", theatres=["bocage44"],
                    regiments=["117th Infantry Regiment", "119th Infantry Regiment", "120th Infantry Regiment"],
                    desc="Tennessee and the Carolinas. Saint-Lô, the breakout - and Mortain, where a battalion of "
                         "the 120th held Hill 314 for five days, cut off."),
    "us_4id": dict(nation="usa", div="4th Infantry Division", nick="Ivy", theatres=["hurtgen44"], veteran=True,
                   regiments=["8th Infantry Regiment", "12th Infantry Regiment", "22nd Infantry Regiment"],
                   desc="Utah Beach on D-Day, Cherbourg, Paris - then the Hürtgen Forest, where the 22nd Infantry "
                        "lost more than two thousand men in eighteen days."),
    "us_28id": dict(nation="usa", div="28th Infantry Division", nick="Keystone", theatres=["hurtgen44"],
                    regiments=["109th Infantry Regiment", "110th Infantry Regiment", "112th Infantry Regiment"],
                    desc="Pennsylvania's Guard - 'the Bloody Bucket' to the Germans, for the red keystone on its "
                         "sleeve. Schmidt and Kommerscheidt: one of the costliest divisional actions of the war."),
    "us_9id": dict(nation="usa", div="9th Infantry Division", nick="Old Reliables", theatres=["tunisia43", "hurtgen44"],
                   regiments=["39th Infantry Regiment", "47th Infantry Regiment", "60th Infantry Regiment"],
                   desc="North Africa, Sicily, Cherbourg - and first into the Hürtgen in the autumn of 1944."),
    "us_45id": dict(nation="usa", div="45th Infantry Division", nick="Thunderbirds", theatres=["sicily43"],
                    regiments=["157th Infantry Regiment", "179th Infantry Regiment", "180th Infantry Regiment"],
                    desc="Guardsmen from Oklahoma, Colorado, New Mexico and Arizona, many of them Native Americans. "
                         "Sicily, then Salerno and Anzio."),
    "us_1ad": dict(nation="usa", div="1st Armored Division", nick="Old Ironsides", theatres=["tunisia43"],
                   regiments=["6th Armored Infantry Regiment", "1st Armored Regiment", "13th Armored Regiment"],
                   desc="America's first armoured division into action against the Germans - and badly mauled at "
                        "Sidi Bou Zid and the Kasserine Pass, February 1943."),
    "us_2ad": dict(nation="usa", div="2nd Armored Division", nick="Hell on Wheels", theatres=["sicily43", "bocage44"],
                   regiments=["41st Armored Infantry Regiment", "66th Armored Regiment", "67th Armored Regiment"],
                   desc="Patton's old division: Sicily, then Cobra's breakout out of the hedgerows."),
    "us_10ad": dict(nation="usa", div="10th Armored Division", nick="Tiger", theatres=["bastogne44"],
                    regiments=["20th Armored Infantry Battalion", "54th Armored Infantry Battalion", "3rd Tank Battalion"],
                    desc="Combat Command B raced into Bastogne and held the roads at Noville, Longvilly and Marvie "
                         "beside the paratroopers."),
    "us_82ab": dict(nation="usa", div="82nd Airborne Division", nick="All American",
                    theatres=["sicily43", "normandy_airborne44"], veteran=True,
                    regiments=["505th Parachute Infantry Regiment", "504th Parachute Infantry Regiment",
                               "507th Parachute Infantry Regiment", "508th Parachute Infantry Regiment",
                               "325th Glider Infantry Regiment"],
                    desc="Sicily by night - then Sainte-Mère-Église, which the 505th took before dawn on D-Day."),
    "us_101ab": dict(nation="usa", div="101st Airborne Division", nick="Screaming Eagles",
                     theatres=["normandy_airborne44", "bastogne44"],
                     regiments=["501st Parachute Infantry Regiment", "502nd Parachute Infantry Regiment",
                                "506th Parachute Infantry Regiment", "327th Glider Infantry Regiment"],
                     desc="'Rendezvous with destiny.' The causeways behind Utah and Carentan - then surrounded at "
                          "Bastogne, and McAuliffe's answer: 'Nuts!'"),
    "us_1mar": dict(nation="usa", div="1st Marine Division", nick="The Old Breed", theatres=["guadalcanal42", "okinawa45"],
                    regiments=["1st Marines", "5th Marines", "7th Marines"],
                    desc="Guadalcanal - America's first offensive of the war - then Cape Gloucester, Peleliu and "
                         "Okinawa."),
    "us_3mar": dict(nation="usa", div="3rd Marine Division", nick="", theatres=["iwojima45"],
                    regiments=["3rd Marines", "9th Marines", "21st Marines"],
                    desc="Bougainville, Guam - then Iwo Jima's centre: the second airfield and the high ground "
                         "beyond it."),
    "us_4mar": dict(nation="usa", div="4th Marine Division", nick="The Fighting Fourth", theatres=["iwojima45"],
                    regiments=["23rd Marines", "24th Marines", "25th Marines"],
                    desc="Roi-Namur, Saipan, Tinian - and Iwo Jima: the Meat Grinder, Hill 382 and the Amphitheater."),
    "us_5mar": dict(nation="usa", div="5th Marine Division", nick="Spearhead", theatres=["iwojima45"],
                    regiments=["26th Marines", "27th Marines", "28th Marines"],
                    desc="Formed for Iwo Jima. The 28th Marines took Mount Suribachi and raised the flag on the "
                         "fourth day."),
    "us_6mar": dict(nation="usa", div="6th Marine Division", nick="Striking Sixth", theatres=["okinawa45"],
                    regiments=["4th Marines", "22nd Marines", "29th Marines"],
                    desc="Formed on Guadalcanal in 1944 and broken up after the war: its whole war was Okinawa - and "
                         "Sugar Loaf Hill."),
    "us_96id": dict(nation="usa", div="96th Infantry Division", nick="Deadeyes", theatres=["okinawa45"],
                    regiments=["381st Infantry Regiment", "382nd Infantry Regiment", "383rd Infantry Regiment"],
                    desc="Leyte, then Okinawa: Kakazu Ridge, Conical Hill, the Maeda Escarpment."),
    # ================================================================== the British Empire
    "uk_51hd": dict(nation="uk", div="51st Highland Division", nick="The Highway Decorators",
                    theatres=["alamein42", "sicily43"], veteran=True,
                    regiments=["5th Black Watch", "1st Gordon Highlanders", "5th Seaforth Highlanders",
                               "5th Cameron Highlanders", "7th Argyll and Sutherland Highlanders"],
                    desc="Re-formed after St-Valéry's surrender in 1940, it went through the minefields at Alamein "
                         "behind its pipers. 'HD' on every wall it passed."),
    "uk_7ad": dict(nation="uk", div="7th Armoured Division", nick="The Desert Rats", theatres=["alamein42", "bocage44"],
                   veteran=True,
                   regiments=["1st Royal Tank Regiment", "5th Royal Tank Regiment", "1st Rifle Brigade",
                              "1/7th Queen's Royal Regiment", "4th County of London Yeomanry"],
                   desc="The jerboa on the sleeve: from the first desert battles of 1940 to Alamein - then "
                        "Normandy, and Villers-Bocage."),
    "uk_43d": dict(nation="uk", div="43rd (Wessex) Division", nick="", theatres=["bocage44", "arnhem44"],
                   regiments=["4th Somerset Light Infantry", "5th Wiltshire Regiment", "4th Dorsetshire Regiment",
                              "5th Duke of Cornwall's Light Infantry", "7th Hampshire Regiment"],
                   desc="Hill 112, above the Odon, July 1944 - 'whoever holds Hill 112 holds Normandy' - and the "
                        "Rhine at Driel two months later."),
    "uk_15d": dict(nation="uk", div="15th (Scottish) Division", nick="", theatres=["bocage44"],
                   regiments=["9th Cameronians", "2nd Glasgow Highlanders", "6th Royal Scots Fusiliers",
                              "10th Highland Light Infantry", "2nd Argyll and Sutherland Highlanders"],
                   desc="Operation Epsom, June 1944: the 'Scottish Corridor' to the Odon."),
    "uk_1ab": dict(nation="uk", div="1st Airborne Division", nick="The Red Devils", theatres=["arnhem44"],
                   regiments=["2nd Parachute Battalion", "1st Parachute Battalion", "3rd Parachute Battalion",
                              "10th Parachute Battalion", "156th Parachute Battalion", "1st Border Regiment",
                              "7th King's Own Scottish Borderers"],
                   desc="A bridge too far: Frost's 2nd Battalion held the north end of the Arnhem road bridge for "
                        "four days; the rest were squeezed into Oosterbeek."),
    "uk_2d": dict(nation="uk", div="2nd Division", nick="", theatres=["kohima44"],
                  regiments=["1st Royal Norfolk Regiment", "2nd Dorsetshire Regiment", "1st Royal Scots",
                             "1st Queen's Own Cameron Highlanders", "1st Royal Welch Fusiliers",
                             "7th Worcestershire Regiment"],
                  desc="Came up the road from Dimapur to relieve Kohima - and fought across the District "
                       "Commissioner's tennis court."),
    "uk_rwk": dict(nation="uk", div="161st Indian Brigade", div_as="4th Bn Royal West Kent Regiment", nick="",
                   theatres=["kohima44"], regiments=["4th Royal West Kent Regiment"],
                   desc="Four hundred men of the West Kents held the Kohima ridge for two weeks against a whole "
                        "Japanese division."),
    "ca_3d": dict(nation="canada", div="3rd Canadian Infantry Division", nick="", theatres=["bocage44"],
                  regiments=["Royal Winnipeg Rifles", "Regina Rifles", "Queen's Own Rifles of Canada",
                             "North Shore (New Brunswick) Regiment", "Régiment de la Chaudière",
                             "North Nova Scotia Highlanders"],
                  desc="Juno Beach on D-Day, then Authie, Carpiquet and the long fight for Caen."),
    "ca_1d": dict(nation="canada", div="1st Canadian Infantry Division", nick="", theatres=["sicily43"],
                  regiments=["Royal Canadian Regiment", "Hastings and Prince Edward Regiment",
                             "48th Highlanders of Canada", "Princess Patricia's Canadian Light Infantry",
                             "Seaforth Highlanders of Canada", "Loyal Edmonton Regiment"],
                  desc="Landed at Pachino in July 1943: Canada's first long campaign - Sicily, then up Italy."),
    "au_9d": dict(nation="australia", div="9th Australian Division", nick="The Rats of Tobruk", theatres=["alamein42"],
                  veteran=True,
                  regiments=["2/13th Battalion", "2/15th Battalion", "2/17th Battalion", "2/24th Battalion",
                             "2/48th Battalion"],
                  desc="Held Tobruk through the siege of 1941, then broke the northern flank at Alamein: the 2/48th "
                       "won more VCs than any battalion in the Australian army."),
    "nz_2d": dict(nation="newzealand", div="2nd New Zealand Division", nick="", theatres=["crete41", "alamein42",
                                                                                          "cassino44"],
                  veteran=True,
                  regiments=["22nd Battalion", "23rd Battalion", "26th Battalion", "28th (Maori) Battalion"],
                  desc="Freyberg's division: Greece, Crete, the desert, and the rubble of Cassino town. The Maori "
                       "Battalion's haka before the charge."),
    "in_4d": dict(nation="india", div="4th Indian Division", nick="The Red Eagles", theatres=["alamein42", "cassino44"],
                  veteran=True,
                  regiments=["1st/2nd Gurkha Rifles", "1st/9th Gurkha Rifles", "4th/6th Rajputana Rifles",
                             "1st Royal Sussex Regiment"],
                  desc="Sidi Barrani, Keren, the desert - then Monastery Hill at Cassino, February 1944."),
    "in_161": dict(nation="india", div="161st Indian Brigade", nick="", theatres=["kohima44"],
                   regiments=["1st/1st Punjab Regiment", "4th/7th Rajput Regiment", "1st Assam Regiment"],
                   desc="The brigade that got to Kohima first - and held on at Jotsoma while the ridge was besieged."),
    # ================================================================== the Soviet Union
    "su_13gd": dict(nation="ussr", div="13th Guards Rifle Division", nick="", theatres=["stalingrad42"],
                    regiments=["34th Guards Rifle Regiment", "39th Guards Rifle Regiment", "42nd Guards Rifle Regiment"],
                    desc="Rodimtsev's guardsmen crossed the Volga under fire on the night of 14 September 1942, "
                         "straight into the fight for the central station - and Pavlov's House."),
    "su_284": dict(nation="ussr", div="284th Rifle Division", nick="", theatres=["stalingrad42"],
                   regiments=["1043rd Rifle Regiment", "1045th Rifle Regiment", "1047th Rifle Regiment"],
                   desc="Batyuk's Siberians on Mamayev Kurgan - Vasily Zaitsev's division."),
    "su_37gd": dict(nation="ussr", div="37th Guards Rifle Division", nick="", theatres=["stalingrad42"],
                    regiments=["109th Guards Rifle Regiment", "114th Guards Rifle Regiment",
                               "118th Guards Rifle Regiment"],
                    desc="Zholudev's former paratroopers, thrown into the Tractor Factory in October 1942."),
    "su_316": dict(nation="ussr", div="316th Rifle Division (Panfilov)", nick="The Panfilov Men", theatres=["moscow41"],
                   regiments=["1073rd Rifle Regiment", "1075th Rifle Regiment", "1077th Rifle Regiment"],
                   desc="Kazakh and Kyrgyz conscripts under Panfilov on the Volokolamsk road, made 8th Guards in "
                        "November 1941."),
    "su_78": dict(nation="ussr", div="78th Rifle Division (Siberian)", nick="", theatres=["moscow41"], regiments=None,
                  desc="Beloborodov's Siberians, rushed from the Far East to the Istra line - 9th Guards by the end "
                       "of November 1941."),
    "su_307": dict(nation="ussr", div="307th Rifle Division", nick="", theatres=["kursk43"], regiments=None,
                   desc="Ponyri, July 1943: the station and the village on the northern face, lost and retaken again "
                        "and again against Model's panzers."),
    "su_150": dict(nation="ussr", div="150th Rifle Division", nick="Idritsa", theatres=["berlin45"],
                   regiments=["756th Rifle Regiment", "674th Rifle Regiment", "469th Rifle Regiment"],
                   desc="Its 756th Regiment's men raised the Victory Banner over the Reichstag, 30 April 1945."),
    "su_171": dict(nation="ussr", div="171st Rifle Division", nick="", theatres=["berlin45"], regiments=None,
                   desc="Beside the 150th at the Reichstag, across the Moltke bridge and the Königsplatz."),
    "pl_1kos": dict(nation="poland", div="1st Tadeusz Kościuszko Infantry Division", nick="", theatres=["berlin45"],
                    regiments=["1st Infantry Regiment", "2nd Infantry Regiment", "3rd Infantry Regiment"],
                    desc="Poles raised in the Soviet Union: Lenino in 1943 - and the streets of Berlin in 1945."),
    # ================================================================== Poland, France, China, Finland
    "pl_3car": dict(nation="poland", div="3rd Carpathian Rifle Division", nick="", theatres=["cassino44"], veteran=True,
                    regiments=["1st Carpathian Rifle Brigade", "2nd Carpathian Rifle Brigade"],
                    desc="Men who'd walked out of Soviet camps, through Persia and Palestine - and on 18 May 1944 "
                         "raised the Polish flag over the ruined monastery."),
    "pl_5kre": dict(nation="poland", div="5th Kresowa Infantry Division", nick="", theatres=["cassino44"],
                    regiments=["5th Wilno Infantry Brigade", "6th Lwów Infantry Brigade"],
                    desc="Anders' eastern Poles: Phantom Ridge and San Angelo above Cassino, May 1944."),
    "pl_14d": dict(nation="poland", div="14th Infantry Division", nick="", theatres=["poland39"],
                   regiments=["55th Infantry Regiment", "57th Infantry Regiment", "58th Infantry Regiment"],
                   desc="Armia Poznań's counter-attack on the Bzura, September 1939: the biggest battle of the "
                        "campaign."),
    "pl_1para": dict(nation="poland", div="1st Independent Parachute Brigade", nick="", theatres=["arnhem44"],
                     regiments=["1st Parachute Battalion", "2nd Parachute Battalion", "3rd Parachute Battalion"],
                     desc="Sosabowski's brigade, dropped at Driel under fire on 21 September 1944 - across the Rhine "
                          "from the men it had come to save."),
    "fr_3dcr": dict(nation="france", div="3e Division Cuirassée", nick="", theatres=["france40"],
                    regiments=["41e Bataillon de Chars de Combat", "45e Bataillon de Chars de Combat",
                               "16e Bataillon de Chasseurs Portés"],
                    desc="Its Char B1 bis tanks took the village of Stonne, and took it again - seventeen times it "
                         "changed hands in May 1940."),
    "fr_55di": dict(nation="france", div="55e Division d'Infanterie", nick="", theatres=["france40"],
                    regiments=["213e Régiment d'Infanterie", "295e Régiment d'Infanterie", "331e Régiment d'Infanterie"],
                    desc="Reservists holding the Meuse at Sedan when the panzers and the Stukas came, 13 May 1940."),
    "cn_74a": dict(nation="china", div="74th Army", nick="", theatres=["changsha41"], veteran=True,
                   regiments=["51st Division", "57th Division", "58th Division"],
                   desc="The best of the Nationalist field armies, with German-trained officers: Shanghai, Nanjing, "
                        "Changsha - and later the defence of Changde."),
    "cn_10a": dict(nation="china", div="10th Army", nick="", theatres=["changsha41"],
                   regiments=["3rd Division", "10th Division", "190th Division"],
                   desc="Li Yutang's 10th Army held Changsha's walls in the third battle, January 1942."),
    "fi_pans": dict(nation="finland", div="Panssaridivisioona", nick="", theatres=["karelia44"],
                    regiments=["Jääkäriprikaati", "Panssariprikaati"],
                    desc="Finland's only armoured division, with captured T-34s and German assault guns: the "
                         "counter-attacks at Tali-Ihantala, June 1944."),
    # ================================================================== Germany
    "de_gd": dict(nation="germany", div="Panzergrenadier-Division Großdeutschland", nick="GD",
                  div_by={"france40": "Infanterie-Regiment Großdeutschland"}, theatres=["france40", "kursk43"],
                  veteran=True,
                  regiments=["Grenadier-Regiment Großdeutschland", "Füsilier-Regiment Großdeutschland"],
                  regiments_by={"france40": ["Infanterie-Regiment Großdeutschland"]},
                  desc="The army's showpiece: across the Meuse at Sedan in 1940 - and in 1943 the spearhead of the "
                       "southern pincer at Kursk."),
    "de_1pz": dict(nation="germany", div="1. Panzer-Division", nick="", theatres=["poland39", "france40"],
                   regiments=["Schützen-Regiment 1", "Panzer-Regiment 1", "Panzer-Regiment 2"],
                   desc="Across Poland in 1939, then through the Ardennes and over the Meuse at Sedan in May 1940."),
    "de_10pz": dict(nation="germany", div="10. Panzer-Division", nick="", theatres=["france40", "tunisia43"],
                    regiments=["Schützen-Regiment 69", "Schützen-Regiment 86", "Panzer-Regiment 7"],
                    desc="Sedan in 1940 - and Kasserine in 1943, before it went into the bag at Tunis."),
    "de_7pz": dict(nation="germany", div="7. Panzer-Division", nick="The Ghost Division", theatres=["barbarossa41"],
                   regiments=["Schützen-Regiment 6", "Schützen-Regiment 7", "Panzer-Regiment 25"],
                   desc="Rommel's 'ghost division' of 1940 - then Barbarossa, the Smolensk pocket and the road to "
                        "Moscow."),
    "de_2pz": dict(nation="germany", div="2. Panzer-Division", nick="", theatres=["moscow41"],
                   regiments=["Schützen-Regiment 2", "Schützen-Regiment 304", "Panzer-Regiment 3"],
                   desc="Vienna's division: close enough in December 1941 to see the Kremlin's towers through field "
                        "glasses."),
    "de_106": dict(nation="germany", div="106. Infanterie-Division", nick="", theatres=["moscow41"],
                   regiments=["Infanterie-Regiment 239", "Infanterie-Regiment 240", "Infanterie-Regiment 241"],
                   desc="Rhinelanders and Westphalians, frozen in front of Moscow in the winter of 1941."),
    "de_15pz": dict(nation="germany", div="15. Panzer-Division", nick="", theatres=["alamein42"], veteran=True,
                    regiments=["Schützen-Regiment 115", "Panzer-Regiment 8"],
                    desc="The Afrikakorps' 'Fifteenth': Tobruk, Gazala, and the last stand at Alamein."),
    "de_164": dict(nation="germany", div="164. leichte Afrika-Division", nick="", theatres=["alamein42"],
                   regiments=["Panzergrenadier-Regiment 125", "Panzergrenadier-Regiment 382",
                              "Panzergrenadier-Regiment 433"],
                   desc="Flown in from Crete in the summer of 1942 to hold the line at Alamein."),
    "de_21pz": dict(nation="germany", div="21. Panzer-Division", nick="", theatres=["tunisia43"], veteran=True,
                    regiments=["Panzergrenadier-Regiment 104", "Panzer-Regiment 5"],
                    desc="The Afrikakorps' other panzer division: Sidi Bou Zid and Kasserine, February 1943."),
    "de_305": dict(nation="germany", div="305. Infanterie-Division", nick="", theatres=["stalingrad42"],
                   regiments=["Grenadier-Regiment 576", "Grenadier-Regiment 577", "Grenadier-Regiment 578"],
                   desc="Swabians from around Lake Constance: the Barrikady gun factory, October and November 1942."),
    "de_389": dict(nation="germany", div="389. Infanterie-Division", nick="", theatres=["stalingrad42"],
                   regiments=["Grenadier-Regiment 544", "Grenadier-Regiment 545", "Grenadier-Regiment 546"],
                   desc="The Tractor Factory and the workers' settlements of northern Stalingrad."),
    "de_14pz": dict(nation="germany", div="14. Panzer-Division", nick="", theatres=["stalingrad42"],
                    regiments=["Panzergrenadier-Regiment 103", "Panzergrenadier-Regiment 108", "Panzer-Regiment 36"],
                    desc="Into the factories of northern Stalingrad, and destroyed in the pocket."),
    "de_292": dict(nation="germany", div="292. Infanterie-Division", nick="", theatres=["kursk43"],
                   regiments=["Grenadier-Regiment 507", "Grenadier-Regiment 508", "Grenadier-Regiment 509"],
                   desc="Model's 9th Army on the northern face: the railway station at Ponyri."),
    "de_352": dict(nation="germany", div="352. Infanterie-Division", nick="", theatres=["omaha44", "bocage44"],
                   regiments=["Grenadier-Regiment 914", "Grenadier-Regiment 915", "Grenadier-Regiment 916"],
                   desc="Moved up to the Calvados coast in the spring of 1944, unknown to Allied intelligence: the men "
                        "in the bunkers above Omaha Beach."),
    "de_716": dict(nation="germany", div="716. Infanterie-Division", nick="", theatres=["omaha44"],
                   regiments=["Grenadier-Regiment 726", "Grenadier-Regiment 736"],
                   desc="A static coastal division of older men and Osttruppen, strung thinly along the beaches."),
    "de_91": dict(nation="germany", div="91. Luftlande-Division", nick="", theatres=["normandy_airborne44"],
                  regiments=["Grenadier-Regiment 1057", "Grenadier-Regiment 1058"],
                  desc="Trained to fight airborne landings - and on D-Day it lost its commander, Generalleutnant "
                       "Falley, to an American paratroopers' ambush."),
    "de_709": dict(nation="germany", div="709. Infanterie-Division", nick="", theatres=["normandy_airborne44"],
                   regiments=["Grenadier-Regiment 729", "Grenadier-Regiment 739", "Grenadier-Regiment 919"],
                   desc="Behind Utah Beach and around Cherbourg: old men, Georgians and Russians, and a few good "
                        "battalions."),
    "de_lehr": dict(nation="germany", div="Panzer-Lehr-Division", nick="", theatres=["bocage44", "bastogne44"],
                    regiments=["Panzergrenadier-Lehr-Regiment 901", "Panzergrenadier-Lehr-Regiment 902",
                               "Panzer-Lehr-Regiment 130"],
                    desc="Formed from the army's demonstration troops - the best-equipped panzer division in the West - "
                         "and all but destroyed under the carpet bombing of Operation Cobra."),
    "de_275": dict(nation="germany", div="275. Infanterie-Division", nick="", theatres=["hurtgen44"],
                   regiments=["Grenadier-Regiment 983", "Grenadier-Regiment 984", "Grenadier-Regiment 985"],
                   desc="Rebuilt after Normandy, and set to hold the Hürtgen: mines, log bunkers and tree bursts."),
    "de_89": dict(nation="germany", div="89. Infanterie-Division", nick="", theatres=["hurtgen44"],
                  regiments=["Grenadier-Regiment 1055", "Grenadier-Regiment 1056"],
                  desc="The 'Horseshoe' division: Schmidt and Kommerscheidt, November 1944."),
    "de_26vg": dict(nation="germany", div="26. Volksgrenadier-Division", nick="", theatres=["bastogne44"],
                    regiments=["Grenadier-Regiment 39", "Grenadier-Regiment 77", "Grenadier-Regiment 78"],
                    desc="Rebuilt from the wreck of the 26th Infantry Division - and given Bastogne to take."),
    "de_5geb": dict(nation="germany", div="5. Gebirgs-Division", nick="", theatres=["crete41"],
                    regiments=["Gebirgsjäger-Regiment 85", "Gebirgsjäger-Regiment 100"],
                    desc="Flown into Maleme under fire, May 1941, to finish what the paratroopers had started."),
    "de_mun": dict(nation="germany", div="Division Müncheberg", nick="", theatres=["berlin45"],
                   regiments=["Panzergrenadier-Regiment Müncheberg 1", "Panzergrenadier-Regiment Müncheberg 2"],
                   desc="Scraped together in March 1945 from training schools and remnants: the Seelow Heights, "
                        "then the streets of Berlin."),
    # ================================================================== Italy, Japan, Romania, Hungary
    "it_ariete": dict(nation="italy", div="Divisione Ariete", nick="", theatres=["alamein42"], veteran=True,
                      regiments=["8° Reggimento Bersaglieri", "132° Reggimento Carri"],
                      desc="The ram: Italy's best armoured division, fought to destruction at Alamein, November 1942."),
    "it_trento": dict(nation="italy", div="Divisione Trento", nick="", theatres=["alamein42"],
                      regiments=["61° Reggimento Fanteria", "62° Reggimento Fanteria"],
                      desc="Motorised infantry in the Alamein line, where the Australians came through in October 1942."),
    "it_centauro": dict(nation="italy", div="Divisione Centauro", nick="", theatres=["tunisia43"],
                        regiments=["5° Reggimento Bersaglieri", "31° Reggimento Carri"],
                        desc="Italy's armour in Tunisia: Kasserine and El Guettar."),
    "it_livorno": dict(nation="italy", div="Divisione Livorno", nick="", theatres=["sicily43"],
                       regiments=["33° Reggimento Fanteria", "34° Reggimento Fanteria"],
                       desc="Counter-attacked the Americans at Gela on 11 July 1943, and was shot to pieces by the "
                            "navy's guns."),
    "jp_2d": dict(nation="japan", div="2nd Division (Sendai)", nick="", theatres=["guadalcanal42"], veteran=True,
                  regiments=["4th Infantry Regiment", "16th Infantry Regiment", "29th Infantry Regiment"],
                  desc="Maruyama's division, landed on Guadalcanal to take Henderson Field in October 1942."),
    "jp_kawaguchi": dict(nation="japan", div="Kawaguchi Detachment", nick="", theatres=["guadalcanal42"],
                         regiments=["124th Infantry Regiment"],
                         desc="Kawaguchi's brigade, thrown against Edson's Ridge on 12-14 September 1942."),
    "jp_ichiki": dict(nation="japan", div="Ichiki Detachment", nick="", theatres=["guadalcanal42"],
                      regiments=["28th Infantry Regiment"],
                      desc="Nine hundred men who charged the Marines across the Tenaru in August 1942. Almost none came "
                           "back."),
    "jp_109": dict(nation="japan", div="109th Division", nick="", theatres=["iwojima45"],
                   regiments=["145th Infantry Regiment", "2nd Independent Mixed Brigade"],
                   desc="Kuribayashi's garrison: 21,000 men in eighteen kilometres of tunnels, each told to kill ten "
                        "Americans before he died."),
    "jp_24": dict(nation="japan", div="24th Division", nick="", theatres=["okinawa45"],
                  regiments=["22nd Infantry Regiment", "32nd Infantry Regiment", "89th Infantry Regiment"],
                  desc="Ushijima's 32nd Army on Okinawa: the Shuri line and the Kiyan peninsula."),
    "jp_62": dict(nation="japan", div="62nd Division", nick="", theatres=["okinawa45"],
                  regiments=["63rd Brigade", "64th Brigade"],
                  desc="Veterans of China, dug into Kakazu Ridge and the Shuri heights."),
    "jp_31": dict(nation="japan", div="31st Division", nick="", theatres=["kohima44"],
                  regiments=["58th Infantry Regiment", "124th Infantry Regiment", "138th Infantry Regiment"],
                  desc="Sato's division marched over the Chindwin hills to Kohima - and, starving, retreated against "
                       "orders."),
    "jp_3d": dict(nation="japan", div="3rd Division", nick="", theatres=["changsha41"], veteran=True,
                  regiments=["6th Infantry Regiment", "34th Infantry Regiment", "68th Infantry Regiment"],
                  desc="Nagoya's division: Shanghai in 1937, and the Changsha offensives."),
    "jp_6d": dict(nation="japan", div="6th Division", nick="", theatres=["changsha41"], veteran=True,
                  regiments=["13th Infantry Regiment", "23rd Infantry Regiment", "45th Infantry Regiment"],
                  desc="Kumamoto's division, one of the army's hardest - and at Nanjing in 1937."),
    "ro_1ad": dict(nation="romania", div="1st Armoured Division 'Romania Mare'", nick="", theatres=["uranus42"],
                   regiments=["1st Tank Regiment", "3rd Motorised Rifle Regiment"],
                   desc="Its Czech-built R-2 light tanks met the T-34s of Operation Uranus in November 1942."),
    "ro_5d": dict(nation="romania", div="5th Infantry Division", nick="", theatres=["uranus42"], regiments=None,
                  desc="On the Don bend, north-west of Stalingrad, when the Soviet offensive broke through."),
    "hu_7d": dict(nation="hungary", div="7th Light Division", nick="", theatres=["don43"], regiments=None,
                  desc="The 2nd Hungarian Army on the Don: Voronezh, January 1943, and the destruction of the army."),
}


def for_battle(nation, theatre) -> list:
    """The notable units of this army that fought this battle: [(key, entry)]."""
    return [(k, d) for k, d in NOTABLE.items() if d["nation"] == nation and (theatre is None or theatre in d["theatres"])]


def division(d, theatre) -> str:
    return (d.get("div_by") or {}).get(theatre) or d["div"]


def regiments(d, theatre) -> list | None:
    return (d.get("regiments_by") or {}).get(theatre) or d.get("regiments")


_BY_DIV = None


def by_division(name):
    """(entry, the battle its name belongs to or None) for a division as a designation or a battle's list names
    it - or None."""
    global _BY_DIV
    if _BY_DIV is None:
        _BY_DIV = {}
        for k, d in NOTABLE.items():
            _BY_DIV[d["div"]] = (d, None)
            if d.get("div_as"):
                _BY_DIV[d["div_as"]] = (d, None)
            for th, n in (d.get("div_by") or {}).items():
                _BY_DIV[n] = (d, th)
    return _BY_DIV.get(name)


def label(d) -> str:
    return d["div"] + (f" - '{d['nick']}'" if d.get("nick") else "")
