#!/usr/bin/env python3
"""Build a recorded sound pack (assets/sounds/<pack>) from curated source recordings.

    python tools/build_sounds.py curation.json            -> assets/sounds/<pack>/ (OGGs, pack.json, CREDITS.md)
    python tools/build_sounds.py curation.json --sheet    ... and a waveform/spectrogram sheet per slot (PNG)

curation.json:
    {"pack": "cinema",
     "slots": {"mg42": [{"src": "path/to/burst.wav", "start": 0.4, "end": 3.1, "gain_db": 0, "auto": true,
                         "title": "...", "author": "...", "license": "CC0 1.0", "license_url": "...",
                         "source": "https://..."}],
               "amb_wind": [{"src": "...", "loop": true, "end": 40}], ...}}

Each recording is mixed to mono at 44.1 kHz, cut (start/end, else trimmed at its first and last sound), rid of
rumble below 30 Hz, normalised to the synthesised bank's peak, faded at the ends - or, for a loop, cross-faded
end into start - and written as Ogg Vorbis.  For automatic weapons ("auto") the start of every shot is found
and recorded, so the game can rebuild a burst of any length from the gun's own rounds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        n = int(round(len(x) * SR / sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x


def highpass(x, hz=30.0):
    X = np.fft.rfft(x, len(x) + 4096)
    f = np.fft.rfftfreq(len(x) + 4096, 1 / SR)
    X *= 1 / (1 + (hz / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X, len(x) + 4096)[:len(x)].astype(np.float32)


def envelope(x, ms=2.0):
    k = max(1, int(SR * ms / 1000))
    a = np.abs(x)
    pad = np.concatenate([a, np.zeros(k - len(a) % k)]) if len(a) % k else a
    return np.repeat(pad.reshape(-1, k).max(axis=1), k)[:len(a)]


def trim(x, lead_db=-38.0, tail_db=-52.0):
    env = envelope(x, 2)
    peak = float(env.max()) or 1.0
    on = np.where(env > peak * 10 ** (lead_db / 20))[0]
    if not len(on):
        return x
    a = max(0, on[0] - int(SR * .004))
    tail = np.where(env > peak * 10 ** (tail_db / 20))[0]
    b = min(len(x), tail[-1] + int(SR * .03))
    return x[a:b]


def onsets(x, min_gap=0.035, rel_db=-14.0):
    """The start of each shot in a burst: sharp rises in the envelope, no two closer than min_gap seconds."""
    env = envelope(x, 1.0)
    peak = float(env.max()) or 1.0
    thr = peak * 10 ** (rel_db / 20)
    d = np.diff(np.concatenate([[0], env]))
    rising = np.where((env > thr) & (d > thr * .25))[0]
    out = []
    gap = int(SR * min_gap)
    for i in rising:
        if not out or i - out[-1] >= gap:
            out.append(int(i))
    # pull each mark back to the quiet just before the shot
    marks = []
    for i in out:
        j = max(0, i - int(SR * .006))
        seg = env[j:i + 1]
        marks.append(int(j + int(np.argmin(seg))))
    return marks


def fades(x, fin=0.002, fout=0.03):
    x = x.copy()
    a, b = int(SR * fin), min(len(x) // 3, int(SR * fout))
    if a:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b:
        x[-b:] *= np.linspace(1, 0, b, dtype=np.float32) ** 1.5
    return x


def make_loop(x, xfade=1.5):
    """A seamless loop: the end cross-faded (equal power) into the start."""
    n = int(SR * xfade)
    if len(x) < 3 * n:
        return x
    head, body, tail = x[:n], x[n:len(x) - n], x[len(x) - n:]
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    mixed = tail * np.cos(t) + head * np.sin(t)
    return np.concatenate([mixed, body]).astype(np.float32)


def write_ogg(path, x, quality=0.65):
    import soundfile as sf
    # (libsndfile's Vorbis "compression level" runs the other way: 0 is the best quality, 1 the smallest file)
    with sf.SoundFile(path, "w", SR, 1, format="OGG", subtype="VORBIS", compression_level=1.0 - quality) as f:
        f.write(x)


def build(cur, sheet=False):
    pack = cur.get("pack", "cinema")
    out_dir = os.path.join(ROOT, "assets", "sounds", pack)
    os.makedirs(out_dir, exist_ok=True)
    spec = {"name": pack, "slots": {}}
    credits = []
    sheets = []
    for slot, entries in cur["slots"].items():
        for k, e in enumerate(entries):
            x = load(e["src"])
            if "start" in e or "end" in e:
                a = int(SR * float(e.get("start", 0)))
                b = int(SR * float(e["end"])) if e.get("end") is not None else len(x)
                x = x[a:b]
            x = highpass(x)
            if not e.get("loop"):
                x = trim(x)
            peak = float(np.max(np.abs(x))) or 1.0
            x = (x / peak * 0.9 * 10 ** (float(e.get("gain_db", 0)) / 20)).astype(np.float32)
            entry = {}
            if e.get("loop"):
                x = make_loop(x)
            else:
                x = fades(x)
            if e.get("auto"):
                ons = onsets(x, float(e.get("min_gap", 0.035)), float(e.get("rel_db", -14)))
                if e.get("max_shots"):
                    ons = ons[:int(e["max_shots"])]
                if len(ons) >= 2:
                    entry["onsets"] = ons
            name = f"{slot}_{k + 1}.ogg"
            write_ogg(os.path.join(out_dir, name), x)
            entry = {"file": name, **entry}
            if e.get("gain") is not None:
                entry["gain"] = float(e["gain"])
            spec["slots"].setdefault(slot, []).append(entry)
            credits.append((name, slot, e))
            if sheet:
                sheets.append((slot, k, x, entry.get("onsets")))
            print(f"  {name:28} {len(x) / SR:6.2f} s" + (f"  {len(entry['onsets'])} shots" if "onsets" in entry else ""))
    with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    with open(os.path.join(ROOT, "assets", "sounds", "CREDITS.md"), "w", encoding="utf-8") as f:
        f.write("# Recorded sounds\n\nThe `cinema` sound pack (Options > Sound pack). Every recording is free to "
                "use and redistribute under the licence shown; each was cut, mixed to mono, normalised and "
                "re-encoded by `tools/build_sounds.py`. Nothing here is taken from any film, game or broadcast.\n\n"
                "| File | Sound | Source | Author | Licence |\n|---|---|---|---|---|\n")
        for name, slot, e in credits:
            lic = e.get("license", "?")
            if e.get("license_url"):
                lic = f"[{lic}]({e['license_url']})"
            src = f"[{e.get('title', 'source')}]({e['source']})" if e.get("source") else e.get("title", "")
            f.write(f"| `{name}` | {slot} | {src} | {e.get('author', '')} | {lic} |\n")
    if sheets:
        draw_sheets(sheets, out_dir)
    return out_dir


def draw_sheets(sheets, out_dir):
    """Waveform and spectrogram of every clip (for checking the cuts by eye)."""
    from PIL import Image, ImageDraw
    w, h = 900, 150
    by_slot = {}
    for slot, k, x, ons in sheets:
        by_slot.setdefault(slot, []).append((k, x, ons))
    dest = os.path.join("/tmp", "fow_sound_sheets")
    os.makedirs(dest, exist_ok=True)
    for slot, clips in by_slot.items():
        img = Image.new("RGB", (w, h * len(clips)), (12, 12, 12))
        d = ImageDraw.Draw(img)
        for row, (k, x, ons) in enumerate(clips):
            y0 = row * h
            # spectrogram (top two thirds)
            n = 1024
            hop = max(1, len(x) // w)
            cols = []
            for i in range(w):
                seg = x[i * hop:i * hop + n]
                if len(seg) < n:
                    seg = np.concatenate([seg, np.zeros(n - len(seg), np.float32)])
                cols.append(np.abs(np.fft.rfft(seg * np.hanning(n)))[:256])
            S = 20 * np.log10(np.array(cols).T + 1e-6)
            S = np.clip((S - S.max() + 70) / 70, 0, 1)[::-1]
            spec = Image.fromarray((S * 255).astype(np.uint8)).resize((w, h * 2 // 3))
            img.paste(Image.merge("RGB", (spec, spec.point(lambda v: v * .7), spec.point(lambda v: v * .3))), (0, y0))
            # waveform (bottom third)
            env = envelope(x, max(0.5, len(x) / SR * 1000 / w))
            mid = y0 + h * 2 // 3 + h // 6
            for i in range(w):
                v = env[min(len(env) - 1, int(i * len(x) / w))]
                d.line([(i, mid - v * h / 6), (i, mid + v * h / 6)], fill=(120, 200, 120))
            for o in ons or []:
                xx = int(o / len(x) * w)
                d.line([(xx, y0), (xx, y0 + h)], fill=(255, 60, 60))
            d.text((4, y0 + 2), f"{slot}_{k + 1}  {len(x) / SR:.2f}s", fill=(255, 255, 0))
        img.save(os.path.join(dest, f"{slot}.png"))
    print("  sheets in", dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("curation")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    with open(a.curation, encoding="utf-8") as f:
        cur = json.load(f)
    print("->", build(cur, a.sheet))


if __name__ == "__main__":
    sys.exit(main())
