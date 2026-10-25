"""Local recording and A/B listening interface for Chatterbox."""
from runtime import ROOT, configure
configure(offline=True)
import json
import os
import secrets
import threading
import time
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import gradio as gr
from fastapi import FastAPI, Header, HTTPException
import uvicorn
from studio import VOICE_CHOICES, stop_active
from voice_profiles import CUSTOM_VOICE, PROFILES
from delivery import TONE_CHOICES
from recorder import recorder
from jobs import JobManager
from mcp_api import create_mcp

PORT = int(os.environ.get("LOCAL_AUDIO_PORT", "7865"))
jobs = JobManager()
mcp, mcp_transport = create_mcp(jobs)


@asynccontextmanager
async def lifespan(app):
    jobs.start()
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        await asyncio.to_thread(jobs.close)


app = FastAPI(lifespan=lifespan)
app.mount("/agent",mcp_transport)
STOP_TOKEN = secrets.token_urlsafe(32)

@app.get("/healthz")
def health():
    from studio import inference_running
    return {"recording_active":recorder.snapshot()["recording"], "inference_running":inference_running(), "service":"local-audio-studio","status":"ready","pid":os.getpid(),
        "mcp":True,"project_root":str(ROOT),"queue":jobs.stats(),
        "note":"Inference runs in a separate worker; readiness is not a generation test."}

@app.post("/local/stop")
def shutdown(x_local_audio_token: str = Header(default="")):
    if not secrets.compare_digest(x_local_audio_token, STOP_TOKEN):
        raise HTTPException(status_code=403)
    jobs.close(wait=False)
    stop_active()
    if recorder.stream is not None:
        recorder.stop()
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"status":"stopping"}

def recording_updates(last_seen):
    state = recorder.snapshot()
    changed = state["path"] and state["path"] != last_seen
    source_update = gr.update(interactive=not state["recording"])
    if changed:
        source_update["value"] = state["path"]
        last_seen = state["path"]
    return (source_update, state["message"], state["level"],
            gr.update(interactive=not state["recording"]),
            gr.update(interactive=state["recording"]),
            gr.update(interactive=not state["recording"]),
            gr.update(interactive=not state["recording"]),
            gr.update(active=state["recording"]), last_seen)


def start_recording(device, last_seen):
    try:
        recorder.start(device)
        return recording_updates(last_seen)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

def stop_recording(last_seen):
    try:
        recorder.stop()
        return recording_updates(last_seen)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc


def restore_recording():
    path = recorder.snapshot()["path"]
    if not path:
        raise gr.Error("No saved microphone recording yet. Press Record first.")
    return path, "Last saved microphone recording loaded. Press Play below to check it."

def voice_preview(choice):
    from studio import choose_reference
    if choice == CUSTOM_VOICE:
        return None
    return str(choose_reference(choice))


def conversion_voice_selection(choice):
    return voice_preview(choice), gr.update(visible=choice == CUSTOM_VOICE)

def create(mode, source, voice, custom, text, preset, static, seed, progress=gr.Progress(), tone="Natural"):
    progress(0.05, desc="Preparing your recording")
    try:
        progress(0.1, desc="Converting on your GPU. You can cancel below.")
        ticket = jobs.submit(mode,source=source,voice=voice,custom=custom,text=text,preset=preset,static=static,seed=int(seed),tone=tone)
        progress(0.15, desc="Waiting in the shared audio queue")
        job, result = jobs.wait_finished(ticket["job_id"])
        progress(1, desc="Ready to compare")
        status = (f"Saved {job.name} · {result['seconds']:.1f} seconds of audio · "
                  f"{result['inference_seconds']:.1f} seconds to load and generate. "
                  "Listen to the clean result first. GPU worker has stopped.")
        return str(job / "clean.wav"), str(job / "radio.wav"), str(job / "comparison.zip"), status
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

def convert(source, voice, custom, preset, static, seed, progress=gr.Progress()):
    return create("convert",source,voice,custom,"",preset,static,seed,progress)

