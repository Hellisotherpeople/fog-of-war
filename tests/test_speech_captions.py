"""Spoken dialogue remains readable without tying the interface to the simulation clock."""
import pickle
from unittest.mock import Mock, patch

import numpy as np
import tcod

from test_command_realism import scene, soldier
from test_smoke import FakeApp
from fow import speech
from fow.audio import Audio, SR
from fow.constants import SCREEN_H, SCREEN_W, VIEW_H, VIEW_W
from fow.entities import Vehicle
from fow.play import PlayState
from fow.render import Camera


def console_text(con):
    return "\n".join("".join(chr(c) for c in row) for row in con.ch.T)


def test_speech_is_readable_after_many_turns_with_sound_disabled_and_then_expires():
    g = scene()
    a = soldier(g, 12, 10)
    app = FakeApp()
    app.settings.update(sound=False, voices=False)
    ps = PlayState(app, g)
    g.map.visible[:] = True
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    a.say("Keep your head down!", g.turn)
    g._collect_speech()
    g.turn += 20                         # moving/reloading can simulate this before the next frame
    with patch("fow.speech.time.monotonic", return_value=100):
        ps.render(con)
    assert "Keep your head down!" in console_text(con)
    with patch("fow.speech.time.monotonic", return_value=102):
        ps.render(con)
    assert "Keep your head down!" in console_text(con)
    with patch("fow.speech.time.monotonic", return_value=120):
        ps.render(con)
    assert "Keep your head down!" not in console_text(con)
    assert "_speech_captions" not in pickle.loads(pickle.dumps(g)).__dict__


def test_delayed_voice_playback_keeps_text_for_the_whole_clip():
    g = scene()
    a = soldier(g, 12, 10)
    g.map.visible[:] = True
    g.audio_events.clear()
    a.say("Watch the road!", g.turn)
    g._collect_speech()
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    with patch("fow.speech.time.monotonic", return_value=100):
        speech.draw(con, g, Camera())
    audio = Audio.__new__(Audio)           # no device, subprocess, model download or cloud dependency
    audio.voice_wait = [(999, g.audio_events[-1])]
    audio.voice_until = []
    bank = Mock()
    bank.request.return_value = None
    audio._bank = Mock(return_value=bank)
    audio.play = Mock()
    with patch("fow.audio.time.time", return_value=101):
        audio._retry_voices(g, g.player)
    assert not audio.play.called and audio.voice_wait
    # A slow first synthesis can outlive the original text completely.
    con.clear()
    with patch("fow.speech.time.monotonic", return_value=110):
        speech.draw(con,g,Camera())
    assert "Watch the road!" not in console_text(con)
    bank.request.return_value = np.zeros(SR * 8, dtype=np.float32)
    with patch("fow.audio.time.time", return_value=111), patch("fow.speech.time.monotonic", return_value=111):
        audio._retry_voices(g, g.player)
    assert audio.play.called
    con.clear()
    with patch("fow.speech.time.monotonic", return_value=118):
        speech.draw(con, g, Camera())
    assert "Watch the road!" in console_text(con)


def test_hidden_and_distant_speakers_do_not_reveal_identity_or_position():
    g = scene()
    hidden = soldier(g, 13, 10, nation="germany")
    far = soldier(g, 60, 50, nation="germany")
    g.map.visible[:] = False
    hidden.say("Halt!", g.turn)
    far.say("Faraway secret", g.turn, tone="talk")
    g._collect_speech()
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    speech.draw(con, g, Camera())
    assert not console_text(con).strip()  # unseen speech has no UI caption by default
    g.__dict__["_prefs"] = {"speech_captions": True}
    speech.draw(con, g, Camera())
    text = console_text(con)
    assert 'Nearby voice: "Halt!"' in text
    assert hidden.name not in text and "Faraway secret" not in text
    assert all(c.actor is None for c in g._speech_captions)
    assert not np.any(con.ch[:VIEW_W, :VIEW_H-5] != ord(" "))


def test_vehicle_crew_and_radio_have_visible_captions():
    g = scene()
    app = FakeApp()
    PlayState(app, g)
    crew = soldier(g, 10, 10)
    v = Vehicle("m4", g.player.side, "usa", 10, 10)
    g.player.vehicle = crew.vehicle = v
    crew.say("Driver, stop!", g.turn)
    g._collect_speech()
    g.msg("HQ: 'Hold your position.'", "radio")
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    speech.draw(con, g, Camera())
    assert not console_text(con).strip()
    app.settings["speech_captions"] = True
    speech.draw(con, g, Camera())
    text = console_text(con)
    assert "Driver, stop!" in text and 'Radio: "Hold your position."' in text
    app.settings["speech_captions"] = False
    con.clear()
    speech.draw(con, g, Camera())
    assert not console_text(con).strip()


