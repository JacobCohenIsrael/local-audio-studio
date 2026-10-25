import json
import sys
import types
import numpy as np


def test_batch_loads_one_model_reuses_conditioning_and_keeps_all_outputs(tmp_path,monkeypatch):
    import torch
    import worker
    calls,loads = [],[]

    class Model:
        sr = 24000

        @classmethod
        def from_local(cls,*args):
            loads.append(args)
            return cls()

        def generate(self,text,**kwargs):
            calls.append((text,kwargs))
            return torch.from_numpy(np.sin(np.arange(24000)*0.1).astype("float32")*0.1)

    module = types.ModuleType("chatterbox.tts")
    module.ChatterboxTTS = Model
    monkeypatch.setitem(sys.modules,"chatterbox.tts",module)
    for name,value in {"is_available":lambda:True,"reset_peak_memory_stats":lambda:None,
        "mem_get_info":lambda:(16*1024**3,16*1024**3),"synchronize":lambda:None,
        "max_memory_allocated":lambda:0,"manual_seed_all":lambda seed:None}.items():
        monkeypatch.setattr(torch.cuda,name,value)
    config = {"mode":"tts","seed":42,"radio_preset":"Radio","static_percent":0,
        "items":[{"text":"First line.","delivery":{},"seed":42},{"text":"Second line.","delivery":{},"seed":43}]}
    (tmp_path/"request.json").write_text(json.dumps(config))
    worker.main(tmp_path)
    result = json.loads((tmp_path/"result.json").read_text())
    assert len(loads)==1 and result["model_loads"]==1
    assert [x[0] for x in calls]==["First line.","Second line."]
    assert calls[0][1]["audio_prompt_path"] and calls[1][1]["audio_prompt_path"] is None
    assert [x["seed"] for x in result["items"]]==[42,43]
    assert all((tmp_path/f"item-{i:03d}-{kind}.wav").exists() for i in (1,2) for kind in ("clean","radio"))
