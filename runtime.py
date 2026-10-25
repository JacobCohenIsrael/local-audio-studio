"""All caches and temporary files belong to this audio project."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def configure(offline=False):
    paths = {
        "HF_HOME": ROOT / "models" / "huggingface",
        "TORCH_HOME": ROOT / "models" / "torch",
        "XDG_CACHE_HOME": ROOT / "work" / "cache",
        "NUMBA_CACHE_DIR": ROOT / "work" / "numba",
        "GRADIO_TEMP_DIR": ROOT / "work" / "gradio",
        "MPLCONFIGDIR": ROOT / "work" / "matplotlib",
    }
    for key, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "4"
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    bin_dir = ROOT / "work" / "bin"
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
