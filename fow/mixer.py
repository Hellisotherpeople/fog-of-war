"""The mixer: every sound in the game summed into one output stream, from its own thread.

The game used to hand each sound to its own SDL stream and top the ambience up between frames.  A frame
that took longer than the quarter-second in the queue (and, waiting for a key, every frame did) let the
ambience run dry, and the speakers clicked three or four times a second.  Here one thread keeps a small
margin of mixed audio queued whatever the game is doing, and widens the margin if it ever runs dry.

On the way out everything passes a look-ahead limiter and a soft clipper, so a firefight is loud
rather than distorted, and every gain - the master volume, the ambience, the music - glides to its new
value instead of stepping.
"""
from __future__ import annotations

import collections
import threading
import time

import numpy as np

SR = 44100
BLOCK = 512                 # samples per render: 11.6 ms
MIN_AHEAD = int(SR * .07)   # the margin of mixed audio kept queued ...
MAX_AHEAD = int(SR * .45)   # ... widened up to this if the speakers ever catch up with it
MAX_VOICES = 48
LIMIT = .89                 # the limiter's ceiling
RELEASE = 1 - np.exp(-BLOCK / (SR * .25))   # the limiter lets go over a quarter of a second
GLIDE = BLOCK / (SR * .2)   # loops and the master volume move a fifth of a second per unit of gain
FADE = int(SR * .008)       # the fade on a sound that is cut short
EDGE_IN = 24                # every clip eases in over half a millisecond (a gunshot still cracks) ...
EDGE_OUT = int(SR * .01)    # ... and out over ten


def _soft_clip(x, knee=.9):
    """Leave the signal alone below the knee; round it off smoothly above."""
    a = np.abs(x)
    over = a > knee
    if over.any():
        y = x[over]
        x[over] = np.sign(y) * (knee + (1 - knee) * np.tanh((np.abs(y) - knee) / (1 - knee)))
    return x


class _Voice:
    __slots__ = ("data", "pos", "gl", "gr", "start", "fade", "tag")

    def __init__(self, data, gl, gr, start, tag):
        self.data, self.gl, self.gr, self.start, self.tag = data, gl, gr, start, tag
        self.pos = 0
        self.fade = None           # samples of fade-out left, once it's being cut short


class _Loop:
    __slots__ = ("data", "pos", "gain", "target", "right")

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.gain = 0.0
        self.target = 0.0
        self.right = 1.0


