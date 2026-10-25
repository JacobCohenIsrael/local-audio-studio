"""One bounded queue shared by browser and MCP; persistent tickets, no automatic retries."""
import hashlib
import json
import re
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from filelock import FileLock
import soundfile as sf
import studio
from delivery import prepare_delivery
from effects import PRESETS, radio_effect, safe_level
from runtime import ROOT

TERMINAL = {"complete", "failed", "cancelled", "interrupted"}
JOB_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")


def now():
    return datetime.now(timezone.utc).isoformat()


def local_audio(path, *, reference=False, maximum=30):
    if not path or "://" in str(path) or str(path).startswith(("\\\\", "//")):
        raise ValueError("Supply a local audio file path, not a URL or network share.")
    p = Path(path).resolve(strict=True)
    if p.suffix.lower() not in {".wav", ".flac", ".mp3", ".ogg", ".m4a"}:
        raise ValueError("Supply a WAV, FLAC, MP3, OGG or M4A audio file.")
    studio.load_audio(p, maximum=maximum, minimum=3 if reference else 0.5)
    return p


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class JobManager:
    def __init__(self, root=ROOT, capacity=4, runner=None):
        self.root = Path(root)
        self.folder = self.root / "work" / "agent-jobs"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.capacity = capacity
        self.condition = threading.Condition(threading.RLock())
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-queue")
        self.runner = runner or self._execute
        self.records, self.events, self.futures, self.requests = {}, {}, {}, {}
        self.closed = False
        self.service_lock = None
        for path in self.folder.glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            self.records[record["job_id"]] = record
            if record.get("request_id"):
                self.requests[record["request_id"]] = record["job_id"]

    def start(self):
        self.service_lock = FileLock(self.folder / "service.lock")
        self.service_lock.acquire(timeout=0)
        with self.condition:
            for record in self.records.values():
                if record["status"] not in TERMINAL:
                    record.update(status="interrupted",error="Service restarted; this job was not retried.",finished_at=now())
                    self._save(record)

    def _save(self, record):
        path = self.folder / (record["job_id"] + ".json")
        temporary = path.with_suffix(".partial")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        temporary.replace(path)

    def stats(self):
        with self.condition:
            pending = [r for r in self.records.values() if r["status"] not in TERMINAL]
            return {"outstanding":len(pending), "capacity":self.capacity,
                "running_job":next((r["job_id"] for r in pending if r["status"]=="running"),None),
                "queued":sum(r["status"]=="queued" for r in pending), "closed":self.closed}

    def submit(self, mode, *, source=None, voice="American male 2 · RMS", custom=None, text="", texts=None,
               preset="Radio", static=0.3, seed=42, tone="Natural", request_id=None):
        if mode not in {"tts", "convert", "radio"} or preset not in PRESETS:
            raise ValueError("Choose a supported audio mode and radio preset.")
        if not isinstance(seed,int) or isinstance(seed,bool) or not 0 <= seed <= 2147483647 or not 0 <= float(static) <= 2:
            raise ValueError("Seed must be 0–2147483647 and static 0–2 percent.")
        if request_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{8,100}",request_id):
            raise ValueError("Use an 8–100 character request ID (letters, digits, underscore, hyphen).")
        if texts is not None:
            if mode!="tts" or not 1 <= len(texts) <= 8 or sum(len(t) for t in texts)>1200:
                raise ValueError("A batch needs 1–8 lines and at most 1200 characters total.")
            for line in texts:
                prepare_delivery(line,tone)
            text = texts[0]
        if mode=="tts":
            prepare_delivery(text,tone)
        reference = None
        if mode!="radio":
            reference = local_audio(studio.choose_reference(voice,custom),reference=True)
        source = local_audio(source,maximum=90 if mode=="radio" else 30) if mode!="tts" else None
        payload = {"mode":mode,"voice":voice,"text":text,"texts":texts,"preset":preset,
            "static":float(static),"seed":seed,"tone":tone}
        hashes = {"source":digest(source) if source else None,"reference":digest(reference) if reference else None}
        fingerprint = hashlib.sha256(json.dumps({**payload,"source_sha256":hashes["source"],
            "reference_sha256":hashes["reference"]},sort_keys=True).encode()).hexdigest()
        with self.condition:
            if self.closed:
                raise RuntimeError("Audio service is stopping.")
            if request_id and request_id in self.requests:
                previous = self.records[self.requests[request_id]]
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("This request ID already belongs to different inputs/settings.")
                return self._view(previous)
            if self.stats()["outstanding"] >= self.capacity:
                raise RuntimeError("Audio queue is full. Check existing jobs before submitting again.")
            job_id = studio.new_job_id()
            staging = self.root / "inputs" / "agent-jobs" / job_id
            staging.mkdir(parents=True)
            for role, path in (("source",source),("reference",reference)):
                if path:
                    saved = staging / (role + path.suffix.lower())
                    remaining = 30 * 1024**2
                    with path.open("rb") as original, saved.open("xb") as target:
                        while block := original.read(min(1024**2,remaining+1)):
                            if len(block)>remaining:
                                raise ValueError("Audio input exceeded 30 MB while being copied.")
                            target.write(block)
                            remaining -= len(block)
                    if digest(saved)!=hashes[role]:
                        raise ValueError("Audio input changed during submission; use a stable saved file.")
                    payload[role] = str(saved)
            payload["custom"] = str(staging / ("reference"+reference.suffix.lower())) if custom and reference else None
            record = {"job_id":job_id,"status":"queued","mode":mode,"created_at":now(),"request_id":request_id,
                "fingerprint":fingerprint,"payload":payload,"line_count":len(texts) if texts else 1}
            self._save(record)
            self.records[job_id] = record
            self.events[job_id] = threading.Event()
            if request_id:
                self.requests[request_id] = job_id
            self.futures[job_id] = self.executor.submit(self._run,job_id)
            return self._view(record)

    def _run(self, job_id):
        with self.condition:
            record, event = self.records[job_id], self.events[job_id]
            if event.is_set():
                record.update(status="cancelled",finished_at=now())
                self._save(record)
                self.condition.notify_all()
                return
            record.update(status="running",started_at=now())
            self._save(record)
        try:
            job, result = self.runner(record,event)
            with self.condition:
                record.update(status="cancelled" if event.is_set() else "complete",result=result,folder=str(job))
        except Exception as exc:
            with self.condition:
                record.update(status="cancelled" if event.is_set() else "failed",error=str(exc))
        finally:
            with self.condition:
                record["finished_at"] = now()
                self._save(record)
                self.condition.notify_all()

    def _execute(self, record, event):
        p = record["payload"]
        if p["mode"]=="radio":
            if event.is_set():
                raise RuntimeError("Cancelled.")
            job = self.root / "outputs" / record["job_id"]
            job.mkdir(parents=True)
            shutil.copyfile(p["source"],job / ("source.original"+Path(p["source"]).suffix))
            y,sr = studio.load_audio(p["source"],maximum=90)
            clean = safe_level(y)
            sf.write(job/"clean.wav",clean,sr,subtype="PCM_16")
            sf.write(job/"radio.wav",radio_effect(clean,sr,p["preset"],p["static"],p["seed"]),sr,subtype="PCM_16")
            result = {"status":"complete","seconds":len(y)/sr,"sample_rate":sr,"gpu_used":False,
                "watermark":"CPU processing only; no new watermark added or existing watermark intentionally removed."}
            (job/"request.json").write_text(json.dumps(p,indent=2),encoding="utf-8")
            (job/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            with zipfile.ZipFile(job/"comparison.zip","w",compression=zipfile.ZIP_DEFLATED) as archive:
                for path in job.iterdir():
                    if event.is_set():
                        raise RuntimeError("Cancelled while packaging radio output.")
                    if path.is_file() and path.suffix in {".wav",".json",".flac",".mp3",".ogg",".m4a"}:
                        archive.write(path,path.name)
            return job,result
        return studio.run_job(p["mode"],p.get("source"),p["voice"],p.get("custom"),p["text"],p["preset"],p["static"],p["seed"],p["tone"],
            texts=p["texts"],job_id=record["job_id"],cancel_event=event,reference_override=p.get("reference"))

    def _record(self, job_id):
        if not JOB_ID.fullmatch(job_id) or job_id not in self.records:
            raise ValueError("Unknown audio job ID.")
        return self.records[job_id]

    def _view(self, record):
        result = {k:v for k,v in record.items() if k not in {"payload","fingerprint","folder"}}
        job = self.root / "outputs" / record["job_id"]
        result["artifacts"] = [{"name":p.name,"path":str(p.resolve()),"uri":p.resolve().as_uri(),"bytes":p.stat().st_size}
            for p in sorted(job.glob("*")) if p.is_file() and
            (p.name in {"clean.wav","radio.wav","comparison.zip"} or re.fullmatch(r"item-\d{3}-(clean|radio)\.wav",p.name))]
        return result

    def get(self, job_id, wait_seconds=0):
        if not 0 <= wait_seconds <= 10:
            raise ValueError("Wait at most 10 seconds per status call.")
        with self.condition:
            record = self._record(job_id)
            self.condition.wait_for(lambda: record["status"] in TERMINAL, timeout=wait_seconds)
            return self._view(record)

    def wait_finished(self, job_id):
        with self.condition:
            record = self._record(job_id)
            self.condition.wait_for(lambda: record["status"] in TERMINAL)
            if record["status"]!="complete":
                raise RuntimeError(record.get("error") or record["status"])
            return self.root / "outputs" / job_id,dict(record["result"])

    def cancel(self, job_id):
        with self.condition:
            record = self._record(job_id)
            if record["status"] in TERMINAL:
                return self._view(record)
            self.events[job_id].set()
            if self.futures[job_id].cancel():
                record.update(status="cancelled",finished_at=now())
                self._save(record)
                self.condition.notify_all()
            return self._view(record)

    def close(self, wait=True):
        with self.condition:
            self.closed = True
            for job_id,record in self.records.items():
                if record["status"] not in TERMINAL:
                    self.cancel(job_id)
        self.executor.shutdown(wait=wait,cancel_futures=True)
        if self.service_lock and wait:
            self.service_lock.release()
