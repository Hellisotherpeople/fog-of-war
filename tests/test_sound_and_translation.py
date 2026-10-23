"""The mixer, recorded packs, the music and 'your side speaks English' work without a sound device."""
import json
import os
from types import SimpleNamespace as NS

import numpy as np
import pytest

from fow import translate
from fow.audio import Bank, _filter, _wrap_add
from fow.mixer import BLOCK, LIMIT, Mixer, SR


@pytest.fixture
def english_side():
    """The option on for the axis, and off again afterwards (it is a module global)."""
    translate.ACTIVE_SIDE = "axis"
    yield
    translate.ACTIVE_SIDE = None


@pytest.fixture(scope="module")
def bank():
    return Bank()


def drain(m, blocks=400):
    out = []
    for _ in range(blocks):
        b = m.render(BLOCK)
        if b is None:
            break
        out.append(b)
    return np.concatenate(out) if out else np.zeros((0, 2), np.float32)


# ---------------------------------------------------------------- the mixer
def test_mixer_limits_a_pileup_and_falls_silent():
    m = Mixer(start=False)
    m.set_master(1.0)
    tone = np.sin(2 * np.pi * 440 * np.arange(SR // 2) / SR).astype(np.float32)
    for i in range(6):                                   # six loud sounds at once: far over full scale
        m.play(tone, 1.0, 1.0, delay=i * .01)
    x = drain(m)
    assert len(x) and np.abs(x).max() <= LIMIT + 1e-3
    assert m.render(BLOCK) is None and not m.voices      # nothing left: the thread can idle


def test_mixer_sounds_ease_in_and_out_without_a_click():
    m = Mixer(start=False)
    m.master = m.master_target = 1.0
    m.play(np.full(SR // 10, .5, np.float32), 1.0, 1.0)  # a hard-edged block of DC: the worst case
    x = drain(m)[:, 0]
    assert abs(x[0]) < .05 and abs(x[x != 0][-1]) < .05


def test_mixer_stop_fades_everything_and_drops_the_loops():
    m = Mixer(start=False)
    m.set_master(1.0)
    m.play(np.ones(SR * 5, np.float32) * .2, 1, 1)
    m.loop("wind", np.ones(SR, np.float32) * .2, .5)
    drain(m, 20)
    m.stop_all()
    tail = drain(m, 200)
    assert len(tail) < SR // 2                          # gone within half a second
    assert not m.voices and all(lp.target == 0 for lp in m.loops.values())


def test_mixer_drops_the_quietest_sound_when_too_many_play():
    from fow.mixer import MAX_VOICES
    m = Mixer(start=False)
    m.set_master(1.0)
    long = np.ones(SR * 2, np.float32) * .01
    m.play(long, .01, .01)                              # the quietest
    drain(m, 1)
    for _ in range(MAX_VOICES):
        m.play(long, .5, .5)
    drain(m, 4)
    assert all(max(v.gl, v.gr) > .01 for v in m.voices)


# ---------------------------------------------------------------- the synthesised bank
def test_one_shot_filter_does_not_wrap_its_ringing_round_to_the_end():
    x = np.zeros(SR // 2, np.float32)
    x[100] = 1.0                                        # a click near the start
    y = _filter(x, hi=500)
    assert np.abs(y[-200:]).max() < 1e-3                # nothing ticks again as the clip finishes


def test_wrap_add_carries_the_overhang_round_to_the_start():
    loop = np.zeros(10, np.float32)
    _wrap_add(loop, np.ones(4, np.float32), 8)
    assert loop.tolist() == [1, 1, 0, 0, 0, 0, 0, 0, 1, 1]


@pytest.mark.parametrize("name", ["sonar", "depth_charge", "klaxon", "flak", "stuka", "torpedo", "naval_gun",
                                  "telephone", "flak_far", "stuka_far", "naval_gun_far", "depth_charge_far"])
def test_new_synthesised_sounds_exist_and_are_finite(bank, name):
    x = bank.get(name)
    assert x is not None and len(x) > SR // 4 and np.isfinite(x).all() and 0 < np.abs(x).max() <= 1


@pytest.mark.parametrize("kind,extra", [("stuka", None), ("klaxon", None), ("sonar", None), ("torpedo", None),
                                        ("depth_charge", None), ("naval_gun", None), ("telephone", None),
                                        ("explosion", "flak")])
def test_game_sound_kinds_reach_a_sound(bank, kind, extra):
    from fow.audio import Audio
    a = Audio.__new__(Audio)                             # no device
    a.bank = bank
    assert a._pick(kind, None, 80, False, extra) is not None


# ---------------------------------------------------------------- recorded packs
def write_pack(root, name="testpack"):
    import soundfile as sf
    folder = root / name
    folder.mkdir(parents=True)
    t = np.arange(int(SR * .6)) / SR
    burst = np.zeros_like(t, dtype=np.float32)
    onsets = [int(SR * s) for s in (.05, .15, .25)]
    for o in onsets:
        burst[o:o + 800] += np.sin(2 * np.pi * 900 * t[:800]) * np.exp(-t[:800] * 60)
    sf.write(folder / "mg42_1.ogg", burst * .8, SR, format="OGG", subtype="VORBIS")
    sf.write(folder / "expl_big_1.ogg", np.sin(2 * np.pi * 60 * t).astype(np.float32) * .8, SR,
             format="OGG", subtype="VORBIS")
    (folder / "pack.json").write_text(json.dumps({"name": name, "slots": {
        "mg42": [{"file": "mg42_1.ogg", "onsets": onsets}], "expl_big": [{"file": "expl_big_1.ogg"}]}}))
    return name


def test_pack_bank_plays_recordings_and_synthesises_the_rest(tmp_path, monkeypatch, bank):
    pytest.importorskip("soundfile")
    from fow import soundpack
    from fow.data.items import ITEMS
    monkeypatch.setattr(soundpack, "ROOT", str(tmp_path))
    name = write_pack(tmp_path)
    assert soundpack.packs() == [name]
    pb = soundpack.PackBank(name, bank)
    assert pb.get("expl_big") is pb.rec["expl_big"][0]
    assert pb.get("klaxon") is not None                  # not in the pack: still synthesised
    one = pb.gun("mg42", ITEMS["mg42"], False, 1)
    ten = pb.gun("mg42", ITEMS["mg42"], False, 10)
    assert len(ten) > 3 * len(one) * .5 and np.abs(ten).max() <= 1
    assert pb.gun("kar98k", ITEMS["kar98k"], False, 1) is None   # no rifle recording: the synth's
    assert pb.gun("mg34", ITEMS["mg34"], True, 5) is not None    # its family's recording, muffled


# ---------------------------------------------------------------- music
def write_music(root, tracks):
    import soundfile as sf
    root.mkdir(parents=True, exist_ok=True)
    for tr in tracks:
        sf.write(root / tr["file"], np.zeros(SR * 20, np.float32), SR, format="OGG", subtype="VORBIS")
    (root / "music.json").write_text(json.dumps({"tracks": tracks}))


def director(tmp_path, monkeypatch, tracks, mode="all"):
    pytest.importorskip("soundfile")
    from fow import music
    monkeypatch.setattr(music, "ROOT", str(tmp_path))
    write_music(tmp_path, tracks)
    started = []
    audio = NS(settings={"music": mode, "vol_music": .5}, enabled=True,
               mixer=NS(add_music=started.append))
    return music.MusicDirector(audio), started


def test_briefing_music_is_the_players_own_army(tmp_path, monkeypatch):
    d, started = director(tmp_path, monkeypatch, [
        dict(file="lili.ogg", nations=["germany"], moods=["march"]),
        dict(file="tipperary.ogg", nations=["uk"], moods=["march"])])
    d.update("briefing", "germany")
    assert d.track.file.endswith("lili.ogg") and len(started) == 1


def test_random_army_resolving_does_not_restart_the_briefing_music(tmp_path, monkeypatch):
    d, started = director(tmp_path, monkeypatch, [dict(file="any.ogg", moods=["anthem"])])
    d.update("briefing", None)                           # generating: the random army isn't chosen yet
    d.update("briefing", "germany")                      # the briefing: now it is
    assert len(started) == 1 and d.source is started[0]


def test_music_never_starts_in_a_fight_and_stops_when_shooting_starts(tmp_path, monkeypatch):
    import time
    d, started = director(tmp_path, monkeypatch, [dict(file="quiet.ogg", moods=["quiet"])])
    d.update("play", "usa", intensity=0)
    d.rest_until = 0
    d.calm_since = time.time() - 100
    d.update("play", "usa", intensity=0)
    assert d.source is not None
    d.update("play", "usa", intensity=.5)                # shooting
    assert d.source is None and started[0]._stopping


def test_menus_only_music_is_silent_in_play(tmp_path, monkeypatch):
    d, started = director(tmp_path, monkeypatch, [dict(file="t.ogg", moods=["title", "quiet"])], mode="title")
    d.update("title")
    assert d.source is not None
    d.update("play", "usa")
    assert d.source is None


# ---------------------------------------------------------------- your side speaks English
def test_every_translated_line_is_one_the_game_says():
    """A key here that matches nothing is a typo: that line would silently stay untranslated."""
    from fow.data import ranks as R
    from fow.data.banter import BANTER
    from fow.data.chatter import C
    from fow.data.nations import NATIONS
    from fow.data.phrases import P, lang
    from fow.data.translations import EN
    for lg, table in EN.items():
        said = set()
        for t in (P, C):
            for by in t.values():
                said.update(by.get(lg) or [])
        for n, d in NATIONS.items():
            if lang(n) == lg:
                for lines in d["shouts"].values():
                    said.update(lines)
                said.update(R.ACK.get(n, []))
                said.update(R.REFUSE.get(n, []))
        for pair in BANTER.get(lg) or []:
            said.update(pair)
        assert set(table) <= said, (lg, sorted(set(table) - said)[:5])
        assert said <= set(table), (lg, sorted(said - set(table))[:5])


@pytest.mark.parametrize("nation,native,english", [
    ("germany", "Handgranate!", "Grenade!"),
    ("germany", "Jawohl, Herr Leutnant!", "Yes, Herr Leutnant!"),
    ("china", "Wǒ de tóu! Wǒ de tóu!", "My head! My head!"),
    ("usa", "Grenade!", None),
])
def test_english_for_native_lines(nation, native, english):
    assert translate.english(nation, native) == english


def test_own_side_speaks_english_and_the_enemy_does_not(english_side):
    from fow.entities import Actor
    ger = Actor("germany", "rifleman", 3, "Hans Weber")
    sov = Actor("ussr", "rifleman", 3, "Ivan Petrov")
    ger.say("Handgranate!", 1)
    sov.say("Granata!", 1)
    assert ger.shout[0] == "Grenade!" and ger.spoken[0] == "Grenade!" and ger.spoken[3] is True
    assert sov.shout[0] == "Granata!" and sov.spoken[3] is False
    assert translate.in_english(ger) and not translate.in_english(sov)


def test_a_hum_is_not_read_out_in_english(english_side):
    from fow.entities import Actor
    ger = Actor("germany", "rifleman", 3, "Hans Weber")
    ger.say("♪ ...", 1, voice="")
    assert ger.shout[0] == "♪ ..." and ger.spoken[0] == "" and ger.spoken[3] is False


@pytest.mark.parametrize("lg,english,accented", [
    ("de", "ðɪs ɪz ðə wɜːld", "zɪs ɪs zə vøːlt"),
    ("hu", "ʌp", "ɒp"),                                 # one pass: ʌ->ɒ is not then turned into o
    ("de", "hɚ", "hɐ"),
])
def test_accent_swaps_each_sound_once(lg, english, accented):
    from fow.neural_voice import accented as acc
    assert acc(english, lg) == accented


def test_accented_english_uses_only_sounds_each_voice_knows():
    """Every English line, accented, must be sayable by each language's installed Piper voice."""
    from fow.neural_voice import ACCENTS, accented
    root = os.path.expanduser("~/.fogofwar/piper")
    PV = pytest.importorskip("piper.voice")
    from fow.data.translations import EN
    models = {lg: next((f for f in sorted(os.listdir(root)) if f.startswith(lg + "_") and f.endswith(".onnx")),
                       None) for lg in ACCENTS} if os.path.isdir(root) else {}
    models = {lg: f for lg, f in models.items() if f}
    if not models:
        pytest.skip("no Piper voices downloaded")
    v = PV.PiperVoice.load(os.path.join(root, next(iter(models.values()))))
    ph = PV.EspeakPhonemizer(v.espeak_data_dir)
    text = " ".join(sorted({e for t in EN.values() for e in t.values()}))
    src = "".join("".join(s) for s in ph.phonemize("en-us", text))
    for lg, f in models.items():
        with open(os.path.join(root, f + ".json"), encoding="utf-8") as fh:
            known = json.load(fh)["phoneme_id_map"]
        missing = {c for c in accented(src, lg) if c not in known} - {"̩"}   # (syllabic mark: dropped)
        assert not missing, (lg, sorted(missing))