class Mixer:
    """Thread-safe from the game's side: every call just leaves a note for the mixing thread."""

    def __init__(self, stream=None, start=True):
        self.stream = stream
        self.voices: list[_Voice] = []
        self.loops: dict[str, _Loop] = {}
        self.music: list = []           # music sources now sounding (several while one fades into the next)
        self.master = 0.0
        self.master_target = 1.0
        self.clock = 0                  # samples rendered so far
        self.ahead = MIN_AHEAD
        self.underruns = 0
        self._calm_since = time.monotonic()
        self._cmd = collections.deque()
        self._lim = 1.0
        self._held = None               # the block rendered but not yet sent: the limiter's look-ahead
        self._sent = False              # audio queued and not known to have finished
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        if start and stream is not None:
            self._running = True
            self._thread = threading.Thread(target=self._run, name="fow-mixer", daemon=True)
            self._thread.start()

    # ------------------------------------------------------------ the game's side
    def play(self, mono, gl, gr, delay=0.0, tag=None):
        if mono is None or len(mono) == 0:
            return
        self._cmd.append(("play", mono, float(gl), float(gr), max(0.0, float(delay)), tag))

    def loop(self, name, data, gain, right=1.0):
        """A loop's level (it keeps its place while silent, and comes back where it left off)."""
        self._cmd.append(("loop", name, data, max(0.0, float(gain)), float(right)))

    def add_music(self, source):
        self._cmd.append(("music", source))

    def set_master(self, gain):
        self.master_target = max(0.0, float(gain))

    def stop_all(self):
        self._cmd.append(("stop",))

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def busy(self) -> bool:
        return bool(self.voices or self._cmd or any(m.sounding() for m in self.music))

    # ------------------------------------------------------------ the mixing thread
    def _run(self):
        frame = 8                       # bytes per stereo float32 sample
        while self._running:
            try:
                queued = self.stream.queued_bytes // frame
            except Exception:
                break
            if self._sent and queued == 0:
                self.underruns += 1     # the speakers caught up: keep more in hand from now on
                self.ahead = min(MAX_AHEAD, int(self.ahead * 1.5) + BLOCK)
                self._calm_since = time.monotonic()
            elif time.monotonic() - self._calm_since > 30 and self.ahead > MIN_AHEAD:
                self.ahead = max(MIN_AHEAD, self.ahead - BLOCK)
                self._calm_since = time.monotonic()
            while queued < self.ahead and self._running:
                blk = self.render(BLOCK)
                if blk is None:
                    self._sent = False
                    break
                try:
                    self.stream.queue_audio(blk)
                except Exception:
                    self._running = False
                    break
                self._sent = True
                queued += BLOCK
            time.sleep(.004)

    def _commands(self):
        while self._cmd:
            c = self._cmd.popleft()
            if c[0] == "play":
                _, mono, gl, gr, delay, tag = c
                self.voices.append(_Voice(mono, gl, gr, self.clock + int(delay * SR), tag))
                if len(self.voices) > MAX_VOICES:
                    # the quietest sound already playing gives way (and fades rather than stops)
                    live = [v for v in self.voices if v.fade is None and v.start <= self.clock]
                    if live:
                        min(live, key=lambda v: max(v.gl, v.gr)).fade = FADE
            elif c[0] == "loop":
                _, name, data, gain, right = c
                lp = self.loops.get(name)
                if lp is None or lp.data is not data:
                    old = lp
                    lp = self.loops[name] = _Loop(data)
                    if old is not None:
                        lp.gain, lp.pos = old.gain, old.pos % len(data)
                lp.target, lp.right = gain, right
            elif c[0] == "music":
                self.music.append(c[1])
            elif c[0] == "stop":
                for v in self.voices:
                    v.fade = FADE if v.fade is None else min(v.fade, FADE)
                for lp in self.loops.values():
                    lp.target = 0.0
                for m in self.music:
                    m.stop(.05)

    def render(self, n):
        """The next n samples of the whole mix (n, 2), or None when there is nothing at all to hear."""
        with self._lock:
            self._commands()
            if not self.voices and not self.music and (self._held is None or self._held[2] == 0) and \
                    not any(lp.gain > 1e-5 or lp.target > 1e-5 for lp in self.loops.values()):
                self._held = None
                return None
            out = np.zeros((n, 2), np.float32)
            self._mix_voices(out, n)
            self._mix_loops(out, n)
            self._mix_music(out, n)
            g0 = self.master
            g1 = g0 + max(-GLIDE, min(GLIDE, self.master_target - g0))
            self.master = g1
            out *= np.linspace(g0, g1, n, dtype=np.float32)[:, None]
            self.clock += n
            return self._limit(out)

    def _mix_voices(self, out, n):
        clock = self.clock
        keep = []
        for v in self.voices:
            off = v.start - clock
            if off >= n:
                keep.append(v)          # not yet
                continue
            off = max(0, off)
            take = min(n - off, len(v.data) - v.pos)
            if v.fade is not None:
                take = min(take, v.fade)
            if take > 0:
                seg = v.data[v.pos:v.pos + take]
                end = len(v.data)
                if v.pos < EDGE_IN or v.pos + take > end - EDGE_OUT:
                    # no sound starts or stops with a step: the speaker cone would click
                    i = np.arange(v.pos, v.pos + take, dtype=np.float32)
                    seg = seg * np.clip(np.minimum((i + 1) / EDGE_IN, (end - i) / EDGE_OUT), 0, 1)
                if v.fade is not None:
                    seg = seg * np.linspace(v.fade / FADE, (v.fade - take) / FADE, take, dtype=np.float32)
                    v.fade -= take
                out[off:off + take, 0] += seg * v.gl
                out[off:off + take, 1] += seg * v.gr
                v.pos += take
            if v.pos < len(v.data) and (v.fade is None or v.fade > 0):
                keep.append(v)
        self.voices = keep

    def _mix_loops(self, out, n):
        for lp in self.loops.values():
            g0 = lp.gain
            g1 = g0 + max(-GLIDE, min(GLIDE, lp.target - g0))
            lp.gain = g1
            if g0 < 1e-5 and g1 < 1e-5:
                continue
            data = lp.data
            idx = (lp.pos + np.arange(n)) % len(data)
            seg = data[idx] * np.linspace(g0, g1, n, dtype=np.float32)
            lp.pos = (lp.pos + n) % len(data)
            out[:, 0] += seg
            out[:, 1] += seg * lp.right

    def _mix_music(self, out, n):
        keep = []
        for m in self.music:
            blk = m.read(n)
            if blk is not None:
                out[:len(blk)] += blk
            if not m.finished():
                keep.append(m)
        self.music = keep

    def _limit(self, cur):
        """Hold each block back one turn, so the gain can come down before a loud block rather than in it."""
        peak = float(np.max(np.abs(cur))) if len(cur) else 0.0
        need = 1.0 if peak <= LIMIT else LIMIT / peak
        prev, self._held = self._held, (cur, need, peak)
        if prev is None:
            prev = (np.zeros_like(cur), 1.0, 0.0)
        blk, need_here, _ = prev
        g0 = self._lim
        g1 = min(need, g0 + (1.0 - g0) * RELEASE)
        ramp = np.minimum(np.linspace(g0, g1, len(blk), dtype=np.float32), max(need_here, 1e-3))
        self._lim = g1
        blk *= ramp[:, None]
        return _soft_clip(blk)


