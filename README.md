# Local Audio Studio

Record a performance, change its voice with local Chatterbox, and compare clean
speech with a radio version. No Strata or cloud speech API is used.

The project code is [MIT licensed](LICENSE). Third-party software, model weights
and reference recordings retain their own licenses; see
[third-party notices](THIRD_PARTY_NOTICES.md). Downloads, personal recordings and
generated audio are not included in this repository.

## Start and use

Double-click **Start Audio.cmd**. The local app opens at http://127.0.0.1:7865.
Use **Stop Audio.cmd** to close only this project's service and active worker.

1. Open **Your voice comparison** for the saved microphone comparison: original,
   male clean/radio, female clean/radio, and one download with all versions.
   **First quality test** retains the separate public-sample comparison.
2. Under **Record & change voice**, press **Record**, speak, then press
   **Stop recording**. The take appears in **Your recording**.
   Short dialogue clips are supported (0.5–30 seconds); there is no three-second
   minimum for the speech being converted. Choose an input under **Microphone
   settings** if needed. The take is available
   for playback. It also stops, saves and loads automatically after 30 seconds.
   These controls work in the embedded browser without browser microphone access.
   Alternatively, upload an existing clip in the player below the controls.
3. Choose a male/female voice profile or My reference recording. Five references
   are available: the two original demos plus American male RMS and American
   female SLT/CLB. Both recording conversion and text-to-speech can use them.
   Listed profiles already include their voice samples. The extra sample field
   appears only for **My reference recording**. That separate cloning sample
   needs 3–30 seconds, and the app uses the first 10.
4. Click **Generate**. Both clean and radio versions are created.
5. Download the comparison ZIP or keep the WAV files in that job's outputs folder.

The source performance is limited to 30 seconds for this first experiment.
There is one GPU job at a time, a five-minute deadline, and a Cancel button.
Each job loads a new worker; its GPU memory is released when it finishes.
Model loading adds overhead to every request.

**Text to speech** generates new English dialogue using the selected target
reference. It is limited to 300 characters initially. The radio settings selected
in the first tab also apply to this tab.

## American pronunciation and expression

To test American delivery, use **Text to speech**, choose an **American**
profile, and type the line. The owner accepted the RMS male and SLT female clean
Natural-tone samples for clarity, exact words and a good American accent on
2026-10-25. Start with those profiles and Natural tone; CLB and other lines/tone
settings still need listening checks. This generates a fresh performance from text, so
your original acting and timing are not preserved. The direct recording voice
converter changes timbre but can retain your accent; it has no accent-removal
control. American reference labels describe the source speaker, not a guarantee
that every generated word will have the desired accent.

The Tone selector offers Natural, Calm, Excited, Urgent / panicked, and
Forceful / angry. These map to Chatterbox's actual exaggeration, CFG and
temperature controls. They are approximate expression presets, not separately
trained emotion modes. A convincing scream, whisper or exact emotion is not
guaranteed by this checkpoint.

You can also enter a supported leading direction:

- [Yelling panically] Incoming!!!
- [Excited] We did it!
- [Calm] Everything is under control.

The app removes that direction, overrides the Tone preset, and synthesizes only
the dialogue. This is an app feature, not a native Chatterbox bracket-tag syntax.
Unsupported directions are rejected instead of being accidentally read aloud.
The original text, stripped dialogue, effective controls and chosen reference
profile are saved with the job. Punctuation and capital letters are retained.

## What the voices mean

The male and female buttons select different real reference recordings.
Chatterbox conditions on the voice in the reference audio; this is not a pitch
shift or a model trained specifically for each demo speaker. It may retain
attributes of your original voice, particularly across very different pitches.
Quality, voice similarity, pronunciation and timing need human listening.

The radio presets use CPU filtering, soft saturation and optional seeded static.
They retain the clean converted result. They do not regenerate speech and are
not an AI radio-speaking-style prompt. Re-run the same seed/settings for a
repeatable comparison, subject to GPU numerical variation.

## Installation

Native Windows, an NVIDIA CUDA GPU, Git and uv are required. The initial tested
setup uses Python 3.11.17, CUDA PyTorch 2.6.0 and Chatterbox source revision
5de7a54aa4e5e2baadb0182dde554908b48b85c2. Drivers remain external prerequisites.

Clone this repository, then run the included setup and start launchers:

```powershell
git clone https://github.com/JacobCohenIsrael/local-audio-studio.git
cd local-audio-studio
& ".\Setup Audio.cmd"
& ".\Start Audio.cmd"
```

