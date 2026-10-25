"""Regression checks for microphone lifecycle and automatic UI handoff.

The fake device supplies a test tone: no real microphone is activated by tests.
"""
import numpy as np
import pytest
import soundfile as sf
import recorder as recorder_module


@pytest.fixture
def capture(monkeypatch, tmp_path):
    streams = []

    class FakeStream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.closed = False
            streams.append(self)

        def start(self):
            signal = (0.1 * np.sin(np.arange(12000) * 0.1)).astype("float32")[:, None]
            self.callback(signal, len(signal), None, None)

        def stop(self):
            pass

        def close(self):
            self.closed = True

    info = {"default_samplerate":16000, "hostapi":0, "max_input_channels":1, "name":"Test microphone"}
    monkeypatch.setattr(recorder_module.sd, "query_devices", lambda *a: info if a else [info])
    monkeypatch.setattr(recorder_module.sd, "query_hostapis", lambda *a: {"name":"MME"})
    monkeypatch.setattr(recorder_module.sd, "InputStream", FakeStream)
    device = recorder_module.PCRecorder(folder=tmp_path)
    yield device, streams
    if device.stream is not None:
        device.stop()


def test_double_start_preserves_the_active_take(capture):
    recorder, streams = capture
    recorder.start()
    frames = recorder.frames
    assert "Already recording" in recorder.start()
    assert len(streams) == 1 and recorder.frames == frames
    assert recorder.snapshot()["recording"]
    path, message = recorder.stop()
    data, sr = sf.read(path)
    assert len(data) == frames and sr == 16000
    assert streams[0].closed and "Saved" in message


def test_auto_stop_saves_clip_and_exposes_it_to_ui(capture, monkeypatch):
    recorder, streams = capture
    import app
    monkeypatch.setattr(app, "recorder", recorder)
    recorder.start()
    recorder._auto_stop(recorder.take_id)
    assert streams[0].closed
    state = recorder.snapshot()
    assert not state["recording"] and state["path"]
    updates = app.recording_updates(None)
    assert updates[0]["value"] == state["path"]
    assert updates[3]["interactive"] and not updates[4]["interactive"]
    assert not updates[7]["active"]


def test_stale_deadline_does_not_stop_a_new_recording(capture):
    recorder, streams = capture
    recorder.start()
    old_id = recorder.take_id
    first_path, _ = recorder.stop()
    recorder.start()
    recorder._auto_stop(old_id)
    assert recorder.snapshot()["recording"]
    second_path, _ = recorder.stop()
    assert second_path != first_path and streams[1].closed


def test_poll_does_not_replace_an_existing_draft(capture, monkeypatch):
    recorder, _ = capture
    import app
    monkeypatch.setattr(app, "recorder", recorder)
    recorder.start()
    path, _ = recorder.stop()
    assert "value" not in app.recording_updates(path)[0]


def test_failed_start_keeps_previous_recording_and_allows_retry(capture, monkeypatch):
    recorder, _ = capture
    recorder.start()
    path, _ = recorder.stop()
    original_stream = recorder_module.sd.InputStream

    def failed_stream(**kwargs):
        raise RuntimeError("Device unavailable")

    monkeypatch.setattr(recorder_module.sd, "InputStream", failed_stream)
    with pytest.raises(ValueError, match="Cannot open"):
        recorder.start()
    assert recorder.stream is None and str(recorder.last_path) == path
    monkeypatch.setattr(recorder_module.sd, "InputStream", original_stream)
    recorder.start()
    assert recorder.snapshot()["recording"]
