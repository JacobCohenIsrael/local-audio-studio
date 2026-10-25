import hashlib
import threading
import zipfile
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from jobs import JobManager, local_audio


@pytest.fixture
def source(tmp_path):
    path = tmp_path/"line.wav"
    sf.write(path,np.sin(np.arange(24000)*0.1)*0.1,24000)
    return path


def test_queue_capacity_idempotency_and_cancellation_are_job_scoped(tmp_path, source):
    entered = threading.Event()

    def runner(record,cancel):
        entered.set()
        cancel.wait(5)
        return tmp_path/"outputs"/record["job_id"],{"status":"complete"}

    jobs = JobManager(tmp_path,capacity=2,runner=runner)
    try:
        first = jobs.submit("radio",source=source,request_id="first-request")
        assert entered.wait(2)
        second = jobs.submit("radio",source=source,request_id="second-request")
        assert jobs.submit("radio",source=source,request_id="second-request")["job_id"]==second["job_id"]
        with pytest.raises(ValueError,match="different inputs"):
            jobs.submit("radio",source=source,static=1,request_id="second-request")
        with pytest.raises(RuntimeError,match="full"):
            jobs.submit("radio",source=source)
        jobs.cancel(second["job_id"])
        assert jobs.get(second["job_id"])["status"]=="cancelled"
        assert not jobs.events[first["job_id"]].is_set()
        jobs.cancel(first["job_id"])
        assert jobs.get(first["job_id"],wait_seconds=2)["status"]=="cancelled"
    finally:
        jobs.close()


def test_input_snapshot_survives_source_changes_and_cpu_radio_needs_no_model(tmp_path, source):
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    jobs = JobManager(tmp_path)
    try:
        ticket = jobs.submit("radio",source=source,request_id="snapshot-test")
        staged = Path(jobs.records[ticket["job_id"]]["payload"]["source"])
        assert hashlib.sha256(staged.read_bytes()).hexdigest()==expected
        source.write_bytes(b"changed after submission")
        state = jobs.get(ticket["job_id"],wait_seconds=3)
        assert state["status"]=="complete" and state["result"]["gpu_used"] is False
        assert {a["name"] for a in state["artifacts"]}=={"clean.wav","radio.wav","comparison.zip"}
        with zipfile.ZipFile(tmp_path/"outputs"/ticket["job_id"]/"comparison.zip") as archive:
            assert "comparison.zip" not in archive.namelist()
            assert {"clean.wav","radio.wav","source.original.wav","request.json","result.json"}==set(archive.namelist())
        assert hashlib.sha256(staged.read_bytes()).hexdigest()==expected
    finally:
        jobs.close()


def test_restart_marks_unfinished_job_interrupted_without_retry(tmp_path):
    import json
    folder = tmp_path/"work"/"agent-jobs"
    folder.mkdir(parents=True)
    job_id = "20261025T000000Z-1234abcd"
    (folder/(job_id+".json")).write_text(json.dumps({"job_id":job_id,"status":"running","mode":"tts","payload":{},"fingerprint":"abc","request_id":"restart-test"}))
    jobs = JobManager(tmp_path,runner=lambda *a: pytest.fail("An interrupted job must never be retried"))
    try:
        jobs.start()
        assert jobs.get(job_id)["status"]=="interrupted"
        assert not jobs.futures
        with pytest.raises(ValueError,match="Unknown"):
            jobs.get("../private")
    finally:
        jobs.close()


def test_urls_and_network_shares_are_not_inputs():
    with pytest.raises(ValueError,match="local audio"):
        local_audio("\\\\server\\private.wav")
