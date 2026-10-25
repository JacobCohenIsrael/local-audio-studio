"""Recording preservation, validation and owned inference process management."""
from runtime import ROOT, configure
configure(offline=True)
import gc
import json
import math
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from effects import PRESETS, mono_audio, safe_level
from voice_profiles import VOICE_CHOICES, CUSTOM_VOICE, get_profile, voice_path
from delivery import prepare_delivery

_job_lock = threading.Lock()
_process_lock = threading.Lock()
_active_process = None
_cancelled = threading.Event()

def load_audio(path, maximum=30, minimum=0.5):
    if not path or not Path(path).is_file():
        raise ValueError("Record or upload an audio clip first.")
    if Path(path).stat().st_size > 30 * 1024**2:
        raise ValueError("Audio files must be smaller than 30 MB.")
    info = sf.info(path)
    if not 8000 <= info.samplerate <= 192000 or info.channels not in (1, 2):
        raise ValueError("Use mono or stereo audio at 8–192 kHz.")
    if not minimum <= info.duration <= maximum:
        raise ValueError(f"Use a clip between {minimum:g} and {maximum:g} seconds.")
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    y = mono_audio(y)
    if float(np.sqrt(np.mean(y*y))) < 1e-5:
        raise ValueError("This clip is nearly silent. Check your microphone and record again.")
    return y, sr

def prepared_copy(original, destination, maximum, minimum=0.5, first_seconds=None):
    y, sr = load_audio(original, maximum, minimum)
    if first_seconds is not None:
        y = y[:int(sr * first_seconds)]
    factor = math.gcd(sr, 24000)
    y = resample_poly(y, 24000 // factor, sr // factor)
    sf.write(destination, safe_level(y), 24000, subtype="PCM_16")

def choose_reference(choice, custom=None):
    if choice not in VOICE_CHOICES:
        raise ValueError("Select a listed voice.")
    if choice == CUSTOM_VOICE:
        if not custom:
            raise ValueError("Record or upload your target voice reference.")
        return Path(custom)
    return voice_path(get_profile(choice)["file"])

def stop_active():
    _cancelled.set()
    with _process_lock:
        process = _active_process
        if process is not None and process.poll() is None:
            process.kill()
            return "Stopping your current audio job. Its inputs and logs are kept."
    return "No audio job is running."

def wait_owned(process, timeout=300):
    deadline = time.monotonic() + timeout
    while process.poll() is None:
        if _cancelled.is_set() or time.monotonic() >= deadline:
            process.kill()
            process.wait(timeout=15)
            if _cancelled.is_set():
                raise RuntimeError("Cancelled. Inputs and logs were retained.")
            raise RuntimeError(f"Stopped after {timeout} seconds. Inputs and logs were retained.")
        time.sleep(0.15)
    if _cancelled.is_set():
        raise RuntimeError("Cancelled. Inputs and logs were retained.")
    return process.returncode

def run_job(mode, source, voice, custom, text="", preset="Radio", static=0.3, seed=42, tone="Natural"):
    global _active_process
    if not _job_lock.acquire(blocking=False):
        raise RuntimeError("An audio job is already running. Wait or cancel it first.")
    job = None
    try:
        _cancelled.clear()
        if mode not in ("convert", "tts") or preset not in PRESETS:
            raise ValueError("Invalid audio mode or radio preset.")
        seed = int(seed)
        if not 0 <= seed <= 2147483647 or not 0 <= float(static) <= 2:
            raise ValueError("Invalid seed or static strength.")
        original_text = text
        delivery = None
        if mode == "tts":
            text, delivery = prepare_delivery(text, tone)
        reference = choose_reference(voice, custom)
        try:
            load_audio(reference, maximum=30, minimum=3)
        except ValueError as exc:
            raise ValueError(f"Voice sample to copy: {exc} Your dialogue recording can be shorter.") from exc
        if mode == "convert":
            load_audio(source, maximum=30)
        for name in (["s3gen.safetensors"] if mode == "convert" else ["s3gen.safetensors", "t3_cfg.safetensors", "ve.safetensors", "tokenizer.json"]):
            if not (ROOT / "models" / "chatterbox" / name).is_file():
                raise RuntimeError("A required model is missing. Run Setup Audio.cmd.")
        job = ROOT / "outputs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        job.mkdir(parents=True)
        config = {"mode":mode, "voice":voice, "text":text.strip(), "radio_preset":preset,
            "static_percent":float(static), "seed":seed, "max_source_seconds":30, "reference_seconds_used":10,
            "chatterbox_revision":"5de7a54aa4e5e2baadb0182dde554908b48b85c2"}
        if delivery is not None:
            config.update({"original_text":original_text,"delivery":delivery})
        profile = get_profile(voice)
        if profile is not None:
            config["voice_profile"] = profile
        (job / "request.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        (job / "status.json").write_text(json.dumps({"status":"running"}))
        shutil.copyfile(reference, job / ("reference.original" + reference.suffix.lower()))
        prepared_copy(reference, job / "reference.wav", maximum=30, minimum=3, first_seconds=10)
        if mode == "convert":
            shutil.copyfile(source, job / ("source.original" + Path(source).suffix.lower()))
            prepared_copy(source, job / "source.wav", maximum=30)
        attribution = voice_path(profile["attribution"]) if profile is not None else None
        if attribution is not None and attribution.exists():
            shutil.copyfile(attribution, job / "reference-attribution.json")
        with open(job / "worker.log", "w", encoding="utf-8") as log:
            with _process_lock:
                if _cancelled.is_set():
                    raise RuntimeError("Cancelled before inference.")
                _active_process = subprocess.Popen([sys.executable, "-X", "utf8", "-u", str(ROOT / "worker.py"), str(job)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                process = _active_process
            code = wait_owned(process)
            if code:
                error = job / "error.json"
                message = json.loads(error.read_text(encoding="utf-8")).get("error") if error.exists() else f"Worker exited with code {code}."
                raise RuntimeError(message)
        result = json.loads((job / "result.json").read_text(encoding="utf-8"))
        (job / "status.json").write_text(json.dumps({"status":"complete"}))
        with zipfile.ZipFile(job / "comparison.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in job.iterdir():
                if path.suffix in (".wav", ".json"):
                    archive.write(path, path.name)
        return job, result
    except Exception as exc:
        if job is not None:
            (job / "status.json").write_text(json.dumps({"status":"failed", "error":str(exc)}, indent=2))
        raise
    finally:
        with _process_lock:
            if _active_process is not None and _active_process.poll() is None:
                _active_process.kill()
                _active_process.wait(timeout=15)
            _active_process = None
        _job_lock.release()


def inference_running():
    with _process_lock:
        return _active_process is not None and _active_process.poll() is None
