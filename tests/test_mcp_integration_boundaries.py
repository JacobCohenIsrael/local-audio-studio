import io
import json
from pathlib import Path
import pytest
from filelock import FileLock, Timeout
import mcp_connection
import studio


def test_bridge_refuses_another_checkouts_service(monkeypatch):
    health={"service":"local-audio-studio","mcp":True,"project_root":"different checkout"}
    monkeypatch.setattr(mcp_connection,"urlopen",lambda *a,**k:io.BytesIO(json.dumps(health).encode()))
    with pytest.raises(RuntimeError,match="different service/check-out"):
        mcp_connection.check_service()


def test_browser_generation_uses_the_same_manager(monkeypatch,tmp_path):
    import app
    calls=[]

    class Manager:
        def submit(self,mode,**kwargs):
            calls.append((mode,kwargs))
            return {"job_id":"example-job"}

        def wait_finished(self,job_id):
            assert job_id=="example-job"
            return tmp_path,{"seconds":1.2,"inference_seconds":2.3}

    monkeypatch.setattr(app,"jobs",Manager())
    result=app.create("convert","input.wav","Female demo voice",None,"","Radio",0.3,42,progress=lambda *a,**k:None)
    assert calls[0][0]=="convert" and calls[0][1]["source"]=="input.wav"
    assert result[:3]==(str(tmp_path/"clean.wav"),str(tmp_path/"radio.wav"),str(tmp_path/"comparison.zip"))


def test_another_process_gpu_lock_blocks_inference_before_spawning(tmp_path,monkeypatch):
    (tmp_path/"work").mkdir()
    monkeypatch.setattr(studio,"ROOT",tmp_path)
    with FileLock(tmp_path/"work"/"gpu.lock"):
        with pytest.raises(Timeout):
            studio.run_job("tts",None,"Male demo voice",None,text="Hello.")
    assert not studio._job_lock.locked()
    assert not (tmp_path/"outputs").exists()
