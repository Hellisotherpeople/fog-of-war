#!/usr/bin/env python3
"""Capture a 28-second Kursk battle as a native-upload LinkedIn MP4.

    .venv/bin/python tools/make_linkedin_video.py

Requires ffmpeg. Uses the game's sprite renderer, four animation phases and
procedural sound bank. The observer camera lifts rendering fog and omits the
player's HUD/condition vignette; combat, terrain damage and AI are simulated.
The camera soldier is protected, as in make_media.py. Saves and settings live
in a temporary FOW_HOME. No external footage, music or image assets are used.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WIDTH, HEIGHT, FPS = 1080, 1350, 30
MAP_HEIGHT, MAP_TOP = 1000, 170
FRAMES_PER_TURN = 6
DURATION = 28
PAPER = (235, 231, 214)
MUTED = (166, 177, 158)
AMBER = (225, 184, 86)
BG = (15, 23, 19)
SHOTS = [
    dict(name="CONTACT", start=8, end=42, a=(76, 88), b=(79, 81),
         title="THE WAR DOESN'T WAIT.",
         sub="One soldier. A whole battlefield moving around you."),
    dict(name="ARMOUR", start=43, end=77, a=(135, 70), b=(130, 62),
         title="ARMOUR MEETS INFANTRY.",
         sub="Crews and squads fight under their own orders."),
    dict(name="BARRAGE", start=78, end=112, a=(129, 60), b=(127, 57),
         title="THE GROUND DOESN'T SURVIVE.",
         sub="Shells crater the ground. Buildings become rubble."),
    dict(name="ADVANCE", start=113, end=147, a=(81, 70), b=(84, 63),
         title="ONE TURN. ONE SECOND.",
         sub="A Second World War roguelike. The battle goes on."),
]


def fonts():
    from PIL import ImageFont
    # Bundled fonts make the command portable; condensed display face on macOS.
    display = Path("/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf")
    if not display.exists():
        display = ROOT / "assets/DejaVuSansMono-Bold.ttf"
    regular = ROOT / "assets/DejaVuSansMono.ttf"
    return {"brand": ImageFont.truetype(str(display), 74),
            "heading": ImageFont.truetype(str(display), 47),
            "sub": ImageFont.truetype(str(regular), 23),
            "meta": ImageFont.truetype(str(regular), 20),
            "small": ImageFont.truetype(str(regular), 17)}


def fit_text(draw, xy, value, font, fill, width):
    # Avoid clipping when the bundled fallback is wider than the display font.
    from PIL import ImageFont
    while draw.textlength(value, font=font) > width:
        font = ImageFont.truetype(font.path, font.size - 1)
    draw.text(xy, value, font=font, fill=fill)


def compose(battle, index, frame, fnt):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (WIDTH, HEIGHT), BG)
    im.paste(battle, (0, MAP_TOP))
    d = ImageDraw.Draw(im)
    # Restrained field-report typography, with mobile-safe text margins.
    d.rectangle((64, 38, 70, 105), fill=AMBER)
    d.text((90, 35), "FOG OF WAR", font=fnt["brand"], fill=PAPER)
    d.text((798, 51), "WORLD WAR II", font=fnt["small"], fill=MUTED)
    d.text((798, 77), "ROGUELIKE", font=fnt["small"], fill=MUTED)
    d.text((64, 127), "KURSK / JULY 1943", font=fnt["meta"], fill=MUTED)
    label = f"0{index + 1} / {SHOTS[index]['name']}"
    d.text((WIDTH - 64 - d.textlength(label, font=fnt["meta"]), 127),
           label, font=fnt["meta"], fill=AMBER)
    d.line((0, MAP_TOP - 1, WIDTH, MAP_TOP - 1), fill=(62, 74, 59), width=2)
    d.rectangle((0, MAP_TOP + MAP_HEIGHT, WIDTH, HEIGHT), fill=BG)
    shot = SHOTS[index]
    fit_text(d, (64, 1190), shot["title"], fnt["heading"], PAPER, 952)
    sub = shot["sub"]
    if frame >= 25 * FPS:
        sub = "github.com/Hellisotherpeople/fog-of-war"
    fit_text(d, (64, 1252), sub, fnt["sub"], MUTED, 952)
    # A small disclosure distinguishes the editorial camera from player sight.
    d.text((64, 1304), "IN-GAME CAPTURE / OBSERVER VIEW / 5x SPEED",
           font=fnt["small"], fill=(129, 144, 128))
    for i in range(4):
        x = 822 + i * 48
        d.rectangle((x, 1310, x + 32, 1313), fill=AMBER if i <= index else (57, 70, 58))
    return im


class Capture:
    """Render the actual battlefield layers to a portrait-friendly viewport."""

    def __init__(self):
        import tcod
        import tcod.render
        from fow.render import Camera
        from fow.sprites import SpriteBank
        self.px = 36
        self.bank = SpriteBank()
        tileset = self.bank.build(self.px)
        self.ctx = tcod.context.new(width=WIDTH, height=MAP_HEIGHT, tileset=tileset)
        self.renderer = self.ctx.sdl_renderer
        atlas = tcod.render.SDLTilesetAtlas(self.renderer, tileset)
        self.renders = [tcod.render.SDLConsoleRender(atlas) for _ in range(8)]
        self.cam = Camera()
        self.cam.configure(math.ceil(WIDTH / self.px) + 1,
                           math.ceil(MAP_HEIGHT / self.px) + 1)
        self.ui = SimpleNamespace(anim=4, mode="normal", cursor=None,
                                  hover=None, travel_dest=None)

    def frame(self, game, center, phase):
        from PIL import Image
        from fow.render_sprites import draw_sprite_layers
        self.cam.set_float(center[0] - WIDTH / (2 * self.px),
                           center[1] - MAP_HEIGHT / (2 * self.px))
        self.ui.anim = 4 - phase
        game.map.visible[:] = True
        game.map.explored[:] = True
        layers = draw_sprite_layers(self.bank, game, self.cam, phase, self.ui)
        dx, dy = self.cam.frac()
        r = self.renderer
        r.draw_color = (0, 0, 0, 255)
        r.clear()
        # The last layer is the player's injury vignette; the observer has no HUD.
        for i, layer in enumerate(layers[:-1]):
            r.copy(self.renders[i].render(layer),
                   dest=(-round(dx * self.px), -round(dy * self.px),
                         self.cam.vw * self.px, self.cam.vh * self.px))
        r.present()
        return Image.fromarray(r.read_pixels()[:, :, :3])


def make_audio(events, target):
    """Mix real game sound events from the observer camera's position."""
    import numpy as np
    from fow.audio import Audio, Bank, SR
    random.seed(701)
    bank = Bank(seed=701)
    picker = SimpleNamespace(bank=bank)
    n = DURATION * SR
    out = np.zeros((n, 2), np.float32)
    # The same subdued battle and wind ambience heard in the game.
    for key, gain in (("battle", 0.035), ("wind", 0.014)):
        loop = bank.loops[key]
        mono = np.resize(loop, n) * gain
        out += mono[:, None]
    rng = random.Random(31)
    last_engine = -5.0
    mixed = 0
    for row in events:
        cx, cy = row["camera"]
        candidates = []
        for kind, weapon, x, y, loud, power, turn, extra in row["events"]:
            if kind in ("voice", "shout", "footsteps", "radio"):
                continue
            dist = math.hypot(x - cx, y - cy)
            if dist > 52:
                continue
            amp = min(0.38, 10 ** ((loud - 20 * math.log10(max(5, dist)) - 76) / 20))
            if amp < 0.008:
                continue
            priority = amp * (2 if kind in ("explosion", "cannon") else 1)
            candidates.append((priority, amp, dist, kind, weapon, x, power, extra))
        for _, amp, dist, kind, weapon, x, power, extra in sorted(candidates, reverse=True)[:4]:
            t = row["time"] + rng.uniform(0, 0.025)
            if kind == "engine":
                if t - last_engine < 1.5:
                    continue
                last_engine = t
            snd = Audio._pick(picker, kind, weapon, power, dist > 28, extra)
            if snd is None:
                continue
            start = int(t * SR)
            count = min(len(snd), n - start)
            if count <= 0:
                continue
            pan = max(-0.85, min(0.85, (x - cx) / 18))
            gains = np.array([math.cos((pan + 1) * math.pi / 4),
                              math.sin((pan + 1) * math.pi / 4)]) * amp
            out[start:start + count] += snd[:count, None] * gains
            mixed += 1
    # Leave headroom for loudness normalization; short fades prevent clicks.
    out = np.tanh(out * 0.9)
    fade = int(SR * 0.3)
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
    return mixed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/media/linkedin")
    args = parser.parse_args()
    if shutil.which("ffmpeg") is None:
        parser.error("ffmpeg is required")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fow_linkedin_") as work:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["FOW_HOME"] = str(Path(work) / "game-home")
        from fow.game import Game
        import fow.render_sprites as sprite_renderer
        from tools.make_media import _daylight, _immortal
        sprite_renderer.player_can_see_actor = lambda game, actor: True
        g = Game("kursk43", "ussr", seed=5, setup={"battlefield": "standard"})
        _daylight(g)
        _immortal(g.player)
        cap = Capture()
        fnt = fonts()
        silent = Path(work) / "picture.mp4"
        movie = output / "fog-of-war-kursk-linkedin.mp4"
        sound = Path(work) / "sound.wav"
        encoder = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{WIDTH}x{HEIGHT}",
            "-framerate", str(FPS), "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-level:v", "4.1", "-g", "60",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,setsar=1",
            str(silent)], stdin=subprocess.PIPE)
        rows, frame, hero, hero_score = [], 0, None, -1
        stills = []
        try:
            for turn in range(1, SHOTS[-1]["end"] + 1):
                g.effects = []
                g.audio_events = []
                g.player.moves = 0
                g.world_turn()
                if turn < SHOTS[0]["start"]:
                    continue
                index = next(i for i, shot in enumerate(SHOTS) if shot["start"] <= turn <= shot["end"])
                shot = SHOTS[index]
                if turn == shot["start"]:
                    print(f"Capturing {index + 1}/4: {shot['name']}", flush=True)
                frac = (turn - shot["start"]) / (shot["end"] - shot["start"] + 1)
                camera = [shot["a"][i] + frac * (shot["b"][i] - shot["a"][i]) for i in (0, 1)]
                rows.append({"time": frame / FPS, "turn": g.turn, "camera": camera,
                             "events": list(g.audio_events)})
                for subframe in range(FRAMES_PER_TURN):
                    frac = (turn - shot["start"] + subframe / FRAMES_PER_TURN) / (shot["end"] - shot["start"] + 1)
                    camera = [shot["a"][i] + frac * (shot["b"][i] - shot["a"][i]) for i in (0, 1)]
                    phase = min(3, subframe * 4 // FRAMES_PER_TURN)
                    battle = cap.frame(g, camera, phase)
                    picture = compose(battle, index, frame, fnt)
                    encoder.stdin.write(picture.tobytes())
                    if frame % (FPS * 2) == FPS:
                        stills.append(picture.resize((270, 338)))
                    if subframe == 2:
                        score = sum(e.get("r", 1) for e in g.effects if e["kind"] == "explosion"
                                    and abs(e["x"] - camera[0]) < 10 and abs(e["y"] - camera[1]) < 10)
                        if score > hero_score:
                            hero_score, hero = score, picture.copy()
                    frame += 1
        finally:
            encoder.stdin.close()
            encoder.wait()
            cap.ctx.close()
        if encoder.returncode:
            raise RuntimeError(f"ffmpeg picture encode failed: {encoder.returncode}")
        assert frame == DURATION * FPS, frame
        print("Mixing game sound effects...", flush=True)
        sound_count = make_audio(rows, sound)
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(silent), "-i", str(sound), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-t", str(DURATION),
            "-movflags", "+faststart", "-metadata", "title=Fog of War | Kursk under fire",
            "-metadata", "comment=In-game observer capture; fog lifted; 5x simulation speed.",
            str(movie)], check=True)
        hero.save(output / "fog-of-war-kursk-cover.jpg", quality=94)
        from PIL import Image
        contact = Image.new("RGB", (270 * 4, 338 * math.ceil(len(stills) / 4)), BG)
        for i, still in enumerate(stills):
            contact.paste(still, (i % 4 * 270, i // 4 * 338))
        contact.save(output / "contact-sheet.jpg", quality=90)
        metadata = dict(duration_seconds=DURATION, frames=frame, fps=FPS, width=WIDTH, height=HEIGHT,
                        theatre="kursk43", nation="ussr", seed=5, simulation_speed=5,
                        sound_events_mixed=sound_count, shots=SHOTS,
                        capture="Native sprite layers and procedural audio; observer visibility; protected camera soldier")
        (output / "capture.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"Saved {movie} ({movie.stat().st_size / 1_000_000:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
