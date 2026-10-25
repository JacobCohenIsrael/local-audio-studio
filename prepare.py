"""Download pinned public models and three attributed listening samples."""
from runtime import ROOT, configure
configure()
import hashlib
import io
import json
import shutil
from pathlib import Path
import requests
import numpy as np
import soundfile as sf
import imageio_ffmpeg
from huggingface_hub import hf_hub_download

REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
FILES = ["s3gen.safetensors", "t3_cfg.safetensors", "ve.safetensors", "tokenizer.json", "README.md"]
def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def models():
    folder = ROOT / "models" / "chatterbox"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {"repository": "ResembleAI/chatterbox", "revision": REVISION, "license": "MIT", "files": {}}
    for name in FILES:
        path = Path(hf_hub_download("ResembleAI/chatterbox", name, revision=REVISION, local_dir=folder))
        manifest["files"][name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        print("Ready:", name, path.stat().st_size, flush=True)
    (ROOT / "models" / "manifest.json").write_text(json.dumps(manifest, indent=2))
    bindir = ROOT / "work" / "bin"
    bindir.mkdir(exist_ok=True)
    shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(), bindir / "ffmpeg.exe")

def samples():
    destination = ROOT / "voices"
    destination.mkdir(exist_ok=True)
    metadata = requests.get("https://raw.githubusercontent.com/oscarknagg/voicemap/master/data/LibriSpeech/SPEAKERS.TXT", timeout=45)
    metadata.raise_for_status()
    (destination / "SPEAKERS.TXT").write_text(metadata.text, encoding="utf-8")
    speakers = {int(line.split("|")[0]): line.strip() for line in metadata.text.splitlines()
                if "|" in line and line.split("|")[0].strip().isdigit()}
    manifest = {"dataset": "openslr/librispeech_asr", "config": "clean", "split": "test",
        "license": "CC-BY-4.0", "url": "https://www.openslr.org/12",
        "attribution": "LibriSpeech: Vassil Panayotov, Guoguo Chen, Daniel Povey, Sanjeev Khudanpur; LibriVox volunteer readers listed in SPEAKERS.TXT.",
        "modifications": "Decoded FLAC to mono PCM WAV. Target references concatenate adjacent same-speaker clips and retain the first 10 seconds.",
        "samples": {}}
    for role, offset, sex in [("source", 0, "M"), ("male", 100, "M"), ("female", 400, "F")]:
        response = requests.get("https://datasets-server.huggingface.co/rows",
            params={"dataset":"openslr/librispeech_asr", "config":"clean", "split":"test", "offset":offset, "length":3}, timeout=45)
        response.raise_for_status()
        rows = response.json()["rows"]
        parts, items = [], []
        speaker_id = rows[0]["row"]["speaker_id"]
        assert speakers[speaker_id].split("|")[1].strip() == sex
        for row in rows:
            item = row["row"]
            if item["speaker_id"] != speaker_id:
                break
            audio = requests.get(item["audio"][0]["src"], timeout=45)
            audio.raise_for_status()
            raw = destination / (item["id"] + ".flac")
            raw.write_bytes(audio.content)
            y, sr = sf.read(io.BytesIO(audio.content), dtype="float32")
            assert sr == 16000 and y.ndim == 1
            parts.append(y)
            items.append({"id":item["id"], "text":item["text"], "sha256":digest(raw), "dataset_row":row["row_idx"]})
        y = np.concatenate(parts)
        y = y[:int((12 if role == "source" else 10) * sr)]
        path = (ROOT / "inputs" / "demo-source.wav") if role == "source" else (destination / (role + ".wav"))
        path.parent.mkdir(exist_ok=True)
        sf.write(path, y, sr, subtype="PCM_16")
        manifest["samples"][role] = {"file":str(path.relative_to(ROOT)), "speaker_id":speaker_id, "gender_metadata":sex,
            "seconds":len(y)/sr, "items":items, "sha256":digest(path)}
        print("Ready sample:", role, len(y)/sr, "seconds", flush=True)
    (destination / "attribution.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Sample preparation complete.", flush=True)

if __name__ == "__main__":
    import sys
    if "--samples-only" not in sys.argv:
        models()
    if "--models-only" not in sys.argv:
        samples()
