import asyncio
from contextlib import asynccontextmanager
import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jobs import JobManager
from mcp_api import create_mcp


@pytest.fixture
def client(tmp_path):
    jobs = JobManager(tmp_path)
    server,transport = create_mcp(jobs,token="test-token-"*4)

    @asynccontextmanager
    async def lifespan(app):
        jobs.start()
        try:
            async with server.session_manager.run():
                yield
        finally:
            await asyncio.to_thread(jobs.close)

    app = FastAPI(lifespan=lifespan)
    app.mount("/agent",transport)
    with TestClient(app,base_url="http://127.0.0.1:7865") as c:
        yield c,jobs


def rpc(client,method,arguments=None,headers=None):
    return client.post("/agent/mcp",headers={"Authorization":"Bearer "+"test-token-"*4,
        "Accept":"application/json, text/event-stream",**(headers or {})},json={"jsonrpc":"2.0","id":1,"method":method,"params":arguments or {}})


def call(client,name,arguments=None):
    response = rpc(client,"tools/call",{"name":name,"arguments":arguments or {}})
    assert response.status_code==200,response.text
    return response.json()["result"]


def test_mcp_auth_and_dns_rebinding_protection(client):
    c,jobs = client
    assert c.post("/agent/mcp",json={}).status_code==401
    assert rpc(c,"tools/list",headers={"Host":"evil.invalid:7865"}).status_code==421
    assert rpc(c,"tools/list",headers={"Origin":"https://evil.invalid"}).status_code==403
    assert jobs.stats()["outstanding"]==0


def test_mcp_lists_tools_and_status_without_gpu_work(client):
    c,jobs = client
    response = rpc(c,"tools/list")
    assert response.status_code==200,response.text
    tools = response.json()["result"]["tools"]
    assert {t["name"] for t in tools}=={"audio_service_status","list_audio_voices","generate_speech","generate_speech_batch","convert_voice","apply_radio_effect","get_audio_job","cancel_audio_job","generate_sound_effects"}
    status = call(c,"audio_service_status")["structuredContent"]
    assert status["queue"]["outstanding"]==0
    assert status["gpu_deadline_seconds"]==300


def test_mcp_real_cpu_radio_round_trip(client,tmp_path):
    c,jobs = client
    path = tmp_path/"source.wav"
    sf.write(path,np.sin(np.arange(24000)*0.1)*0.1,24000)
    submitted = call(c,"apply_radio_effect",{"source_path":str(path),"request_id":"mcp-radio-test"})
    assert not submitted.get("isError"),submitted
    ticket = submitted["structuredContent"]
    state = call(c,"get_audio_job",{"job_id":ticket["job_id"],"wait_seconds":3})["structuredContent"]
    assert state["status"]=="complete"
    assert state["result"]["gpu_used"] is False
    assert {a["name"] for a in state["artifacts"]}=={"clean.wav","radio.wav","comparison.zip"}


def test_mcp_rejects_bad_requests_before_creating_jobs(client):
    c,jobs = client
    failed = call(c,"generate_speech_batch",{"texts":["Hello"]*9})
    assert failed["isError"]
    assert call(c,"generate_speech",{"text":"Hello","voice_id":"cmu-bdl"})["isError"]
    assert call(c,"get_audio_job",{"job_id":"../server.json"})["isError"]
    assert jobs.stats()["outstanding"]==0


def test_mcp_sound_effects_batch_round_trip(client):
    c,jobs = client
    submitted = call(c,"generate_sound_effects",{"effects":[
        {"effect":"explosion","duration":.25}, {"effect":"laser","duration":.25},
        {"effect":"plasma","duration":.25}], "request_id":"mcp-sfx-batch-test"})
    assert not submitted.get("isError"), submitted
    ticket = submitted["structuredContent"]
    state = call(c,"get_audio_job",{"job_id":ticket["job_id"],"wait_seconds":5})["structuredContent"]
    assert state["status"] == "complete", state
    assert len(state["artifacts"]) == 4
    assert state["result"]["gpu_used"] is False
    assert call(c,"generate_sound_effects",{"effects":[{"effect":"laser","duration":10}]})["isError"]
