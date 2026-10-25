"""Optional local microphone capture for browsers without microphone support."""
from runtime import ROOT
import threading
import uuid
import math
from datetime import datetime, timezone
import numpy as np
import soundfile as sf
import sounddevice as sd

class PCRecorder:
    def __init__(self, folder=None, max_seconds=30):
        self.lock = threading.Lock()
        self.folder = folder or ROOT / "inputs" / "recordings"
        self.max_seconds = max_seconds
        self.stream = None
        self.parts = []
        self.frames = 0
        self.rate = 48000
        self.timer = None
        saved = sorted(self.folder.glob("*.wav"))
        self.last_path = saved[-1] if saved else None
        self.peak = 0.0
        self.take_id = None
        self.message = "Last saved recording restored below." if saved else "Ready. Press Record, speak, then press Stop recording."

    def devices(self):
        devices = [("System default microphone", -1)]
        for index, device in enumerate(sd.query_devices()):
            # The ordinary Windows MME entries avoid duplicate driver variants.
            host = sd.query_hostapis(device["hostapi"])["name"]
            if device["max_input_channels"] and host == "MME" and "Mapper" not in device["name"]:
                devices.append((device["name"], index))
        return devices

    def start(self, device=-1):
        with self.lock:
            if self.stream is not None:
                # A double click must not reset or lose an active take.
                return "Already recording. Speak, then press Stop recording."
            index = None if int(device) == -1 else int(device)
            info = sd.query_devices(index, "input")
            self.rate = int(info["default_samplerate"])
            self.parts = []
            self.frames = 0
            self.peak = 0.0
            maximum = int(self.rate * self.max_seconds)
            def callback(indata, frames, timing, status):
                remaining = maximum - self.frames
                if remaining > 0:
                    piece = indata[:remaining, 0].copy()
                    self.parts.append(piece)
                    self.frames += len(piece)
                    self.peak = float(np.max(np.abs(piece))) if piece.size else 0.0
                if self.frames >= maximum:
                    raise sd.CallbackStop
            try:
                self.stream = sd.InputStream(device=index, samplerate=self.rate, channels=1,
                    dtype="float32", callback=callback)
                self.stream.start()
            except Exception as exc:
                if self.stream is not None:
                    self.stream.close()
                self.stream = None
                self.message = "Cannot open the microphone. Check its connection and Windows microphone access for desktop apps."
                raise ValueError(f"{self.message} Details: {exc}") from exc
            self.take_id = uuid.uuid4().hex
            self.timer = threading.Timer(self.max_seconds, self._auto_stop, args=(self.take_id,))
            self.timer.daemon = True
            self.timer.start()
            self.message = "Recording. Speak now, then press Stop recording."
        return self.message

    def _auto_stop(self, take_id):
        with self.lock:
            if self.take_id == take_id and self.stream is not None:
                self._finish()

    def snapshot(self):
        with self.lock:
            active = self.stream is not None
            seconds = self.frames / self.rate
            # A decibel-scaled meter makes ordinary speech visible at low gain.
            level = max(0.0, min(100.0, (20 * math.log10(max(self.peak, 1e-6)) + 60) / 60 * 100)) if active else 0.0
            message = f"RECORDING — {seconds:.1f} / {self.max_seconds:g} seconds. Speak, then press Stop recording." if active else self.message
            return {"recording":active, "seconds":seconds, "level":level, "message":message,
                    "path":str(self.last_path) if self.last_path else None}

    def _finish(self):
        """Called with the lock held, from either Stop or the deadline timer."""
        if self.timer:
            self.timer.cancel()
            self.timer = None
        stream, self.stream = self.stream, None
        try:
            stream.stop()
        finally:
            stream.close()
        data = np.concatenate(self.parts) if self.parts else np.empty(0)
        if not len(data):
            self.message = "No microphone samples arrived. Check the selected input device and try again. Your previous recording is kept."
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        self.last_path = self.folder / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".wav")
        sf.write(self.last_path, data, self.rate, subtype="PCM_16")
        seconds = len(data) / self.rate
        if seconds < 0.5:
            self.message = "Short recording saved. Record at least half a second before converting."
        elif float(np.sqrt(np.mean(data * data))) < 1e-5:
            self.message = f"Saved {seconds:.1f} seconds, but the input is silent. Check the microphone mute button and selected device."
        else:
            self.message = f"Saved {seconds:.1f} seconds. Choose a voice, then press Generate."

    def stop(self):
        with self.lock:
            if self.stream is None:
                if self.last_path:
                    return str(self.last_path), self.message
                raise ValueError("Press Record first.")
            self._finish()
            return str(self.last_path) if self.last_path else None, self.message

recorder = PCRecorder()
