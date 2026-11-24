"""Rebuild the original, deterministic synthesized story test cues.

Run from any directory with the project's Python environment. No recordings,
downloaded samples, speech, or external sound libraries are used.
"""
from pathlib import Path
import wave

import numpy as np
from scipy.signal import butter, sosfilt


RATE = 44100
DESTINATION = Path(__file__).resolve().parent
RNG = np.random.default_rng(20261107)


def timeline(seconds):
    return np.arange(round(seconds * RATE)) / RATE


def noise(seconds, low, high):
    samples = RNG.normal(size=round(seconds * RATE))
    filtered = sosfilt(butter(3, [low, high], btype='bandpass', fs=RATE, output='sos'), samples)
    return filtered / max(np.std(filtered), 1e-8)


def fade(samples, attack=.04, release=.15):
    samples = samples.copy()
    a, r = min(round(attack * RATE), len(samples)), min(round(release * RATE), len(samples))
    samples[:a] *= np.linspace(0, 1, a)
    samples[-r:] *= np.linspace(1, 0, r)
    return samples


def add(destination, cue, at):
    start = round(at * RATE)
    count = min(len(cue), len(destination) - start)
    if count > 0:
        destination[start:start + count] += cue[:count]


def bells(notes, seconds=2.4, spacing=.17):
    result = np.zeros(len(timeline(seconds)))
    t = timeline(1.5)
    for index, frequency in enumerate(notes):
        cue = sum(amplitude * np.sin(2 * np.pi * frequency * ratio * t) * np.exp(-decay * t)
                  for ratio, amplitude, decay in [(1, 1, 3), (2.01, .25, 5), (3.98, .1, 8)])
        add(result, fade(cue, .006, .1), index * spacing)
    return result


def breeze():
    t = timeline(3.5)
    return noise(3.5, 100, 2000) * (.3 + .2 * np.sin(2 * np.pi * .45 * t))


def leaves():
    result = np.zeros(len(timeline(2.6)))
    for at in (.05, .36, .8, 1.14, 1.6, 1.95):
        t = timeline(.45)
        add(result, noise(.45, 1800, 9000) * np.sin(np.pi * t / .45) ** 2, at)
    return result


def hoofbeats():
    result = np.zeros(len(timeline(2.5)))
    t = timeline(.15)
    hit = (np.sin(2 * np.pi * 160 * t) + .5 * noise(.15, 500, 4000)) * np.exp(-35 * t)
    for at, strength in [(.05, 1), (.22, .75), (.6, 1), (.77, .75),
                         (1.15, 1), (1.32, .75), (1.7, 1), (1.87, .75)]:
        add(result, fade(hit * strength, .002, .02), at)
    return result


def purr():
    t = timeline(2.6)
    breath = .65 + .35 * np.sin(2 * np.pi * .7 * t)
    pulses = (.5 + .5 * np.sin(2 * np.pi * 26 * t)) ** 2
    return breath * pulses * (np.sin(2 * np.pi * 104 * t) + .35 * noise(2.6, 70, 500))


def tumble():
    result = np.zeros(len(timeline(1.8)))
    for at, frequency in [(0, 440), (.3, 330), (.6, 220), (.9, 150)]:
        t = timeline(.5)
        add(result, np.sin(2 * np.pi * (frequency * t - 55 * t * t)) * np.exp(-9 * t), at)
    return result


def tea_pour():
    t = timeline(2.2)
    water = noise(2.2, 500, 7500) * np.sin(np.pi * t / 2.2) ** 1.5
    result = .4 * water
    for at in (.12, .65, 1.2, 1.8):
        drop_t = timeline(.15)
        add(result, .45 * np.sin(2 * np.pi * (900 * drop_t - 1600 * drop_t ** 2))
            * np.exp(-30 * drop_t), at)
    return result


def kettle():
    t = timeline(2.5)
    hiss = .2 * noise(2.5, 1500, 8000)
    whistle = np.sin(2 * np.pi * (1500 * t + 70 * t * t)) * (.5 + .1 * np.sin(2 * np.pi * 5 * t))
    return (hiss + whistle) * np.minimum(t / .7, 1)


def broom():
    result = np.zeros(len(timeline(2.1)))
    for at in (0, .65, 1.3):
        t = timeline(.55)
        add(result, noise(.55, 500, 6500) * np.sin(np.pi * t / .55) ** 2, at)
    return result


def rain():
    result = .16 * noise(3.5, 700, 9500)
    for at in RNG.uniform(0, 3.3, 45):
        t = timeline(.08)
        add(result, .25 * np.sin(2 * np.pi * RNG.uniform(900, 2300) * t) * np.exp(-75 * t), at)
    return result


def umbrella():
    t = timeline(.7)
    return noise(.7, 250, 6500) * np.exp(-((t - .24) / .13) ** 2) + .4 * np.sin(2 * np.pi * 180 * t) * np.exp(-45 * t)


def splash():
    t = timeline(1.6)
    result = noise(1.6, 350, 9500) * (1 - np.exp(-60 * t)) * np.exp(-4 * t)
    for at in (.25, .42, .66, .9):
        drop_t = timeline(.2)
        add(result, .7 * np.sin(2 * np.pi * (1100 * drop_t - 1400 * drop_t ** 2)) * np.exp(-24 * drop_t), at)
    return result


def door_hook():
    result = np.zeros(len(timeline(.85)))
    t = timeline(.2)
    for at, frequency in [(0, 380), (.25, 260)]:
        add(result, (np.sin(2 * np.pi * frequency * t) + .25 * noise(.2, 400, 3000)) * np.exp(-25 * t), at)
    return result


def main():
    cues = {
        'soft_chime': bells([660, 990, 1320]),
        'gentle_leaves': leaves(),
        'light_breeze': breeze(),
        'quiet_bell': bells([784], seconds=2),
        'horse_hooves': hoofbeats(),
        'cat_purr': purr(),
        'comic_tumble': tumble(),
        'tea_pour': tea_pour(),
        'kettle_simmer': kettle(),
        'broom_sweep': broom(),
        'magic_shimmer': bells([523.25, 659.25, 784, 1046.5, 1318.5], seconds=2.8),
        'soft_mystery': bells([392, 466.16, 587.33], seconds=2.8, spacing=.3),
        'rain_soft': rain(),
        'umbrella_open': umbrella(),
        'pond_splash': splash(),
        'umbrella_hook': door_hook(),
    }
    for name, samples in cues.items():
        samples = fade(samples)
        samples *= .55 / max(float(np.max(np.abs(samples))), 1e-8)
        path = DESTINATION / (name + '.wav')
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            audio.writeframes((samples * 32767).astype('<i2').tobytes())
        print(f'{name}: {len(samples) / RATE:g}s')


if __name__ == '__main__':
    main()
