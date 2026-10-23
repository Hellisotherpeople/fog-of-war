"""Music: real recordings of the period's music (assets/music, all public domain - see its CREDITS.md).

What plays depends on where you are:
  title       the menus: something with the war in it
  briefing    your army's own music while the battle is generated and you read your orders
  play        now and then, in a quiet hour - never in a fight: it fades the moment the shooting starts
  death       the lament your army plays for its dead
  memorial    the fallen
The Options screen sets the volume, and whether music plays only in the menus, everywhere, or never.
"""
from __future__ import annotations

import json
import os
import random
import time

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")


class Track:
    __slots__ = ("file", "title", "nations", "sides", "moods", "gain", "credit")

    def __init__(self, d):
        self.file = os.path.join(ROOT, d["file"])
        self.title = d.get("title", d["file"])
        self.nations = set(d.get("nations", []))
        self.sides = set(d.get("sides", []))
        self.moods = set(d.get("moods", []))
        self.gain = float(d.get("gain", 1.0))
        self.credit = d.get("credit", "")


def library():
    try:
        with open(os.path.join(ROOT, "music.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [Track(d) for d in data.get("tracks", []) if os.path.exists(os.path.join(ROOT, d.get("file", "")))]


def _side_of(nation):
    from .data.nations import NATIONS
    return NATIONS.get(nation, {}).get("side")


class MusicDirector:
    FADE_OUT = {"title": 3.0, "briefing": 3.0, "play": 2.5, "death": 4.0, "memorial": 3.0}

    def __init__(self, audio):
        self.audio = audio
        self.tracks = library()
        self.ctx = None
        self.nation = None
        self.source = None
        self.track = None
        self.recent: list = []
        self.rest_until = 0.0            # in play: no music before this (one piece now and then, not wallpaper)
        self.calm_since = time.time()
        self.played_once = set()         # (context, nation) for the one-shot contexts
        self.ok = self._decoder_ok()

    @staticmethod
    def _decoder_ok():
        try:
            import soundfile  # noqa: F401
            return True
        except Exception:
            return False

    def available(self):
        return self.ok and bool(self.tracks)

    # ------------------------------------------------------------ choosing
    def _pool(self, ctx, nation):
        side = _side_of(nation) if nation else None
        want = {"title": ("title",), "briefing": ("anthem", "march"), "play": ("quiet", "march", "anthem"),
                "death": ("lament",), "memorial": ("memorial", "lament")}.get(ctx, ())
        for strict in (True, False):
            pool = []
            for t in self.tracks:
                if not t.moods.intersection(want):
                    continue
                if ctx in ("title", "memorial") or not strict:
                    if ctx in ("title", "memorial") or not t.nations or nation in t.nations or side in t.sides:
                        pool.append(t)
                elif nation in t.nations:
                    pool.append(t)
            if pool:
                return pool
            if ctx in ("death", "briefing"):
                # no lament of his own army's: the general ones (no nation), then a side's
                pool = [t for t in self.tracks if t.moods.intersection(want) and (not t.nations or side in t.sides)]
                if pool:
                    return pool
        return []

    def _pick(self, ctx, nation):
        pool = self._pool(ctx, nation)
        if not pool:
            return None
        fresh = [t for t in pool if t.file not in self.recent] or pool
        t = random.choice(fresh)
        self.recent = (self.recent + [t.file])[-max(1, min(5, len(pool) - 1)):]
        return t

    # ------------------------------------------------------------ playing
    def _volume(self):
        try:
            return max(0.0, min(1.5, float(self.audio.settings.get("vol_music", 0.55))))
        except (TypeError, ValueError):
            return 0.55

    def _start(self, track, fade_in=2.5):
        from .mixer import MusicSource
        self.track = track
        self.source = MusicSource(track.file, gain=self._volume() * track.gain, fade_in=fade_in)
        self.audio.mixer.add_music(self.source)

    def _stop(self, fade=2.5):
        if self.source is not None:
            self.source.stop(fade)
        self.source = None
        self.track = None

    def allowed(self, ctx):
        mode = self.audio.settings.get("music", "all")
        if mode == "off" or not self.audio.enabled:
            return False
        return mode == "all" or ctx != "play"

    def update(self, ctx, nation=None, intensity=0.0):
        """Called every frame with what's on screen."""
        if not self.available():
            return
        now = time.time()
        if intensity > 0.08:
            self.calm_since = now
        if not self.allowed(ctx):
            self._stop(1.5)
            self.ctx = ctx
            return
        # (a random army is only known once the battle is made: None -> "germany" isn't a change of mind)
        changed = ctx != self.ctx or (nation != self.nation and nation is not None and self.nation is not None
                                      and ctx in ("briefing", "death"))
        if nation is not None:
            self.nation = nation
        if changed:
            prev = self.ctx
            self.ctx = ctx
            keep = prev in ("title", "briefing") and ctx in ("title", "briefing") and self.source is not None and \
                (ctx == "title" or self.track is not None and nation in self.track.nations)
            if not keep:
                self._stop(self.FADE_OUT.get(prev, 2.5))
            if ctx == "play":
                self.rest_until = max(self.rest_until, now + random.uniform(90, 200))
        if self.source is not None:
            self.source.set_gain(self._volume() * (self.track.gain if self.track else 1.0))
            if ctx == "play" and now - self.calm_since < 1.0:
                self._stop(1.2)                              # the shooting starts: the music goes at once
                self.rest_until = now + random.uniform(240, 420)
                return
            if self.source.finished():
                self.source = None
                self.track = None
                if ctx == "play":
                    self.rest_until = now + random.uniform(300, 720)
                elif ctx in ("death", "memorial"):
                    self.played_once.add((ctx, nation))
            return
        # nothing playing: what next?
        if ctx in ("death", "memorial") and (ctx, nation) in self.played_once:
            return
        if ctx == "play":
            if now < self.rest_until or now - self.calm_since < 75:
                return
        t = self._pick(ctx, nation)
        if t is not None:
            self._start(t, fade_in=4.0 if ctx == "play" else 2.0)

    def now_playing(self):
        return self.track.title if self.track is not None and self.source is not None else None
