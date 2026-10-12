"""Readable speech on the battlefield, independent of simulation speed and TTS availability."""
from __future__ import annotations

from dataclasses import dataclass
import math
import textwrap
import time

from .constants import VIEW_H, VIEW_W
from .senses import player_can_see_actor


def voice_level(player, x, y, loud, info):
    """The same hearing threshold for written and synthesized speech."""
    own = info.get("own")
    radio = info.get("style") == "radio"
    lx, ly = player.vehicle.pos if player.vehicle is not None else player.pos
    distance = 0.0 if own or radio else math.hypot(x - lx, y - ly)
    deaf = player.body.deaf > 0 or not player.body.conscious
    level = loud - 20 * math.log10(max(1.0, distance))
    gain = 10 ** ((level - 70) / 20.0) * (0.25 if deaf else 1.0)
    if own:
        gain = 0.45 * (0.3 if deaf else 1.0)
    elif radio:
        gain = 0.4 * (0.35 if deaf else 1.0)
    return distance, gain


def event_position(game, event):
    """Queued speech stays at its world position while the tactical array moves underneath it."""
    world = event[7].get("speech_world")
    landscape = game.__dict__.get("landscape")
    if world is not None and landscape is not None and landscape.frame is game.map:
        return world[0] - landscape.origin[0], world[1] - landscape.origin[1]
    return event[2:4]


def _visible(game, actor):
    return (actor is not None and actor.alive and game.map is not None
            and game.map.in_bounds(actor.x, actor.y) and player_can_see_actor(game, actor))


@dataclass
class Caption:
    key: tuple
    actor: object
    text: str
    label: str
    color: tuple
    hold: float
    expires: float | None = None


def remember(game, x, y, loud, info, actor=None):
    """Capture only something the player can hear; unseen voices never get a map anchor."""
    p = game.player
    text = info.get("caption", info.get("text", ""))
    if p is None or not p.body.conscious or not text or voice_level(p, x, y, loud, info)[1] < 0.015:
        return
    radio = info.get("style") == "radio" or isinstance(info.get("sid"), tuple)
    crew = actor is not None and p.vehicle is not None and actor.vehicle is p.vehicle
    known = actor is p or crew or _visible(game, actor)
    if radio:
        label = "Radio"
        anchor = None
    elif actor is p:
        label, anchor = "You", actor
    elif known:
        label, anchor = game.name_of(actor), actor
    else:
        label, anchor = "Nearby voice", None
    color = (190, 215, 245) if radio else (250, 250, 200) if known else (220, 220, 210)
    if known and actor.side != p.side:
        color = (255, 180, 170)
    key = (info.get("sid"), game.turn, text)
    captions = game.__dict__.setdefault("_speech_captions", [])
    # A speaker's newest line replaces their last; a long simulated wait never builds a backlog.
    captions[:] = [c for c in captions if c.key[0] != key[0] and c.key[1] >= game.turn - 30][-7:]
    captions.append(Caption(key, anchor, text, label, color, min(12.0, max(3.5, 1.5 + len(text) / 16))))


def playing(game, info, turn, duration, event=None):
    """Keep an existing caption through the actual clip, including asynchronous synthesis delay."""
    key = (info.get("sid"), turn, info.get("caption", info.get("text", "")))
    if event is not None and not any(c.key == key for c in game.__dict__.get("_speech_captions", ())):
        # Synthesis may finish after the original caption's reading time. Show the actual spoken line again.
        actor = next((a for a in game.actors if a.id == info.get("sid")), None)
        remember(game, *event_position(game, event), event[4], info, actor)
        for caption in game.__dict__.get("_speech_captions", ()):
            if caption.key == (info.get("sid"), game.turn, key[2]):
                caption.key = key
    for caption in game.__dict__.get("_speech_captions", ()):
        if caption.key == key:
            caption.hold = max(caption.hold, duration + 0.5)
            if caption.expires is not None:
                caption.expires = max(caption.expires, time.monotonic() + duration + 0.5)


def _overlap(a, b):
    x, y, w, h = a
    bx, by, bw, bh = b
    return x < bx + bw and x + w > bx and y < by + bh and y + h > by


def _paint(con, rect, lines, color):
    x, y, w, h = rect
    con.draw_rect(x, y, w, h, ord(" "), fg=(20, 20, 20), bg=color)
    for row, line in enumerate(lines):
        con.print(x + 1, y + row, line, fg=(20, 20, 20), bg=color)


def draw(con, game, cam):
    """Anchored bubbles for visible speakers, with optional UI captions for other speech."""
    now = time.monotonic()
    captions = game.__dict__.get("_speech_captions", [])
    captions[:] = [c for c in captions if c.expires is None or c.expires > now]
    p = game.player
    if not p.body.conscious:
        captions.clear()
        return
    w, h = min(VIEW_W, con.width), min(VIEW_H, con.height)
    if w < 8 or h < 4:
        return
    occupied, strips = [], []
    for caption in reversed(captions):
        if caption.expires is None:
            caption.expires = now + caption.hold
        a = caption.actor
        # Crew are heard from your own vehicle, with no claim to seeing their individual positions.
        if a is not None and a.vehicle is None and _visible(game, a) and cam.on_screen(a.x, a.y):
            tx, ty = cam.to_text(a.x, a.y)
            lines = textwrap.wrap(caption.text, min(42, w - 4)) or [""]
            bw, bh = max(map(len, lines)) + 2, len(lines)
            bx = max(0, min(w - bw, tx - bw // 2))
            choices = [(bx, ty - bh - 1, bw, bh), (bx, ty + 2, bw, bh)]
            for rect in choices:
                if rect[1] < 0 or rect[1] + bh > h or any(_overlap(rect, r) for r in occupied):
                    continue
                _paint(con, rect, lines, caption.color)
                above = rect[1] < ty
                tail = (tx, ty - 1 if above else ty + 1, 1, 1)
                if 0 <= tx < w and 0 <= tail[1] < h:
                    con.print(tx, tail[1], "," if above else "'", fg=caption.color)
                    occupied.append(tail)
                occupied.append(rect)
                break
            else:
                strips.append(caption)
        else:
            strips.append(caption)
    if not (game.__dict__.get("_prefs") or {}).get("speech_captions", False):
        return
    # The strip stays inside the map and does not disclose identities or locations of unseen men.
    bottom = h - 2
    for caption in strips[:3]:
        lines = textwrap.wrap(f'{caption.label}: "{caption.text}"', w - 4)
        bh = len(lines)
        rect = (1, bottom - bh, w - 2, bh)
        while rect[1] >= 0 and any(_overlap(rect, r) for r in occupied):
            rect = (rect[0], rect[1] - 1, rect[2], rect[3])
        if rect[1] < 0:
            continue
        _paint(con, rect, lines, caption.color)
        occupied.append(rect)
        bottom = rect[1] - 1