class MusicSource:
    """A piece of music, decoded a few seconds ahead on its own thread and faded in and out."""

    def __init__(self, path, gain=1.0, fade_in=2.0, loop=False, on_end=None):
        self.path = path
        self.gain = 0.0
        self.target = float(gain)
        self.step = BLOCK / (SR * max(.01, fade_in))
        self.loop = loop
        self.on_end = on_end
        self._buf = collections.deque()
        self._have = 0
        self._eof = False
        self._done = False
        self._stopping = False
        self._ok = True
        self._thread = threading.Thread(target=self._decode, name="fow-music", daemon=True)
        self._thread.start()

    def _decode(self):
        try:
            import soundfile as sf
            while not self._done:
                with sf.SoundFile(self.path) as f:
                    sr, ch = f.samplerate, f.channels
                    while not self._done:
                        if self._have > SR * 4:
                            time.sleep(.05)
                            continue
                        a = f.read(SR, dtype="float32", always_2d=True)
                        if len(a) == 0:
                            break
                        if ch == 1:
                            a = np.repeat(a, 2, axis=1)
                        elif ch > 2:
                            a = a[:, :2]
                        if sr != SR:
                            a = _resample(a, sr, SR)
                        self._buf.append(np.ascontiguousarray(a, np.float32))
                        self._have += len(a)
                if not self.loop:
                    break
        except Exception:
            self._ok = False
        self._eof = True

    def stop(self, fade=2.0):
        self._stopping = True
        self.target = 0.0
        self.step = BLOCK / (SR * max(.01, fade))

    def set_gain(self, g):
        if not self._stopping:
            self.target = float(g)

    def sounding(self):
        return not self.finished()

    def finished(self):
        return self._done

    def read(self, n):
        if self._done:
            return None
        out = np.zeros((n, 2), np.float32)
        got = 0
        while got < n and self._buf:
            a = self._buf[0]
            take = min(n - got, len(a))
            out[got:got + take] = a[:take]
            if take < len(a):
                self._buf[0] = a[take:]
            else:
                self._buf.popleft()
            self._have -= take
            got += take
        g0 = self.gain
        g1 = g0 + max(-self.step, min(self.step, self.target - g0))
        self.gain = g1
        out *= np.linspace(g0, g1, n, dtype=np.float32)[:, None]
        if (self._stopping and g1 <= 1e-4) or (self._eof and not self._buf and got < n):
            self._done = True
            if self.on_end is not None and not self._stopping:
                try:
                    self.on_end(self)
                except Exception:
                    pass
        return out

    def ready(self):
        return bool(self._buf) or self._eof


def _resample(a, sr_from, sr_to):
    """Linear resampling (the music is prepared at 44.1 kHz; this is only for strays)."""
    n = int(round(len(a) * sr_to / sr_from))
    if n <= 1:
        return a
    x = np.linspace(0, len(a) - 1, n)
    return np.stack([np.interp(x, np.arange(len(a)), a[:, c]) for c in range(a.shape[1])], 1).astype(np.float32)
