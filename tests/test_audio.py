import subprocess
import sys
import time
import numpy as np
import pytest
import soundfile as sf
from effects import radio_effect, safe_level
import studio

def amplitude(y, sr, frequency):
    t = np.arange(len(y)) / sr
    return abs(np.dot(y, np.exp(-2j*np.pi*frequency*t))) / len(y)

def test_radio_attenuates_bass_and_high_frequencies_without_changing_duration():
    sr=24000
    t=np.arange(sr*2)/sr
    y=sum(0.1*np.sin(2*np.pi*f*t) for f in [80,1000,7000])
    out=radio_effect(y,sr,static_percent=0)
    assert len(out)==len(y)
    assert amplitude(out,sr,1000) > 20*amplitude(out,sr,80)
    assert amplitude(out,sr,1000) > 10*amplitude(out,sr,7000)
    assert np.isfinite(out).all() and max(abs(out))<=0.891

def test_static_is_repeatable_and_does_not_change_clean_input():
    original=np.zeros(24000,dtype=np.float32)
    a=radio_effect(original,24000,static_percent=1,seed=5)
    b=radio_effect(original,24000,static_percent=1,seed=5)
    c=radio_effect(original,24000,static_percent=1,seed=6)
    assert np.array_equal(a,b) and not np.array_equal(a,c)
    assert not np.any(original)

@pytest.mark.parametrize("audio",[np.array([]),np.array([float("nan")]),np.array([float("inf")])])
def test_invalid_signals_are_rejected(audio):
    with pytest.raises(ValueError):
        safe_level(audio)

def test_long_or_silent_recording_is_rejected_before_inference(tmp_path):
    silent=tmp_path/"silent.wav"
    sf.write(silent,np.zeros(24000),24000)
    with pytest.raises(ValueError,match="silent"):
        studio.load_audio(silent)
    long=tmp_path/"long.wav"
    sf.write(long,np.ones(24000*31)*0.1,24000)
    with pytest.raises(ValueError,match="between"):
        studio.load_audio(long)

def test_short_dialogue_is_accepted_while_cloning_reference_needs_three_seconds(tmp_path):
    short=tmp_path/"short.wav"
    sf.write(short,np.ones(24000)*0.1,24000)
    audio, sample_rate = studio.load_audio(short)
    assert len(audio) / sample_rate == 1
    with pytest.raises(ValueError,match="between"):
        studio.load_audio(short,minimum=3)

def test_deadline_stops_only_the_owned_worker():
    studio._cancelled.clear()
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        with pytest.raises(RuntimeError,match="Stopped after"):
            studio.wait_owned(child,timeout=0.1)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()

def test_cancellation_stops_owned_worker():
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        studio._cancelled.set()
        with pytest.raises(RuntimeError,match="Cancelled"):
            studio.wait_owned(child,timeout=5)
        assert child.poll() is not None
    finally:
        studio._cancelled.clear()
        if child.poll() is None:
            child.kill()

def test_custom_voice_requires_reference():
    with pytest.raises(ValueError,match="target voice"):
        studio.choose_reference("My reference recording")
