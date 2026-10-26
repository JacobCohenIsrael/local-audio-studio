"""Seeded CPU synthesis of original game effects; no speech model or samples."""
import json
import math
import time
import zipfile

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 48000
EFFECTS = ("explosion", "laser", "plasma")


def validate(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError("A sound-effects batch needs 1–16 items.")
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) - {"effect", "duration", "intensity", "seed"}:
            raise ValueError("Use effect, duration, intensity and seed only.")
        effect = item.get("effect")
        duration, intensity, seed = item.get("duration", 2.0), item.get("intensity", 0.7), item.get("seed", 42)
        if effect not in EFFECTS:
            raise ValueError("Choose explosion, laser or plasma.")
        for value, low, high, name in ((duration, 0.15, 8, "Duration"), (intensity, 0, 1, "Intensity")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be {low}–{high}.")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2147483647:
            raise ValueError("Seed must be 0–2147483647.")
        result.append(dict(effect=effect, duration=float(duration), intensity=float(intensity), seed=seed))
    return result


def synthesize(effect, duration=2.0, intensity=0.7, seed=42):
    item = validate([dict(effect=effect, duration=duration, intensity=intensity, seed=seed)])[0]
    duration, intensity = item["duration"], item["intensity"]
    sr = SAMPLE_RATE
    rng = np.random.default_rng(seed)
    t = np.arange(round(duration * sr)) / sr
    u = t / duration
    noise = rng.standard_normal(len(t))

    def lowpass(y, hz):
        return sosfilt(butter(3, hz, fs=sr, output="sos"), y)

    def oscillator(frequency):
        return np.sin(2 * np.pi * np.cumsum(np.broadcast_to(frequency, t.shape)) / sr)

    if effect == "explosion":
        # A sharp pressure front, descending body, rumble and scattered debris.
        rumble = lowpass(noise, 100 + 140 * intensity)
        body = oscillator(35 + (100 + 80 * intensity) * np.exp(-u * 24))
        crack = noise - lowpass(noise, 1800)
        debris = lowpass(noise, 2200) * np.maximum(0, np.sin(t * (55 + rng.uniform(0, 25)))) ** 8
        y = (3.5 * rumble + .65 * body) * np.exp(-u * 5)
        y += crack * (.4 + intensity) * np.exp(-u * 70) + debris * intensity * np.exp(-u * 7)
    elif effect == "laser":
        frequency = 100 + (1600 + intensity * 2600 + rng.uniform(-250, 250)) * np.exp(-u * 18)
        phase = 2 * np.pi * np.cumsum(frequency) / sr
        y = (np.sin(phase) + .28 * np.sin(phase * 2.01)) * np.exp(-u * 10)
        y = np.tanh(y * (1 + 3 * intensity))
        y += .12 * noise * np.exp(-u * 100)
    else:
        # Brief rising charge, unstable discharge and a resonating energy tail.
        charge = oscillator(140 + 950 * np.minimum(u / .18, 1) ** 2)
        charge *= np.sin(np.pi * np.minimum(u / .18, 1)) ** 2 * (u < .18)
        age = np.maximum(u - .18, 0)
        phase = 2 * np.pi * np.cumsum(75 + 650 * np.exp(-age * 14)) / sr
        discharge = np.sin(phase + (2 + 4 * intensity) * np.sin(phase * 1.47))
        discharge += lowpass(noise, 1600 + 4000 * intensity) * (.5 + intensity)
        discharge *= (u >= .18) * (1 - np.exp(-age * 350)) * np.exp(-age * 6)
        y = charge * .45 + np.tanh(discharge * (1 + intensity))
    # Short echoes remain within the requested duration.
    dry = y.copy()
    for delay, gain in ((.073, .23), (.137, .12)):
        offset = int(delay * sr)
        if offset < len(y):
            y[offset:] += dry[:-offset] * gain
    fade = min(int(sr * .005), len(y) // 2)
    y[:fade] *= np.linspace(0, 1, fade)
    y *= np.minimum(1, (1 - u) / .10) ** 2
    y[-1] = 0
    peak = np.max(np.abs(y))
    y *= (.55 + .34 * intensity) / max(float(peak), 1e-9)
    return y.astype(np.float32)


def render_batch(job, items, cancel_event, deadline_seconds=300):
    items = validate(items)
    started = time.monotonic()

    def check():
        if cancel_event.is_set():
            raise RuntimeError("Sound-effects job cancelled; partial outputs retained.")
        if time.monotonic() - started >= deadline_seconds:
            raise RuntimeError("Sound-effects batch exceeded its deadline; no retry performed.")

    check()
    job.mkdir(parents=True)
    (job / "request.json").write_text(json.dumps({"mode":"sfx", "synthesis_version":1, "items":items}, indent=2), encoding="utf-8")
    outputs = []
    for index, item in enumerate(items, 1):
        check()
        y = synthesize(**item)
        check()
        name = f"sfx-{index:03d}-{item['effect']}.wav"
        sf.write(job / name, y, SAMPLE_RATE, subtype="PCM_24")
        outputs.append({**item, "file":name, "seconds":len(y) / SAMPLE_RATE})
    result = {"status":"complete", "gpu_used":False, "sample_rate":SAMPLE_RATE,
              "subtype":"PCM_24", "channels":1, "items":outputs,
              "seconds":sum(i["seconds"] for i in outputs),
              "quality":"Procedural game effects; listening approval pending."}
    (job / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with zipfile.ZipFile(job / "sound-effects.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in [i["file"] for i in outputs] + ["request.json", "result.json"]:
            check()
            archive.write(job / name, name)
    check()
    return job, result
