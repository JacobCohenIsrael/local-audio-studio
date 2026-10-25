"""Reference profiles are data, with paths constrained to the voice library."""
import json
from pathlib import Path
from runtime import ROOT

CUSTOM_VOICE = "My reference recording"
# Retain rejected reference data and jobs, but never offer it after setup/restart.
REJECTED_PROFILE_IDS = {"cmu-bdl"}
BASE_PROFILES = [
    {"id":"demo-male", "label":"Male demo voice", "gender":"male", "locale":"English; accent unspecified", "file":"voices/male.wav", "attribution":"voices/attribution.json"},
    {"id":"demo-female", "label":"Female demo voice", "gender":"female", "locale":"English; accent unspecified", "file":"voices/female.wav", "attribution":"voices/attribution.json"},
]

def voice_path(relative, root=ROOT):
    path = (root / relative).resolve()
    path.relative_to((root / "voices").resolve())
    return path

def load_profiles(manifest=None, root=ROOT):
    result = [dict(profile) for profile in BASE_PROFILES]
    manifest = manifest or root / "voices" / "profiles.json"
    if manifest.exists():
        for profile in json.loads(manifest.read_text(encoding="utf-8")):
            if profile.get("id") in REJECTED_PROFILE_IDS:
                continue
            if profile["label"] == CUSTOM_VOICE or any(p["label"] == profile["label"] for p in result):
                raise ValueError("Duplicate voice profile name.")
            path = voice_path(profile["file"], root)
            voice_path(profile["attribution"], root)
            if path.is_file():
                result.append(dict(profile))
    return result

PROFILES = load_profiles()
VOICE_CHOICES = [profile["label"] for profile in PROFILES] + [CUSTOM_VOICE]

def get_profile(label):
    return next((dict(p) for p in PROFILES if p["label"] == label), None)
