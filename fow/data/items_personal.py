"""A soldier's things: what each army ate and drank, smoked and swallowed to stay awake, carried for luck,
read, and kept.  Found in men's pockets and packs (roles.build_kit), on the dead, in the ruins.

Each has a use (play.use_tool): food and drink steady a man, stimulants keep him going (and cost him later),
charms and photographs and letters help or don't, newspapers carry the real news of the day (flavor.py).
"""
from __future__ import annotations

from .items import gear

_UK = ["uk", "canada", "australia", "newzealand", "india"]
IDS = set()                  # everything registered here (roles.build_kit picks from these)


def _p(id, name, tool, nations, years=(1900, 1950), *, weight=0.1, volume=0.1, glyph=";", color=(180, 170, 140),
       uses=1, desc="", **kw):
    IDS.add(id)
    return gear(id, name, "tool", tool=tool, nations=tuple(nations), years=years, weight=weight, volume=volume,
                glyph=glyph, color=color, uses=uses, desc=desc, freq=0, **kw)


# ---------------------------------------------------------------- rations
_p("k_ration", "K-ration (dinner unit)", "ration", ["usa"], (1942.5, 1950), weight=0.9, volume=0.6,
   desc="A waxed box the size of a Cracker Jack: a tin of processed cheese, biscuits, a fruit bar, powdered "
        "lemonade, gum and four cigarettes.")
_p("c_ration", "C-ration can", "ration", ["usa"], (1940, 1950), weight=0.5, volume=0.4,
   desc="Meat and beans, meat and vegetable hash, or meat and vegetable stew - and every man had a view on which "
        "was worst. Eaten cold as often as not.")
_p("d_ration", "D ration bar", "chocolate", ["usa"], (1941, 1950), weight=0.12, volume=0.05,
   desc="Chocolate, oat flour and sugar, made deliberately to taste 'a little better than a boiled potato' so men "
        "would save it for emergencies. They called it Hershey's Tropical Bar, or worse.")
_p("compo_ration", "compo ration tin", "ration", _UK, (1941, 1950), weight=0.8, volume=0.6,
   desc="A share of a fourteen-man composite pack: steak and kidney pudding, or 'M and V' (meat and veg), hard "
        "tack biscuits, tea, sugar and powdered milk already mixed.")
_p("bully_beef", "tin of bully beef", "ration", _UK + ["usa"], (1900, 1950), weight=0.4, volume=0.3,
   desc="Corned beef from the Argentine. In the desert it came out of the tin as a liquid.")
_p("tushonka", "tin of Lend-Lease pork", "ration", ["ussr"], (1942, 1950), weight=0.5, volume=0.4,
   desc="American stewed pork in a tin with English on it. Red Army men called it 'the second front', since for "
        "two years it was the only one the Allies had opened.")
_p("sukhari", "bag of sukhari", "ration", ["ussr", "poland"], (1900, 1950), weight=0.5, volume=0.4,
   desc="Rye bread dried hard as wood. It keeps for ever, and has to be soaked or broken with a rifle butt.")
_p("eiserne_portion", "Eiserne Portion", "ration", ["germany", "hungary", "romania"], (1900, 1950), weight=0.6,
   volume=0.4, desc="The iron ration: a tin of meat and a bag of hard biscuits, to be eaten only on an officer's "
                    "order, when nothing else has come up for days.")
_p("schokakola", "tin of Scho-Ka-Kola", "chocolate", ["germany"], (1936, 1950), weight=0.15, volume=0.08,
   desc="Dark chocolate with coffee and kola nut in a round red-and-white tin, issued to pilots, tank crews and "
        "paratroopers to keep them awake.")
_p("kanpan", "bag of kanpan", "ration", ["japan"], (1900, 1950), weight=0.3, volume=0.3,
   desc="Hard biscuits with a few sugar sweets (konpeitō) in the bag. By 1944 on the islands there was nothing "
        "else - and then not that.")
_p("galletta", "galletta biscuits", "ration", ["italy"], (1900, 1950), weight=0.3, volume=0.3,
   desc="The Italian army's hard biscuit, with a tin of 'AM' meat: Amministrazione Militare, which the men read "
        "as 'Asinus Mortuus' - dead donkey.")
