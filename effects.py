"""CPU radio processing; the clean recording is always kept separately."""
import math
import numpy as np
from scipy.signal import butter, sosfilt

PRESETS = {"Light": (180, 4800, 1.25), "Radio": (300, 3400, 2.0), "Damaged radio": (450, 2700, 3.2)}

def mono_audio(data):
    y = np.asarray(data, dtype=np.float32)
    if y.ndim == 2:
        y = y.mean(axis=1)
    if y.ndim != 1 or not y.size or not np.isfinite(y).all():
        raise ValueError("Audio must contain finite, non-empty mono or stereo samples.")
    return y

def safe_level(data, peak=0.89):
    y = mono_audio(data).copy()
    maximum = float(np.max(np.abs(y)))
    if maximum > peak:
        y *= peak / maximum
    return y

def radio_effect(data, sample_rate, preset="Radio", static_percent=0.3, seed=42):
    if preset not in PRESETS:
        raise ValueError("Choose a listed radio preset.")
    if not 0 <= float(static_percent) <= 2:
        raise ValueError("Static must be between 0 and 2 percent.")
    if not 8000 <= sample_rate <= 192000:
        raise ValueError("Unsupported sample rate.")
    y = mono_audio(data).astype(np.float64)
    low, high, drive = PRESETS[preset]
    high = min(high, sample_rate * 0.45)
    sos = butter(4, [low, high], btype="bandpass", fs=sample_rate, output="sos")
    y = sosfilt(sos, y)
    # Soft saturation compresses peaks. Filtering again restrains new harmonics.
    rms = math.sqrt(float(np.mean(y * y)) + 1e-12)
    if rms > 1e-5:
        y = y * min(4.0, 0.16 / rms)
    y = np.tanh(y * drive) / np.tanh(drive)
    y = sosfilt(sos, y)
    noise = np.random.default_rng(int(seed)).standard_normal(len(y))
    y += sosfilt(sos, noise) * (float(static_percent) / 100)
    # Short fades avoid abrupt clicks without changing duration.
    n = min(int(sample_rate * 0.008), len(y) // 2)
    if n:
        y[:n] *= np.linspace(0, 1, n)
        y[-n:] *= np.linspace(1, 0, n)
    return safe_level(y)
