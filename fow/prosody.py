"""Cheap, deterministic local speech delivery; no model or network required.

This adds restrained timing, breath and emphasis to existing voices. It cannot
turn a neutral TTS model into a trained actor. Radio filtering is a separate layer.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Delivery:
    rate: int
    pitch: float = 1.
    tremor: float = 0.
    breath: float = 0.
    emphasis: float = 0.
    gain: float = 1.


STYLES = {
    'talk': Delivery(180, emphasis=.025),
    'shout': Delivery(216, 1.035, emphasis=.12),
    'scream': Delivery(232, 1.075, .012, .025, .16),
    'panic': Delivery(238, 1.045, .016, .018, .13),
    'pain': Delivery(160, 1.02, .02, .025, .1),
    'whisper': Delivery(163, .99, breath=.05, emphasis=.035, gain=.58),
    'mutter': Delivery(158, .98, breath=.012, gain=.72),
    'calm': Delivery(166, .985, emphasis=.035, gain=.88),
    'urgent': Delivery(221, 1.025, emphasis=.13),
    'weary': Delivery(153, .98, .003, .018, .045, .8),
    'radio': Delivery(198, emphasis=.07),
}


def style_for(actor, tone):
    """An explicit acting cue wins; otherwise the speaker's body supplies it."""
    if tone not in ('talk', 'shout', 'radio'):
        return tone if tone in STYLES else 'talk'
    if actor.body.effective_pain() > 75:
        return 'pain'
    if actor.suppression > 60 and actor.morale < 40:
        return 'panic'
    if actor.stamina < 20 and tone == 'talk':
        return 'weary'
    if tone == 'talk' and actor.ai.get('patient'):
        return 'calm'
    return tone


def shape(x, style, sr, seed=0):
    """A small expressive contour on mono samples, after the voice and acoustic filters."""
    profile = STYLES.get(style, STYLES['talk'])
    if len(x) < 2:
        return x.astype(np.float32)
    rng = np.random.default_rng(seed)
    # Work at a 100 Hz control rate; sample interpolation is linear and vectorized.
    frames = max(2, int(len(x) / sr * 100) + 1)
    t = np.linspace(0., len(x) / sr, frames)
    phase = rng.uniform(0, 2 * np.pi)
    contour = profile.pitch * (1 + profile.tremor * np.sin(2 * np.pi * 6.1 * t + phase))
    contour *= 1 + profile.emphasis * .12 * np.sin(2 * np.pi * 1.7 * t + phase)
    speed = np.interp(np.arange(len(x)), np.linspace(0, len(x) - 1, frames), contour)
    index = np.cumsum(speed) - speed[0]
    index = index[index < len(x) - 1]
    y = np.interp(index, np.arange(len(x)), x).astype(np.float32)
    n = len(y)
    tt = np.arange(n, dtype=np.float32) / sr
    envelope = 1 + profile.emphasis * np.sin(2 * np.pi * 2.3 * tt + phase)
    # Noise follows actual voiced energy, so pauses stay quiet.
    if profile.breath:
        hop = max(1, sr // 100)
        padded = np.pad(y * y, (0, (-n) % hop))
        rms = np.sqrt(padded.reshape(-1, hop).mean(axis=1))
        energy = np.repeat(rms, hop)[:n]
        breath = rng.standard_normal(n).astype(np.float32)
        breath[1:] -= breath[:-1] * .92
        y += breath * energy * profile.breath
    y *= envelope * profile.gain
    # Preserve relative delivery loudness; only reduce peaks that would clip.
    y /= max(1., float(np.max(np.abs(y))) / .97)
    return y.astype(np.float32)