# ---------------------------------------------------------------- drink
_p("rum_jar", "jar of SRD rum", "flask", _UK, (1900, 1950), weight=1.5, volume=1.0, uses=8,
   desc="A stone jar stencilled SRD - 'Service Rum Diluted', or 'Seldom Reaches Destination'. The dawn tot, "
        "handed out from a spoon by the sergeant.")
_p("vodka", "flask of vodka", "flask", ["ussr", "poland"], (1900, 1950), weight=0.6, volume=0.4, uses=4,
   desc="The 'narkom's hundred grams', the People's Commissar's daily ration for men in the line from 1941. "
        "Before an attack there was more.")
_p("schnapps", "bottle of schnapps", "flask", ["germany", "hungary", "romania"], (1900, 1950), weight=0.8,
   volume=0.5, uses=5, desc="Korn from home, or something distilled in a French farm cellar. Traded, stolen, "
                            "saved for Christmas.")
_p("sake", "bottle of sake", "flask", ["japan"], (1900, 1950), weight=0.8, volume=0.5, uses=5,
   desc="Issued for the Emperor's birthday and before the last attack. On the islands, men drank it from their "
        "canteen cups before walking into the guns.")
_p("wine", "bottle of wine", "flask", ["italy", "france"], (1900, 1950), weight=1.2, volume=0.8, uses=6,
   desc="Rough red from a farmhouse. Every army that came through France or Italy found the cellars.")
# ---------------------------------------------------------------- stimulants
_p("pervitin", "tube of Pervitin", "stimulant", ["germany"], (1938.0, 1950), weight=0.02, volume=0.02, uses=10,
   desc="Methamphetamine, 3 mg a tablet, made by Temmler of Berlin: 'Panzerschokolade'. Millions of tablets went "
        "west with the army in 1940. It keeps you awake for days; then you pay for it.")
_p("benzedrine", "Benzedrine tablets", "stimulant", _UK + ["usa"], (1942.0, 1950), weight=0.02, volume=0.02, uses=8,
   desc="Amphetamine sulphate, issued to bomber crews and to Eighth Army before Alamein. 'Wakey-wakey pills.'")
# ---------------------------------------------------------------- tobacco and fire
_p("makhorka", "pouch of makhorka", "cigarettes", ["ussr"], (1900, 1950), weight=0.1, volume=0.1, uses=20,
   desc="Coarse shag tobacco from the stems, rolled in a strip of newspaper - Pravda burned best, men said, or "
        "Krasnaya Zvezda.")
_p("zippo", "Zippo lighter", "lighter", ["usa"], (1933, 1950), weight=0.06, volume=0.03, glyph="=",
   desc="Black crackle finish for the war, brass underneath where the paint's worn off. It lights in the wind. "
        "Sailors, GIs and war correspondents carried them; Ernie Pyle wrote about them.")
_p("trench_lighter", "trench lighter", "lighter", ["uk", "germany", "france", "ussr", "italy"], (1914, 1950),
   weight=0.05, volume=0.03, glyph="=", desc="Made from a cartridge case, with a wick and a flint: one of the "
                                            "things men made in the long waits.")
# ---------------------------------------------------------------- luck, faith and home
_p("senninbari", "senninbari", "charm", ["japan"], (1937, 1950), weight=0.1, volume=0.1, glyph="[",
   desc="A thousand-stitch belt: a sash with a thousand red knots, each sewn by a different woman on a street "
        "corner at home. Worn round the belly, it turns bullets. Men who had them kept them.")
_p("omamori", "omamori amulet", "charm", ["japan"], (1900, 1950), weight=0.01, volume=0.01,
   desc="A little brocade bag from a shrine, with a prayer inside that must never be taken out.")
_p("yosegaki", "signed Hinomaru flag", "flag", ["japan"], (1937, 1950), weight=0.1, volume=0.1, glyph="[",
   desc="A silk rising-sun flag covered in brushed characters: good wishes and names from family, neighbours "
        "and classmates, 'Eternal good fortune in war'. Carried folded over the heart. The most wanted souvenir "
        "in the Pacific.")
_p("iron_cross", "Iron Cross, 2nd Class", "medal", ["germany"], (1939.7, 1950), weight=0.03, volume=0.01,
   glyph="*", desc="Black iron in a silver frame, the ribbon worn through the second buttonhole. Every American "
                   "in Normandy wanted one to send home.")
_p("medal_ribbon", "campaign ribbons", "medal", _UK + ["usa"], (1900, 1950), weight=0.01, volume=0.01, glyph="*",
   desc="A bar of faded ribbons, each for somewhere he'd rather not have been.")