def test_effects_queue_cannot_silence_audible_speech_in_a_busy_battle():
    g = scene()
    a = soldier(g,12,10)
    g.audio_events.clear()
    for _ in range(400):
        g.audio('gunfire',50,50)
    a.say('Keep moving!',g.turn)
    g._collect_speech()
    assert len(g.audio_events) == 400
    assert any(ev[0] == 'voice' and ev[7]['text'] == 'Keep moving!' for ev in g.audio_events)


def test_long_bubbles_wrap_at_zoomed_map_edges_without_overwriting_panels():
    g = scene()
    a = soldier(g, 12, 10)
    b = soldier(g, 13, 10)
    g.map.visible[:] = True
    a.say("Stay under cover. The enemy machine gun is watching the road beyond that broken wall.", g.turn)
    b.say("I will cover you!", g.turn)
    g._collect_speech()
    cam = Camera()
    cam.configure(48, 22, 2, 2)
    cam.x0, cam.y0 = 12, 10
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    speech.draw(con, g, cam)
    text = console_text(con)
    assert "I will cover you!" in text  # the bubble that fits stays attached to its speaker
    assert "Stay under cover." not in text  # overflow must not become a UI caption by default
    con.clear()
    g.__dict__["_prefs"] = {"speech_captions": True}
    speech.draw(con, g, cam)
    text = console_text(con)
    assert "Stay under cover." in text and "broken wall." in text and "I will cover you!" in text
    assert np.all(con.ch[VIEW_W:, :] == ord(" "))
    assert np.all(con.ch[:, VIEW_H:] == ord(" "))


def test_text_survives_when_a_translation_has_no_synthesized_voice():
    g = scene()
    a = soldier(g, 12, 10)
    g.map.visible[:] = True
    g.audio_events.clear()
    a.say("The bridge is mined.", g.turn, voice="", tone="talk")
    g._collect_speech()
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    speech.draw(con, g, Camera())
    assert "The bridge is mined." in console_text(con)
    assert not any(e[0] == "voice" for e in g.audio_events)


def test_many_distant_voices_cannot_displace_an_audible_nearby_line():
    g = scene()
    a = soldier(g,12,10)
    g.audio_events.clear()
    a.say("Stay with me!",g.turn)
    g._collect_speech()
    near = g.audio_events[-1]
    far = [("voice",None,1000+i,1000,50,0,g.turn,dict(text="Distant",nation="germany",sid=500+i))
           for i in range(30)]
    audio = Audio.__new__(Audio)
    audio.voice_wait = []
    audio._retry_voices = Mock()
    audio._voice_events(g,g.player,[near]+far)
    assert [ev[7]['text'] for _,ev in audio.voice_wait] == ["Stay with me!"]


def test_pending_voice_keeps_its_world_position_across_boundary_and_back():
    from test_streaming import world, reframe
    g,ps,landscape = world()
    g.audio_events.clear()
    g.audio('voice',g.player.x+2,g.player.y,66,extra=dict(text='Over here!',sid=123,nation='usa'))
    queued = g.audio_events[-1]       # the audio worker may already hold this tuple
    original = queued[7]['speech_world']
    for step in (30,-30):
        reframe(g,landscape,step,0)
        point = speech.event_position(g,queued)
        assert landscape.world_pos(*point) == original
        assert landscape.world_pos(*g.audio_events[-1][2:4]) == original
    assert speech.voice_level(g.player,*point,66,queued[7])[1] >= .015


def test_live_tts_line_is_promoted_ahead_of_background_warming(tmp_path):
    from fow.voice import VoiceBank, Speaker
    with patch('fow.voice.VoiceBank.WORKERS',0), patch('fow.voice.CACHE_DIR',str(tmp_path)), \
         patch('fow.voice.find_synth',return_value=Mock(name='test')), patch('fow.neural_voice.available',return_value=False):
        bank = VoiceBank(engine='system')
    speaker = Speaker('test',0,1.,False,'en_US')
    bank.request(speaker,'Watch the road!','shout',warm=True)
    bank.request(speaker,'Watch the road!','shout')
    assert bank.jobs.get_nowait()[0] == 0    # formerly remained behind every queued background line