def speak(text, voice, custom, preset, static, seed, tone="Natural", progress=gr.Progress()):
    return create("tts",None,voice,custom,text,preset,static,seed,progress,tone=tone)

def quality_samples():
    try:
        report = json.loads((ROOT / "work" / "quality-check.json").read_text(encoding="utf-8"))
        runs = report["runs"]
        male = next(x for x in runs if x["voice"]==VOICE_CHOICES[0] and x["mode"]=="convert")
        female = next(x for x in runs if x["voice"]==VOICE_CHOICES[1] and x["mode"]=="convert")
        files = [ROOT / male["folder"] / "clean.wav", ROOT / male["folder"] / "radio.wav",
                 ROOT / female["folder"] / "clean.wav", ROOT / female["folder"] / "radio.wav"]
        return [str(p) if p.exists() else None for p in files]
    except (OSError, KeyError, StopIteration):
        return [None]*4

def recording_comparison():
    """Load the owner's comparison without replacing the public sample test."""
    manifest = ROOT / "work" / "recording-comparison.json"
    if not manifest.exists():
        return [None] * 6 + ["No saved recording comparison yet."]
    report = json.loads(manifest.read_text(encoding="utf-8"))
    keys = ["original", "male_clean", "male_radio", "female_clean", "female_radio", "download"]
    paths = []
    for key in keys:
        path = (ROOT / report[key]).resolve()
        path.relative_to((ROOT / "outputs").resolve())
        paths.append(str(path) if path.is_file() else None)
    return paths + [f"Your {report['source_seconds']:.1f}-second recording, converted with both target voices. Radio preset: {report['radio_preset']}; static: {report['static_percent']}%. Listen to clean versions first."]