_p("crucifix", "small crucifix", "rosary", ["poland", "italy", "france", "usa", "hungary", "germany"], (1900, 1950),
   weight=0.02, volume=0.01, desc="Worn on a cord with the identity tags, or sewn inside the tunic by a mother.")
_p("pinup", "pin-up photograph", "photo", ["usa", "uk", "canada", "australia"], (1941, 1950), weight=0.01,
   volume=0.01, glyph="?", color=(225, 215, 180),
   desc="Betty Grable looking back over her shoulder in a white bathing suit, torn out of Yank and creased to "
        "fit a helmet liner.")
_p("wedding_ring", "wedding ring", "ring", ["usa", "uk", "germany", "ussr", "italy", "france", "poland", "japan"],
   (1900, 1950), weight=0.01, volume=0.01, glyph="o", color=(220, 190, 90),
   desc="Gold, worn thin. There's an inscription inside.")
_p("pocket_watch", "pocket watch", "watch", ["uk", "germany", "ussr", "italy", "france", "poland", "hungary"],
   (1900, 1950), weight=0.1, volume=0.05, glyph="o",
   desc="A silver hunter case on a chain, his father's, or his grandfather's. It still keeps time.")
# ---------------------------------------------------------------- reading
_p("stars_and_stripes", "Stars and Stripes", "newspaper", ["usa"], (1942.3, 1950), weight=0.05, volume=0.05,
   glyph="?", color=(225, 215, 180),
   desc="The soldiers' newspaper, printed in Europe by the Army: the war news, the baseball scores, Bill Mauldin's "
        "Willie and Joe.")
_p("yank", "Yank magazine", "newspaper", ["usa"], (1942.4, 1950), weight=0.05, volume=0.05, glyph="?",
   color=(225, 215, 180), desc="'The Army Weekly - by the men, for the men in the service.' And the pin-up in the "
                               "middle.")
_p("signal_mag", "Signal magazine", "newspaper", ["germany", "italy", "hungary"], (1940.3, 1950), weight=0.08,
   volume=0.05, glyph="?", color=(225, 215, 180),
   desc="The Wehrmacht's glossy picture magazine, printed in twenty languages for the occupied countries: colour "
        "photographs of victories that grew fewer.")
_p("krasnaya_zvezda", "Krasnaya Zvezda", "newspaper", ["ussr"], (1924, 1950), weight=0.05, volume=0.05, glyph="?",
   color=(225, 215, 180), desc="Red Star, the army's paper: Ehrenburg's columns, the Sovinformburo communiqués - "
                               "and good for rolling makhorka.")
_p("diary", "pocket diary", "document", ["japan", "germany", "usa", "uk", "ussr", "italy"], (1900, 1950),
   weight=0.05, volume=0.05, glyph="?", color=(225, 215, 180),
   desc="A dead man's diary. Japanese soldiers kept them faithfully and the Allies' translators read them for "
        "unit names, strengths and morale - they were some of the best intelligence of the Pacific war.")
_p("komsomol_card", "Komsomol card", "document", ["ussr"], (1918, 1950), weight=0.01, volume=0.01, glyph="?",
   color=(200, 90, 80), desc="The Young Communist League card, carried in the tunic pocket next to the Red Army book.")
# ---------------------------------------------------------------- kit of his own
_p("shaving_kit", "shaving kit", "shave", ["usa", "uk", "germany", "italy", "france", "canada", "australia",
                                              "newzealand", "poland", "hungary", "romania", "finland", "ussr", "japan"],
   (1900, 1950), weight=0.3, volume=0.2,
   desc="A razor, a brush and a stick of soap in a cloth roll. Some armies insisted on a shave every day, in the "
        "line too: it kept men human, and a gas mask sealed on a shaved face.")
_p("housewife", "'housewife' sewing kit", "sewing", ["usa", "uk", "canada", "australia", "newzealand", "germany"],
   (1900, 1950), weight=0.05, volume=0.05,
   desc="Needles, thread, spare buttons and darning wool in a cloth fold. Pronounced 'hussif'.")
_p("chewing_gum", "pack of chewing gum", "gum", ["usa"], (1900, 1950), weight=0.02, volume=0.02, uses=5,
   desc="Wrigley's, in every ration box, and handed to children in every town from Casablanca to Czechoslovakia.")
