"""One bounded inference request. Process exit releases this job's GPU memory."""
from runtime import ROOT, configure
configure(offline=True)
import json
import random
import sys
import time
import traceback
from pathlib import Path
import numpy as np
import soundfile as sf
from effects import radio_effect, safe_level

def main(job):
    config = json.loads((job / "request.json").read_text(encoding="utf-8"))
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Check the project environment before generating.")
    torch.set_num_threads(4)
    seed = int(config["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.reset_peak_memory_stats()
    available, total = torch.cuda.mem_get_info()
    if available < 5 * 1024**3:
        raise RuntimeError("Less than 5 GB of GPU memory is free. Finish other GPU jobs first.")
    started = time.monotonic()
    checkpoints = ROOT / "models" / "chatterbox"
    if config["mode"] == "convert":
        from chatterbox.vc import ChatterboxVC
        model = ChatterboxVC.from_local(checkpoints, "cuda")
        wav = model.generate(audio=str(job / "source.wav"), target_voice_path=str(job / "reference.wav"))
    elif config["mode"] == "tts":
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_local(checkpoints, "cuda")
        delivery = config.get("delivery", {})
        wav = model.generate(config["text"], audio_prompt_path=str(job / "reference.wav"),
            exaggeration=delivery.get("exaggeration",0.5), cfg_weight=delivery.get("cfg_weight",0.5),
            temperature=delivery.get("temperature",0.8))
    else:
        raise ValueError("Unknown job mode.")
    torch.cuda.synchronize()
    y = safe_level(wav.detach().cpu().numpy().reshape(-1))
    if len(y) / model.sr > 90 or float(np.sqrt(np.mean(y * y))) < 1e-5:
        raise RuntimeError("Generated audio is too long or nearly silent; retained as a failed job.")
    sf.write(job / "clean.wav", y, model.sr, subtype="PCM_16")
    radio = radio_effect(y, model.sr, config["radio_preset"], config["static_percent"], seed)
    sf.write(job / "radio.wav", radio, model.sr, subtype="PCM_16")
    result = {"status":"complete", "sample_rate":model.sr, "seconds":len(y)/model.sr,
        "inference_seconds":round(time.monotonic()-started, 3),
        "peak_gpu_allocated_mib":round(torch.cuda.max_memory_allocated()/1024**2, 1),
        "gpu_free_before_mib":round(available/1024**2, 1),
        "clean_peak":float(np.max(np.abs(y))), "radio_peak":float(np.max(np.abs(radio))),
        "watermark":"Chatterbox applies its upstream Perth watermark before the radio effect.",
        "quality":"Requires human listening; file and signal checks do not establish voice similarity."}
    (job / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)

if __name__ == "__main__":
    job = Path(sys.argv[1]).resolve()
    if job.parent != (ROOT / "outputs").resolve():
        raise ValueError("Worker job must belong to this project's outputs folder.")
    try:
        main(job)
    except Exception as exc:
        (job / "error.json").write_text(json.dumps({"status":"failed", "error":str(exc)}, indent=2))
        traceback.print_exc()
        sys.exit(1)