with gr.Blocks(title="Local Audio Studio") as demo:
    gr.Markdown("# Local Audio Studio\nRecord a performance, choose a voice, and compare clean speech with a radio version. Everything runs on this PC.")
    with gr.Tabs():
        with gr.Tab("Record & change voice"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 1 · Record")
                    gr.Markdown("Press **Record**, speak, then **Stop recording**. Short lines are welcome.")
                    with gr.Accordion("Microphone settings",open=False):
                        device = gr.Dropdown(recorder.devices(),value=-1,label="PC microphone")
                    with gr.Row():
                        pc_start = gr.Button("Record")
                        pc_stop = gr.Button("Stop recording",interactive=False)
                    recording_status = gr.Textbox(value=recorder.snapshot()["message"],label="Recording status",interactive=False)
                    input_level = gr.Slider(0,100,value=0,label="Live microphone input level",interactive=False)
                    last_recording = recorder.snapshot()["path"]
                    recording_seen = gr.State(last_recording)
                    recording_timer = gr.Timer(0.3,active=False)
                    source = gr.Audio(buttons=["download"],sources=["upload"],value=last_recording,type="filepath",format="wav",
                        label="Your recording · or upload a clip")
                    with gr.Accordion("More recording options",open=False):
                        restore = gr.Button("Load last microphone recording")
                        sample = gr.Button("Try the sample recording")
                    restore.click(restore_recording,outputs=[source,recording_status],queue=False,api_name=False)
                    sample.click(lambda: str(ROOT/"inputs"/"demo-source.wav"),outputs=source,queue=False,api_name=False)
                    gr.Markdown("### 2 · Choose a voice")
                    voice = gr.Dropdown(VOICE_CHOICES,value=VOICE_CHOICES[1],label="Voice")
                    with gr.Accordion("Hear the selected voice",open=False):
                        preview = gr.Audio(buttons=["download"],value=str(ROOT/"voices"/"female.wav"),label="Voice preview",interactive=False,type="filepath")
                    with gr.Column(visible=False) as custom_options:
                        gr.Markdown("Upload a separate sample of the voice you want to copy. This sample needs 3–30 seconds; your dialogue recording above can be shorter.")
                        custom = gr.Audio(buttons=["download"],sources=["upload"],type="filepath",format="wav",
                            label="Voice sample to copy · 3–30 seconds")
                    voice.change(conversion_voice_selection,inputs=voice,outputs=[preview,custom_options],queue=False,api_name=False)
                    with gr.Accordion("Radio settings",open=False):
                        preset = gr.Dropdown(["Light","Radio","Damaged radio"],value="Radio",label="Radio sound")
                        static = gr.Slider(0,2,value=0.3,step=0.1,label="Static (%) · 0 for no noise")
                        seed = gr.Number(value=42,precision=0,label="Variation seed")
                    gr.Markdown("### 3 · Generate")
                    with gr.Row():
                        generate = gr.Button("Generate",variant="primary")
                        cancel = gr.Button("Cancel current job")
                with gr.Column():
                    clean = gr.Audio(buttons=["download"],label="1 · Clean converted voice",interactive=False,type="filepath")
                    radio = gr.Audio(buttons=["download"],label="2 · Same voice over radio",interactive=False,type="filepath")
                    download = gr.File(label="Download comparison, inputs & settings")
                    status = gr.Textbox(label="Status",interactive=False)
            recording_outputs = [source,recording_status,input_level,pc_start,pc_stop,device,generate,recording_timer,recording_seen]
            pc_start.click(start_recording,inputs=[device,recording_seen],outputs=recording_outputs,
                queue=False,api_name=False,show_progress="hidden")
            pc_stop.click(stop_recording,inputs=recording_seen,outputs=recording_outputs,
                queue=False,api_name=False,show_progress="hidden")
            recording_timer.tick(recording_updates,inputs=recording_seen,outputs=recording_outputs,
                queue=False,api_name=False,api_visibility="private",show_progress="hidden")
            generate.click(convert,[source,voice,custom,preset,static,seed],[clean,radio,download,status],
                api_name="convert",concurrency_id="audio",concurrency_limit=1)
            cancel.click(stop_active,outputs=status,queue=False,api_name=False)
            gr.Markdown("Record → choose a voice → Generate. Both clean and radio versions are created. Recordings can be 0.5–30 seconds; no extra voice sample is needed for a listed profile.")
            gr.Markdown("**Want American pronunciation?** Choose an American profile in **Text to speech** and type your line. Recording conversion changes the voice but can retain your original accent.")
        with gr.Tab("Text to speech"):
            gr.Markdown("Generate a new performance from text. **RMS (male) and SLT (female)** passed your Natural-tone sample listening test for clear speech, accurate words and a good American accent. Other text and delivery settings still need listening checks. This does not preserve your original acting or timing.")
            text = gr.Textbox(value="Control, this is Ranger Two. The northern route is clear. We are returning to base.",
                label="English dialogue · up to 300 spoken characters",lines=3,
                placeholder="[Yelling panically] Incoming!!!")
            tone = gr.Dropdown(TONE_CHOICES,value="Natural",label="Tone · approximate expression presets")
            gr.Markdown("Optional directions: **[Yelling panically] Incoming!!!**, **[Excited] We did it!**, **[Calm] Everything is under control.** A supported leading direction overrides the preset and is removed before speaking. Exact emotion or a convincing yell is not guaranteed.")
            default_tts_voice = next((p["label"] for p in PROFILES if p.get("id")=="cmu-rms"),VOICE_CHOICES[0])
            tvoice = gr.Dropdown(VOICE_CHOICES,value=default_tts_voice,label="Voice")
            gr.Markdown("**Recommended starting voices:** American male 2 · RMS and American female 1 · SLT, with Natural tone. RMS is the default. BDL remains removed after failed listening tests; its previous files and results are preserved.")
            tpreview = gr.Audio(buttons=["download"],value=voice_preview(default_tts_voice),label="Preview selected reference voice",interactive=False,type="filepath")
            tvoice.change(voice_preview,inputs=tvoice,outputs=tpreview,queue=False,api_name=False)
            tref = gr.Audio(buttons=["download"],sources=["microphone","upload"],type="filepath",format="wav",label="Your target reference · optional")
            with gr.Row():
                tbutton = gr.Button("Generate dialogue",variant="primary")
                tc = gr.Button("Cancel current job")
            with gr.Row():
                tclean = gr.Audio(buttons=["download"],label="Clean dialogue",type="filepath",interactive=False)
                tradio = gr.Audio(buttons=["download"],label="Radio dialogue",type="filepath",interactive=False)
            td = gr.File(label="Download comparison")
            ts = gr.Textbox(label="Status",interactive=False)
            tbutton.click(speak,[text,tvoice,tref,preset,static,seed,tone],[tclean,tradio,td,ts],
                api_name="speak",concurrency_id="audio",concurrency_limit=1)
            tc.click(stop_active,outputs=ts,queue=False,api_name=False)
            gr.Markdown("This initial text-to-speech setup uses the English Chatterbox checkpoint.")
        with gr.Tab("Your voice comparison"):
            personal_note = gr.Markdown()
            personal_source = gr.Audio(buttons=["download"],label="Your original recording",interactive=False)
            with gr.Row():
                with gr.Column():
                    personal_male_clean = gr.Audio(buttons=["download"],label="Male · clean",interactive=False)
                    personal_male_radio = gr.Audio(buttons=["download"],label="Male · radio",interactive=False)
                with gr.Column():
                    personal_female_clean = gr.Audio(buttons=["download"],label="Female · clean",interactive=False)
                    personal_female_radio = gr.Audio(buttons=["download"],label="Female · radio",interactive=False)
            personal_zip = gr.File(label="Download all versions and settings")
            personal_refresh = gr.Button("Load your saved comparison")
            personal_outputs = [personal_source,personal_male_clean,personal_male_radio,personal_female_clean,personal_female_radio,personal_zip,personal_note]
            personal_refresh.click(recording_comparison,outputs=personal_outputs,queue=False,api_name=False)
            demo.load(recording_comparison,outputs=personal_outputs,api_name=False)
        with gr.Tab("First quality test"):
            gr.Markdown("Compare the same public source performance in two target voices. These are actual Chatterbox outputs. Listen for changed words, metallic sound, voice similarity and timing. Radio processing can conceal defects, so check the clean versions first.")
            gr.Audio(buttons=["download"],value=str(ROOT/"inputs"/"demo-source.wav"),label="Original source performance",interactive=False)
            with gr.Row():
                with gr.Column():
                    qa = gr.Audio(buttons=["download"],label="Male · clean",interactive=False)
                    qb = gr.Audio(buttons=["download"],label="Male · radio",interactive=False)
                with gr.Column():
                    qc = gr.Audio(buttons=["download"],label="Female · clean",interactive=False)
                    qd = gr.Audio(buttons=["download"],label="Female · radio",interactive=False)
            refresh = gr.Button("Load saved comparison")
            refresh.click(quality_samples,outputs=[qa,qb,qc,qd],queue=False,api_name=False)
            demo.load(quality_samples,outputs=[qa,qb,qc,qd],api_name=False)
            gr.Markdown("Source clips: LibriSpeech / LibriVox, CC BY 4.0. References are concatenated and limited to ten seconds. Full attribution is saved in voices/attribution.json and included with demo-voice jobs.")

demo.queue(default_concurrency_limit=1,max_size=4)
app = gr.mount_gradio_app(app,demo,path="/",allowed_paths=[str(ROOT/"outputs"),str(ROOT/"inputs"),str(ROOT/"voices")],
    blocked_paths=[str(ROOT/"work"/"server.json")],max_file_size="30mb",
    theme=gr.themes.Soft(primary_hue="teal"),footer_links=[],show_error=True)

if __name__ == "__main__":
    (ROOT/"work"/"server.json").write_text(json.dumps({"pid":os.getpid(),"port":PORT,"token":STOP_TOKEN}))
    uvicorn.run(app,host="127.0.0.1",port=PORT,log_level="info")
