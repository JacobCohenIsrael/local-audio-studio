"""Authenticated loopback MCP tools; all clients share the browser's job queue."""
import asyncio
import hmac
from typing import Any
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from voice_profiles import PROFILES, CUSTOM_VOICE, voice_path
from delivery import TONE_CHOICES
from effects import PRESETS
from mcp_connection import read_token

INSTRUCTIONS = (
    "Local Audio Studio: list voices, submit speech/conversion/radio jobs, then wait with get_audio_job. "
    "Use generate_speech_batch for up to 8 lines sharing one model load. One shared queue, at most 4 outstanding jobs; "
    "GPU workers stop after 300 seconds. Pass a unique request_id and reuse it only for the same request. "
    "Never automatically retry failed/interrupted jobs. Outputs are local files; listen before claiming quality. "
    "Microphone capture stays in the browser UI."
)


class BearerAuth:
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"]=="http":
            headers = dict(scope["headers"])
            expected = ("Bearer "+self.token).encode()
            if not hmac.compare_digest(headers.get(b"authorization",b""),expected):
                await send({"type":"http.response.start","status":401,
                    "headers":[(b"content-type",b"application/json"),(b"www-authenticate",b"Bearer")]})
                await send({"type":"http.response.body","body":b'{"error":"Local MCP bearer token required"}'})
                return
        await self.app(scope,receive,send)


def create_mcp(jobs, token=None):
    server = MCPServer("Local Audio Studio",version="1.0.0",instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
    writes = ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)

    def voice_label(voice_id, custom_reference):
        if voice_id=="custom":
            if not custom_reference:
                raise ValueError("custom_reference is required for voice_id=custom (3–30 seconds).")
            return CUSTOM_VOICE
        profile = next((p for p in PROFILES if p["id"]==voice_id),None)
        if profile is None:
            raise ValueError("Unknown voice_id; use list_audio_voices first.")
        if custom_reference:
            raise ValueError("Use voice_id=custom when supplying a custom_reference.")
        return profile["label"]

    @server.tool(annotations=read_only)
    async def audio_service_status() -> dict[str,Any]:
        """Check queue capacity and limits without loading a model or allocating GPU memory."""
        return {"service":"local-audio-studio","queue":jobs.stats(),"gpu_deadline_seconds":300,
            "max_batch_lines":8,"max_batch_characters":1200,"source_seconds":[0.5,30],
            "reference_seconds":[3,30],"tones":TONE_CHOICES,"radio_presets":list(PRESETS),
            "model_residency":"One load per job/batch; process exits and releases VRAM afterward."}

    @server.tool(annotations=read_only)
    async def list_audio_voices() -> dict[str,Any]:
        """List stable voice IDs. RMS/SLT Natural-tone TTS samples passed owner listening; BDL is excluded."""
        return {"voices":[{"id":p["id"],"label":p["label"],"gender":p["gender"],"locale":p["locale"],
            "reference_path":str(voice_path(p["file"])),"accepted_natural_tts_sample":p["id"] in {"cmu-rms","cmu-slt"}}
            for p in PROFILES],"custom_voice_id":"custom","note":"Acceptance applies to the tested samples, not all text or expression settings."}

    async def submit(mode, voice_id, custom_reference, **kwargs):
        return await asyncio.to_thread(jobs.submit,mode,voice=voice_label(voice_id,custom_reference),custom=custom_reference,**kwargs)

    @server.tool(annotations=writes)
    async def generate_speech(text: str, voice_id: str="cmu-rms", tone: str="Natural", radio_preset: str="Radio",
                              static_percent: float=0.3, seed: int=42, request_id: str|None=None,
                              custom_reference: str|None=None) -> dict[str,Any]:
        """Queue English TTS (1–300 spoken characters). Returns immediately with job_id; fetch clean/radio paths using get_audio_job."""
        return await submit("tts",voice_id,custom_reference,text=text,tone=tone,preset=radio_preset,static=static_percent,seed=seed,request_id=request_id)

    @server.tool(annotations=writes)
    async def generate_speech_batch(texts: list[str], voice_id: str="cmu-rms", tone: str="Natural", radio_preset: str="Radio",
                                    static_percent: float=0.3, seed: int=42, request_id: str|None=None,
                                    custom_reference: str|None=None) -> dict[str,Any]:
        """Queue 1–8 lines, each <=300 spoken characters, <=1200 characters total. One shared TTS model/reference load; seed increments per line. Whole batch has a 300-second deadline."""
        return await submit("tts",voice_id,custom_reference,texts=texts,tone=tone,preset=radio_preset,static=static_percent,seed=seed,request_id=request_id)

    @server.tool(annotations=writes)
    async def convert_voice(source_path: str, voice_id: str="cmu-rms", radio_preset: str="Radio", static_percent: float=0.3,
                            seed: int=42, request_id: str|None=None, custom_reference: str|None=None) -> dict[str,Any]:
        """Queue reference-conditioned voice conversion of a local 0.5–30 second audio file. Preserves performance; can retain source accent. Not pitch shifting."""
        return await submit("convert",voice_id,custom_reference,source=source_path,preset=radio_preset,static=static_percent,seed=seed,request_id=request_id)

    @server.tool(annotations=writes)
    async def apply_radio_effect(source_path: str, radio_preset: str="Radio", static_percent: float=0.3,
                                 seed: int=42, request_id: str|None=None) -> dict[str,Any]:
        """Queue CPU-only radio filtering of a local audio file up to 90 seconds; keeps a clean copy. No speech regeneration or GPU model load."""
        return await asyncio.to_thread(jobs.submit,"radio",source=source_path,preset=radio_preset,static=static_percent,seed=seed,request_id=request_id)

    @server.tool(annotations=read_only)
    async def get_audio_job(job_id: str, wait_seconds: float=0) -> dict[str,Any]:
        """Get queued/running/complete/failed/cancelled/interrupted state and local artifact paths. Wait 0–10 seconds for completion to avoid rapid polling. Partial files from failed jobs aren't quality-approved."""
        return await asyncio.to_thread(jobs.get,job_id,wait_seconds)

    @server.tool(annotations=writes)
    async def cancel_audio_job(job_id: str) -> dict[str,Any]:
        """Cancel only the specified queued/running audio job. Retains inputs and partial outputs; other jobs continue."""
        return jobs.cancel(job_id)

    transport = server.streamable_http_app(streamable_http_path="/mcp",stateless_http=True,json_response=True,max_request_body_size=65536)
    return server,BearerAuth(transport,token or read_token())
