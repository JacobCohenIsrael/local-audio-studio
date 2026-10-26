# Local Audio Studio

Turn a recorded performance into a different voice, write a line of dialogue,
or give speech a radio sound — all on your own PC with Chatterbox.
Listen to the clean and radio versions side by side, then download your favorites.

## What you can do

- **Record and change a voice.** Use your microphone or upload a short clip,
  then choose a voice profile or provide your own reference recording.
- **Make dialogue from text.** Generate English speech with a choice of voices
  and tone presets.
- **Add a radio effect.** Keep both the clean speech and the processed version.
- **Make game sound effects.** Create explosions, lasers and plasma weapons with
  duration, intensity and seeded variations. Preview each WAV or download a batch ZIP.
- **Connect an agent.** Use the same local studio from other projects through
  [MCP](MCP.md).

## Get started

You'll need **Windows, an NVIDIA GPU with CUDA support, Git, and uv**.
Setup downloads about **3.2 GB of model files**, plus Python dependencies,
caches and voice samples. An internet connection is needed for setup;
speech generation then runs locally in offline mode.

```powershell
git clone https://github.com/JacobCohenIsrael/local-audio-studio.git
cd local-audio-studio
& ".\Setup Audio.cmd"
& ".\Start Audio.cmd"
```

Already set up? Just double-click **Start Audio.cmd**. The app opens at
[127.0.0.1:7865](http://127.0.0.1:7865).
Use **Stop Audio.cmd** when you're done.

## Try your first recording

1. Open **Record & change voice** and press **Record**.
2. Speak for up to 30 seconds, then press **Stop recording**. Play back your take
   in **Your recording**. You can also upload an existing clip.
3. Choose a voice profile. The included profiles already have reference samples;
   **My reference recording** lets you supply your own 3–30 second sample.
4. Click **Generate**, then listen to the **clean** and **radio** results.
5. Download the comparison ZIP to keep the versions together.

The studio processes one GPU job at a time. Model loading can take a little
while; each job has a five-minute limit and can be cancelled.
Your original recording and each job's results are saved separately.

**Sound effects:** Open **Sound effects**, select one or more types, set duration
and intensity, and choose 1–5 variations per type. Click **Generate sound effects**.
Choose a generated effect in the preview selector, or download the entire batch. These are
procedural, stylized game sounds generated on the CPU, with no extra models or
downloads. Exports are mono 48 kHz, 24-bit WAV, with a separate file for each effect.
Their tails fit within the selected 0.15–8 second duration. Plasma includes a
short charge-up. Judge suitability by listening; cinematic realism is not promised.
The app and MCP share the same queue; **Cancel this batch** cancels only that batch.

**Prefer to type?** Open **Text to speech**, enter up to 300 characters, and
choose a voice. **American male RMS** or **American female SLT** with **Natural**
tone are good starting points: their tested samples passed the owner's listening
checks. The radio settings in the first tab also apply to text to speech.

## What to expect

Voice conversion uses a real reference recording to guide Chatterbox. Results
vary, and the converted voice may keep some of your original voice or accent.
Text to speech creates a fresh performance, so it won't preserve your recorded
acting or timing. Tone presets are approximate; listen for pronunciation,
missing words and how natural the result sounds.

Recordings, generated audio, models and caches stay in this project on your PC
and are excluded from version control. The app listens only on the local
loopback address and uses no cloud speech API. Chatterbox's upstream Perth
watermark is retained.

## Need more detail?

- [Usage and technical guide](GUIDE.md): voice profiles, expression controls,
  microphone troubleshooting, setup details, file locations and quality tests.
- [MCP guide](MCP.md): connect agents, generate batches of dialogue and manage jobs.
- [Third-party notices](THIRD_PARTY_NOTICES.md): model and recording sources,
  attribution and licenses.

The project code is [MIT licensed](LICENSE). Third-party software, model weights
and reference recordings retain their own licenses. Downloads, personal
recordings and generated audio are not included in this repository.
