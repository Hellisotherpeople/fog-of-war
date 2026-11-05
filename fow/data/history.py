"""The historical places a sector may hold, and what happened there.

Kept factual and plain, and kept to what the battle's ground can honestly carry.  A site is a
landmark: a burnt village, a ravine, a ruin, a stone marker.  Looking at the marker shows the note.
Germany is named where German troops did the killing, and the Waffen-SS is named where it was theirs -
without turning the game into a museum label.
"""
from __future__ import annotations

SITES = {
    "bocage44": [dict(name="the burnt village of Oradour", kind="burnt_village", weight=2.0,
                      note="On 10 June 1944 men of the SS division Das Reich drove the people of Oradour-sur-Glane "
                           "into the church and the barns and killed 642 of them, nearly the whole village. It was "
                           "never rebuilt; the walls were left standing as they fell.")],
    "barbarossa41": [dict(name="the ravine at Babi Yar", kind="ravine", weight=1.5,
                          note="On 29 and 30 September 1941 SS and police shot 33,771 Jews of Kiev in this ravine "
                               "in two days, at the edge of the city. The ground went on being used for mass "
                               "shootings for another two years.")],
    "moscow41": [dict(name="the village of Petrishchevo", kind="marker_village", weight=1.2,
                      note="In November 1941 the partisans burned the German sheds and stables here. The Germans "
                           "caught an eighteen-year-old saboteur, Zoya Kosmodemyanskaya, tortured her, and hanged "
                           "her in the square. She was made a Hero of the Soviet Union.")],
    "stalingrad42": [dict(name="Pavlov's House", kind="ruin_marker", weight=1.2,
                          note="A four-storey flats block held for fifty-eight days by Sergeant Yakov Pavlov's "
                               "small group. The defenders broke through the wall to the Volga and were supplied "
                               "across it. The building was rebuilt after the war; the ridge of rubble that ran "
                               "behind it was called the 'Railwaymen's House' for the men who died there.")],
    "berlin45": [dict(name="the Reichstag", kind="great_ruin", weight=1.5,
                      note="The old parliament building: burned out in 1933, and stormed on 30 April 1945. Men of "
                           "the Red Army fought from room to room for days and raised the red flag over the "
                           "dome, while the fighting went on in the streets below.")],
    "kohima44": [dict(name="the garrison hill cemetery", kind="cemetery_marker", weight=1.2,
                      note="On the tennis court below the deputy commissioner's bungalow the 2nd Division held "
                           "out until relieved in April 1944. The dead of both armies were buried on the slope "
                           "beside it; the stone cross there carries the Kohima Epitaph.")],
    "poland39": [dict(name="the September memorial", kind="marker_village", weight=1.0,
                      note="The first campaign was over in five weeks. The stone lists men killed in the fighting "
                           "of 1939; by 1944 another list would have been needed.")],
}