Setup downloads the pinned third-party code, models and public voice samples.
The saved comparison tabs will be empty on a fresh installation until you make
your own recordings or run the quality comparison.

Run **Setup Audio.cmd** to prepare or repair the project environment. The model
files total about 3.2 GB; Python libraries and download caches require additional
space. No changes to other projects are needed. Dependencies are recorded in
requirements.lock.txt; setup verifies imports and CUDA without inference.
Additional reference preparation downloads about 340 MB of hash-verified public
CMU ARCTIC archives into the project cache. RMS, SLT and CLB use ten-second
references. BDL was rejected after owner listening and is no longer prepared.
Run add_voice_profiles.py with the project Python to restore those references;
Setup Audio.cmd prepares them on new installs unless sample setup is skipped.

All caches stay under this project. After preparation, inference runs with
Hugging Face offline mode enabled. The PC recording controls capture locally
through the project's microphone recorder; your browser controls it and plays
the saved take. The app binds only to 127.0.0.1; no public Gradio share link is used.

## Files

- inputs/: sample source; original uploads are additionally preserved per job.
- voices/: public demo references and full source attribution.
- models/: pinned weights and hash manifest.
- outputs/<unique-job>/: original/prepared inputs, clean.wav, radio.wav, settings,
  result measurements, logs and comparison.zip.
- work/: runtime environment, dependency cache, server logs and private reports.

## Tests

Run .venv/Scripts/python.exe -m pytest tests -q for signal and failure-control checks.
Run .venv/Scripts/python.exe quality_check.py --with-tts for the bounded real GPU
comparison. It reuses already-completed comparison jobs and does not retry failures.
Actual timings and peak allocations are in work/quality-check.json.

This setup does not prove subjective quality. Listen for changed/missing words,
metallic sound, target similarity, pauses and performance preservation.
The saved microphone comparison is separate from the public-sample test.
The owner accepted the original microphone male/female conversion and radio
comparison, and the later RMS/SLT clean Natural-tone TTS samples. This approval
applies to those samples; it does not validate every voice, line or tone setting.

## Microphone troubleshooting

- The recording status, elapsed seconds and input meter update while recording.
  Start is disabled until Stop; repeating Start cannot discard an active take.
- If the meter stays at zero while you speak, check the microphone's physical mute
  button and choose its explicit entry in PC microphone instead of System default.
- The most recent microphone recording is restored when the app starts. Use
  **More recording options → Load last microphone recording** to retrieve it after trying the demo sample
  or uploading another file. The demo sample is separate from your recorded takes.
- Stop and the automatic 30-second limit both save and load the take. Short or
  silent takes are retained with a clear message instead of silently discarded.
- Windows must allow desktop applications to use the microphone. This project
  does not change Windows privacy permissions or the system default audio device.

## Sources and licenses

- Chatterbox: https://github.com/resemble-ai/chatterbox — MIT, with upstream Perth
  watermarking retained.
- Weights: https://huggingface.co/ResembleAI/chatterbox — pinned revision
  5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18, hashes in models/manifest.json.
- Demo recordings: LibriSpeech, Vassil Panayotov, Guoguo Chen, Daniel Povey and
  Sanjeev Khudanpur; LibriVox volunteer readers, CC BY 4.0:
  https://www.openslr.org/12 and https://huggingface.co/datasets/openslr/librispeech_asr.
  Reader metadata is preserved in voices/SPEAKERS.TXT. References concatenate
  adjacent same-reader clips and retain ten seconds; the demo source retains
  twelve seconds. Exact IDs, transcripts, modifications and hashes are in
  voices/attribution.json. Converted demo audio must be identified as synthetic.
- Third-party Python libraries retain their own licenses.
- American references: http://festvox.org/cmu_arctic/ — CMU ARCTIC BDL/RMS
  (US male) and SLT/CLB (US female). Archive hashes match the published checksums
  in the pinned torchaudio dataset loader. The original CMU license, attribution,
  transformations and recording hashes are retained per profile and copied into
  jobs. Initial utterances are concatenated and limited to ten seconds.
  Both original and revised BDL references failed owner listening: extra or
  distorted words and unacceptable pronunciation. BDL is excluded by profile ID
  at runtime, including after rerunning setup with an older profile manifest.
  Its reference files, attribution and outputs remain preserved. RMS is the TTS
  default. RMS and SLT clean Natural-tone samples passed owner listening on
  2026-10-25; CLB and expressive settings remain unverified.
