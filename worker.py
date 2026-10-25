"""One bounded GPU job. A TTS batch shares one model, then process exit frees VRAM."""
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


def write_audio_pair(job, stem, wav, sample_rate, config, seed):
    y = safe_level(wav.detach().cpu().numpy().reshape(-1))
    if len(y) / sample_rate > 90 or float(np.sqrt(np.mean(y * y))) < 1e-5:
        raise RuntimeError("Generated audio is too long or nearly silent; retained as a failed job.")
    clean_name, radio_name = stem + "clean.wav", stem + "radio.wav"
    sf.write(job / clean_name, y, sample_rate, subtype="PCM_16")
    radio = radio_effect(y, sample_rate, config["radio_preset"], config["static_percent"], seed)
    sf.write(job / radio_name, radio, sample_rate, subtype="PCM_16")
    return {"seconds":len(y)/sample_rate, "clean":clean_name, "radio":radio_name,
        "clean_peak":float(np.max(np.abs(y))), "radio_peak":float(np.max(np.abs(radio))), "seed":seed}


def main(job):
    config = json.loads((job / "request.json").read_text(encoding="utf-8"))
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Check the project environment before generating.")
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    available, total = torch.cuda.mem_get_info()
    if available < 5 * 1024**3:
        raise RuntimeError("Less than 5 GB of GPU memory is free. Finish other GPU jobs first.")
    started = time.monotonic()
    random.seed(int(config["seed"]))
    np.random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))
    torch.cuda.manual_seed_all(int(config["seed"]))
    checkpoints = ROOT / "models" / "chatterbox"
    if config["mode"] == "convert":
        from chatterbox.vc import ChatterboxVC
        model = ChatterboxVC.from_local(checkpoints, "cuda")
    elif config["mode"] == "tts":
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_local(checkpoints, "cuda")
    else:
        raise ValueError("Unknown job mode.")
    loaded = time.monotonic()
    items = config.get("items") or [{"text":config["text"], "delivery":config.get("delivery",{}), "seed":config["seed"]}]
    results = []
    for index, item in enumerate(items):
        seed = int(item["seed"])
        if index:
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        if config["mode"] == "convert":
            wav = model.generate(audio=str(job / "source.wav"), target_voice_path=str(job / "reference.wav"))
        else:
            delivery = item["delivery"]
            # All lines share a reference. Native generate updates emotion_adv
            # itself, so subsequent lines can reuse its prepared conditionals.
            wav = model.generate(item["text"], audio_prompt_path=str(job / "reference.wav") if index == 0 else None,
                exaggeration=delivery.get("exaggeration",0.5), cfg_weight=delivery.get("cfg_weight",0.5),
                temperature=delivery.get("temperature",0.8))
        torch.cuda.synchronize()
        stem = f"item-{index+1:03d}-" if "items" in config else ""
        results.append(write_audio_pair(job, stem, wav, model.sr, config, seed))
    result = {"status":"complete", "sample_rate":model.sr, "seconds":sum(r["seconds"] for r in results),
        "inference_seconds":round(time.monotonic()-started, 3), "model_load_seconds":round(loaded-started,3),
        "generation_seconds":round(time.monotonic()-loaded,3), "model_loads":1, "items":results,
        "peak_gpu_allocated_mib":round(torch.cuda.max_memory_allocated()/1024**2, 1),
        "gpu_free_before_mib":round(available/1024**2, 1),
        "watermark":"Chatterbox applies its upstream Perth watermark before the radio effect.",
        "quality":"Requires human listening; file and signal checks do not establish voice similarity."}
    if len(results) == 1:
        result.update({k:results[0][k] for k in ("clean_peak","radio_peak")})
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
