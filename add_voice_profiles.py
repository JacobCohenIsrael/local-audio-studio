"""Prepare remaining US-English references from hash-verified CMU ARCTIC archives."""
from runtime import ROOT, configure
configure()
import hashlib
import io
import json
import re
import tarfile
import time
import requests
import numpy as np
import soundfile as sf

VOICES = [
    ("rms", "American male 2 · RMS", "male", "c6dc11235629c58441c071a7ba8a2d067903dfefbaabc4056d87da35b72ecda4"),
    ("slt", "American female 1 · SLT", "female", "7c173297916acf3cc7fcab2713be4c60b27312316765a90934651d367226b4ea"),
    ("clb", "American female 2 · CLB", "female", "3f16dc3f3b97955ea22623efb33b444341013fc660677b2e170efdcc959fa7c6"),
]

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    folder = ROOT / "voices" / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    downloads = ROOT / "work" / "voice-downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    profiles = []
    for speaker, label, gender, expected in VOICES:
        url = f"http://festvox.org/cmu_arctic/packed/cmu_us_{speaker}_arctic.tar.bz2"
        archive = downloads / f"cmu_us_{speaker}_arctic.tar.bz2"
        if not archive.exists():
            print("Downloading public reference corpus:", speaker, flush=True)
            deadline = time.monotonic() + 180
            with requests.get(url, stream=True, timeout=(15, 30)) as response:
                response.raise_for_status()
                with archive.with_suffix(".partial").open("wb") as target:
                    for chunk in response.iter_content(1024 * 1024):
                        if time.monotonic() > deadline:
                            raise TimeoutError("Reference corpus download exceeded three minutes.")
                        target.write(chunk)
            archive.with_suffix(".partial").replace(archive)
        if sha256(archive) != expected:
            raise ValueError(f"Checksum mismatch for {speaker}. Existing files were retained.")
        texts = {}
        parts, ids = [], []
        sample_rate = None
        # Read selected members directly; never extract archive paths to disk.
        with tarfile.open(archive, "r:bz2") as corpus:
            names = corpus.getnames()
            for name in names:
                if re.search(r"/(COPYING|LICENSE|README)(\.[^/]*)?$", name, re.I):
                    member = corpus.extractfile(name)
                    if member:
                        texts[name.rsplit("/", 1)[-1]] = member.read().decode("utf-8", errors="replace")
            license_items = {k:v for k,v in texts.items() if k.upper().startswith(("COPYING", "LICENSE"))}
            cached_attribution = folder / f"{speaker}-attribution.json"
            if not license_items and cached_attribution.exists():
                texts = json.loads(cached_attribution.read_text(encoding="utf-8"))["documents"]
                license_items = {k:v for k,v in texts.items() if k.upper().startswith(("COPYING", "LICENSE"))}
            if not license_items:
                # The modern audio-only tarballs omit documents. The original
                # distribution directory is linked by CMU's speaker page.
                original = f"http://festvox.org/cmu_arctic/cmu_arctic/cmu_us_{speaker}_arctic/"
                for document in ("COPYING", "AREADME"):
                    response = requests.get(original + document, timeout=20)
                    if document == "AREADME" and response.status_code == 404:
                        continue
                    response.raise_for_status()
                    texts[document] = response.text
                license_items = {"COPYING":texts["COPYING"]}
            if "Permission" not in " ".join(license_items.values()) and "permission" not in " ".join(license_items.values()):
                raise ValueError("Unexpected license document; reference not installed.")
            print("License found:", speaker, list(license_items), flush=True)
            wavs = sorted(n for n in names if re.search(r"/wav/arctic_a\d+\.wav$", n))
            for name in wavs[:10]:
                member = corpus.extractfile(name)
                audio, sr = sf.read(io.BytesIO(member.read()), dtype="float32")
                if audio.ndim == 2:
                    audio = audio.mean(axis=1)
                if sample_rate is not None and sr != sample_rate:
                    raise ValueError("Mixed sample rates in corpus.")
                sample_rate = sr
                parts.append(audio)
                ids.append(name.rsplit("/",1)[-1])
                if sum(len(p) for p in parts) >= 10 * sr:
                    break
        audio = np.concatenate(parts)[:10 * sample_rate]
        if len(audio) < sample_rate * 3 or not np.isfinite(audio).all():
            raise ValueError("Reference audio is invalid.")
        output = folder / f"us_{gender}_{speaker}.wav"
        if output.exists():
            existing, existing_sr = sf.read(output, dtype="float32")
            # An existing profile is preserved, rather than silently replaced.
            if existing_sr != sample_rate or len(existing) != len(audio) or not np.allclose(existing, audio, atol=1/32768):
                raise ValueError(f"Existing profile differs: {output.name}. It was preserved.")
        else:
            sf.write(output, audio, sample_rate, subtype="PCM_16")
        attribution = folder / f"{speaker}-attribution.json"
        details = {"dataset":"CMU ARCTIC", "speaker":speaker, "source":url,
            "source_sha256":expected, "checksum_source":"torchaudio 2.6.0 datasets/cmuarctic.py",
            "speaker_metadata_source":"http://festvox.org/cmu_arctic/",
            "gender":gender, "locale":"en-US", "modifications":"Concatenated initial same-speaker utterances; retained first 10 seconds as PCM WAV.",
            "utterances":ids, "documents":texts, "sha256":sha256(output)}
        attribution.write_text(json.dumps(details,indent=2),encoding="utf-8")
        profiles.append({"id":f"cmu-{speaker}", "label":label, "gender":gender,"locale":"en-US",
            "file":output.relative_to(ROOT).as_posix(), "attribution":attribution.relative_to(ROOT).as_posix(),
            "sha256":sha256(output), "seconds":len(audio)/sample_rate, "source":"CMU ARCTIC",
            "license":"CMU ARCTIC permissive license; text included in attribution"})
        print("Ready profile:", label, len(audio)/sample_rate, "seconds", flush=True)
    (ROOT / "voices" / "profiles.json").write_text(json.dumps(profiles,indent=2),encoding="utf-8")
    print("Three US-source profiles prepared. Rejected BDL files and original demos preserved.", flush=True)

if __name__ == "__main__":
    main()
