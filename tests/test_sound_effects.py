import threading
import zipfile

import numpy as np
import pytest
import soundfile as sf

from jobs import JobManager
from sound_effects import EFFECTS, SAMPLE_RATE, render_batch, synthesize, validate


@pytest.mark.parametrize("effect", EFFECTS)
def test_effects_are_finite_repeatable_audible_and_fade_out(effect):
    y = synthesize(effect, duration=1.25)
    assert len(y) == int(SAMPLE_RATE * 1.25)
    assert np.isfinite(y).all() and np.max(np.abs(y)) <= .9
    assert np.sqrt(np.mean(y*y)) > .015
    assert y[0] == y[-1] == 0
    assert np.sqrt(np.mean(y[-480:] ** 2)) < .01
    np.testing.assert_array_equal(y, synthesize(effect, duration=1.25))
    assert not np.array_equal(y, synthesize(effect, duration=1.25, seed=43))


@pytest.mark.parametrize("items", [[], [{}], [{"effect":"voice"}],
    [{"effect":"laser","duration":float("nan")}], [{"effect":"laser","duration":9}],
    [{"effect":"laser","intensity":-1}], [{"effect":"laser","seed":True}],
    [{"effect":"laser","seed":-1}], [{"effect":"laser","path":"../oops.wav"}],
    [{"effect":"laser"}] * 17])
def test_invalid_batches_rejected(items):
    with pytest.raises(ValueError):
        validate(items)


def test_real_queue_batch_exports_exact_wavs_and_reuses_request(tmp_path, monkeypatch):
    import studio
    monkeypatch.setattr(studio, "choose_reference", lambda *a: pytest.fail("SFX must not use voices"))
    monkeypatch.setattr(studio, "run_job", lambda *a, **k: pytest.fail("SFX must not load GPU models"))
    jobs = JobManager(tmp_path)
    try:
        items = [dict(effect=effect, duration=.3, seed=7) for effect in EFFECTS]
        ticket = jobs.submit("sfx", effects=items, request_id="effects-batch-test")
        state = jobs.get(ticket["job_id"], wait_seconds=5)
        assert state["status"] == "complete", state
        assert state["effect_count"] == 3 and state["result"]["gpu_used"] is False
        assert jobs.submit("sfx", effects=items, request_id="effects-batch-test")["job_id"] == ticket["job_id"]
        with pytest.raises(ValueError, match="different inputs"):
            jobs.submit("sfx", effects=[dict(effect="plasma")], request_id="effects-batch-test")
        folder = tmp_path / "outputs" / ticket["job_id"]
        wavs = []
        for item in state["result"]["items"]:
            path = folder / item["file"]
            info = sf.info(path)
            assert (info.samplerate, info.channels, info.subtype) == (48000, 1, "PCM_24")
            wavs.append(path.name)
        assert {a["name"] for a in state["artifacts"]} == set(wavs + ["sound-effects.zip"])
        with zipfile.ZipFile(folder / "sound-effects.zip") as archive:
            assert set(archive.namelist()) == set(wavs + ["request.json", "result.json"])
            for name in wavs:
                assert archive.read(name) == (folder / name).read_bytes()
    finally:
        jobs.close()


def test_batch_cancellation_and_deadline(tmp_path, monkeypatch):
    import sound_effects
    cancel = threading.Event()
    original = sound_effects.synthesize

    def cancel_during_synthesis(**kwargs):
        y = original(**kwargs)
        cancel.set()
        return y

    monkeypatch.setattr(sound_effects, "synthesize", cancel_during_synthesis)
    with pytest.raises(RuntimeError, match="cancelled"):
        render_batch(tmp_path / "cancelled", [dict(effect="laser")], cancel)
    assert not list((tmp_path / "cancelled").glob("*.wav"))
    with pytest.raises(RuntimeError, match="deadline"):
        render_batch(tmp_path / "expired", [dict(effect="laser")], threading.Event(), deadline_seconds=0)


def test_browser_sfx_uses_shared_queue_and_exports_paths(tmp_path, monkeypatch):
    import app
    jobs = JobManager(tmp_path)
    monkeypatch.setattr(app, "jobs", jobs)
    try:
        results = list(app.create_sound_effects(["laser", "plasma"], .2, .7, 2, 42))
        assert len(results) == 2
        assert results[0][4] == results[1][4]
        assert len(results[1][1]) == 4
        assert results[1][0] == results[1][1][0]
        assert results[1][2].endswith("sound-effects.zip")
        assert len(results[1][5]["choices"]) == 4
        monkeypatch.setattr(app, "ROOT", tmp_path)
        assert app.preview_sound_effect(results[1][1][2]) == results[1][1][2]
        with pytest.raises(ValueError):
            app.preview_sound_effect(str(tmp_path / "private.txt"))
    finally:
        jobs.close()
