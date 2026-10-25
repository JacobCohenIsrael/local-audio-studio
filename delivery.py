"""App-level delivery cues mapped to real Chatterbox controls, not native tags."""
import re

PRESETS = {
    "Natural": {"exaggeration":0.5, "cfg_weight":0.5, "temperature":0.8},
    "Calm": {"exaggeration":0.25, "cfg_weight":0.5, "temperature":0.65},
    "Excited": {"exaggeration":0.8, "cfg_weight":0.3, "temperature":0.85},
    "Urgent / panicked": {"exaggeration":1.0, "cfg_weight":0.25, "temperature":0.85},
    "Forceful / angry": {"exaggeration":0.9, "cfg_weight":0.3, "temperature":0.8},
}
TONE_CHOICES = list(PRESETS)
DIRECTIONS = {
    "yelling panically":"Urgent / panicked", "panicked":"Urgent / panicked",
    "panicky":"Urgent / panicked", "urgent":"Urgent / panicked",
    "yelling":"Forceful / angry", "angry":"Forceful / angry", "forceful":"Forceful / angry",
    "calm":"Calm", "calmly":"Calm", "excited":"Excited", "excitedly":"Excited", "natural":"Natural",
}

def prepare_delivery(text, tone="Natural"):
    if tone not in PRESETS:
        raise ValueError("Choose a listed tone preset.")
    spoken = text.strip()
    direction = None
    match = re.match(r"^\[([^\]]{1,70})\]\s*(.*)$", spoken, flags=re.DOTALL)
    if match:
        direction = " ".join(match[1].lower().split())
        if direction not in DIRECTIONS:
            raise ValueError("Unsupported direction. Try [Yelling panically], [Excited], [Calm], or choose a tone preset.")
        tone = DIRECTIONS[direction]
        spoken = match[2].strip()
    if not spoken or len(spoken) > 300:
        raise ValueError("Enter between 1 and 300 spoken characters after any direction.")
    if "[" in spoken or "]" in spoken:
        raise ValueError("Use one supported direction at the beginning, followed by the spoken dialogue.")
    return spoken, {"preset":tone, "direction":direction, **PRESETS[tone],
        "method":"Chatterbox exaggeration/CFG/temperature approximation; exact emotion or yelling is not guaranteed."}
