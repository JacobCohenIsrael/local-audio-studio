from pathlib import Path
import json
import pytest
from delivery import prepare_delivery
from voice_profiles import CUSTOM_VOICE, load_profiles


def test_direction_is_not_spoken_and_punctuation_is_preserved():
    text, settings = prepare_delivery("[Yelling panically] Incoming!!!")
    assert text == "Incoming!!!"
    assert settings["preset"] == "Urgent / panicked"
    assert settings["exaggeration"] > prepare_delivery("Incoming!!!")[1]["exaggeration"]


def test_unrecognized_directions_are_rejected_instead_of_read_aloud():
    with pytest.raises(ValueError, match="Unsupported direction"):
        prepare_delivery("[Do a perfect movie impression] Hello")
    with pytest.raises(ValueError, match="one supported direction"):
        prepare_delivery("Hello [Yelling] there")


def test_tone_and_text_limits():
    spoken, settings = prepare_delivery("Stay calm.", "Calm")
    assert spoken == "Stay calm." and settings["preset"] == "Calm"
    with pytest.raises(ValueError, match="spoken characters"):
        prepare_delivery("[Calm]")
    with pytest.raises(ValueError, match="spoken characters"):
        prepare_delivery("a" * 301)


def test_reference_registry_rejects_paths_outside_voice_library(tmp_path):
    manifest = tmp_path / "profiles.json"
    manifest.write_text(json.dumps([{"label":"Bad profile", "file":"../private.wav", "attribution":"voices/credits.json"}]))
    with pytest.raises(ValueError):
        load_profiles(manifest, root=tmp_path)


def test_reference_registry_does_not_shadow_custom_reference(tmp_path):
    manifest = tmp_path / "profiles.json"
    manifest.write_text(json.dumps([{"label":CUSTOM_VOICE,"file":"voices/example.wav","attribution":"voices/credits.json"}]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_profiles(manifest, root=tmp_path)
