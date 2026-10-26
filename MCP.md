# Local Audio Studio MCP

Other local agent sessions can use one shared audio service without driving the
browser or starting their own models. The service and all generated audio stay
on this PC. Setup Audio.cmd installs the pinned MCP SDK along with the app.

## Connect Codex across projects

From this project directory:

```powershell
.venv/Scripts/python.exe connect_mcp.py --install-user
```

Start the studio once with **Start Audio.cmd**, then connect MCP.
This adds only `mcp_servers.local_audio_studio` to the user's Codex configuration.
It preserves other settings, backs up the original in ignored local work storage,
and refuses to overwrite a conflicting audio entry. Restart the MCP connection
or open a new session to load it. To remove the connection:

```powershell
codex mcp remove local_audio_studio
```

For configuration snippets for other stdio clients, run:

```powershell
.venv/Scripts/python.exe connect_mcp.py
```

Use the generated absolute command/arguments. The lightweight `mcp_bridge.py`
checks that port 7865 belongs to this checkout and connects to its authenticated
HTTP endpoint. Each agent gets a
small bridge process; all share the same audio queue. Closing one connection
does not stop the service or another agent's job. The bridge loads no models.
The studio must be started independently: Windows MCP clients can terminate
their entire child-process group at disconnect. The bridge therefore reports a
clear startup instruction if the service is off, rather than making shared jobs
depend on one client's lifetime. After Stop Audio.cmd, start the studio and
reconnect MCP before the next agent session.

## Tools

MCP version 1.1.0 adds `generate_sound_effects`. The existing client registration
and stdio bridge expose it without a configuration change. If an already-open
client caches its tool list, reconnect that audio MCP connection after starting
the updated studio.

| Tool | Purpose |
| --- | --- |
| `audio_service_status` | Queue capacity, limits, tone and radio options; no model load. |
| `list_audio_voices` | Stable voice IDs, source metadata and reference paths. |
| `generate_speech` | Submit one English TTS line; returns a job ID immediately. |
| `generate_speech_batch` | Submit up to 8 lines with one voice/model load. |
| `convert_voice` | Convert an existing local recording using a target reference. |
| `apply_radio_effect` | CPU-only processing of existing audio; no speech regeneration. |
| `generate_sound_effects` | CPU batch of 1–16 explosions, lasers or plasma weapons; individual WAVs and ZIP. |
| `get_audio_job` | Status, measurements and absolute paths/file URIs for results. |
| `cancel_audio_job` | Cancel only the named queued/running job; preserve its files. |

Suggested starting IDs are `cmu-rms` (male) and `cmu-slt` (female), with Natural
tone. Their specific Natural-tone TTS samples passed the owner's listening test.
This does not guarantee every line, conversion or expressive delivery. Other IDs
are returned by discovery. BDL remains excluded. For a supplied target sample,
use `voice_id="custom"` and an absolute `custom_reference` audio path.

Microphone recording stays in the browser's Record & change voice tab. Agents
consume explicitly supplied audio file paths; MCP does not expose microphone
start/stop controls or automatically collect recordings.

## Efficient agent workflow

1. Discover voices/options once per session.
2. Submit a job with a unique `request_id` (for example a UUID). Repeating the
   same key with unchanged inputs/settings returns the existing job; a conflicting
   payload is rejected. It never silently retries a failed job.
3. Prefer a batch for several lines sharing one voice. It loads Chatterbox and
   prepares the reference once. Seeds increment from the supplied seed by line.
4. Use `get_audio_job(job_id, wait_seconds=10)` to wait efficiently. Status calls
   stay responsive while inference runs; avoid rapid polling.
5. On `complete`, consume the returned clean/radio WAV paths or comparison ZIP.
   Audio is not base64-encoded into MCP messages. All outputs stay under this
   project's outputs folder; agents can copy them using their own file permissions.
6. Treat `failed`, `cancelled` and `interrupted` as terminal. Inspect the error
   before deliberately submitting a new request. Partial files are preserved and
   are not validated as finished audio.

Example batch arguments:

```json
{
  "texts": [
    "Control, the road is clear. We are returning to base.",
    "All units, hold position. Wait for the signal."
  ],
  "voice_id": "cmu-rms",
  "tone": "Natural",
  "seed": 42,
  "request_id": "your-unique-request-id"
}
```

## Limits and lifetime

Sound-effects example arguments for `generate_sound_effects`:

```json
{
  "effects": [
    {"effect": "explosion", "duration": 3.0, "intensity": 0.9, "seed": 42},
    {"effect": "laser", "duration": 0.8, "intensity": 0.6, "seed": 43},
    {"effect": "plasma", "duration": 2.0, "intensity": 0.8, "seed": 44}
  ],
  "request_id": "your-unique-sfx-request-id"
}
```

Wait with `get_audio_job`, then use the returned `sfx-NNN-effect.wav` paths or
`sound-effects.zip`. Each file is mono 48 kHz, 24-bit PCM WAV. The ZIP includes
the WAVs, request settings and result metadata. The effects are original
procedural synthesis, independent of Chatterbox and voice references; no extra
model, source recordings, GPU work or cloud service is involved. Seeded variation
is repeatable within this implementation/environment. Quality requires listening.

- One queue for browser and MCP requests; at most four outstanding jobs, including
  the active job. Excess submissions fail clearly instead of building a backlog.
- One GPU worker at a time, protected across project processes by a file lock.
  A worker gets a 300-second deadline for its entire job, including a whole batch.
  It exits after completion, failure or cancellation, releasing GPU memory.
- Sound-effects batches use the same queue and a 300-second deadline. Each batch
  has 1–16 items; each item has `effect` (`explosion`, `laser`, `plasma`), `duration`
  (0.15–8 seconds, default 2), `intensity` (0–1, default 0.7), and `seed`
  (0–2147483647, default 42). Cancellation is checked between synthesis, writing
  and packaging steps; an individual bounded synthesis finishes before stopping.
- Each TTS line has at most 300 spoken characters; batches have 1–8 lines and
  at most 1200 input characters total. Leading supported stage directions behave
  the same as in the browser. Quality still needs listening.
- Conversion input: 0.5–30 seconds. Target reference: 3–30 seconds; first 10 used.
  CPU radio input: 0.5–90 seconds. Input files are limited to 30 MB and supported
  local audio formats. URLs and UNC network paths are not accepted.
- Input snapshots are preserved when a job is admitted, so edits to the original
  dialogue recording while queued do not change that job. Each job has its own
  output directory. Tickets persist in ignored local work storage; unfinished
  jobs are marked interrupted at service restart and never automatically resumed.
- The browser's Cancel current job button stops the active shared GPU job.
  MCP clients should use cancellation by job ID to avoid cancelling another job.
  Stop Audio.cmd stops this project's service and pending jobs.
- Perth watermarking remains enabled for synthesized/converted speech. Radio
  processing keeps separate clean audio and applies no new voice model.

## Direct Streamable HTTP

Clients supporting HTTP can connect to `http://127.0.0.1:7865/agent/mcp` with
`Authorization: Bearer <local token>`. Read the token from this checkout's
`work/mcp-token.txt`; never commit it or put it in a public configuration file.
The stdio bridge handles this automatically, so no secret is stored in Codex's
audio connection entry. Token rotation requires restarting the service and clients.

The endpoint is loopback-only, bearer-authenticated, with SDK Host/Origin checks
and a 64 KiB request-body limit. The token grants trusted local agents access to
submitted jobs and audio paths. There is no network exposure, arbitrary shell
tool, output-directory override or cloud upload tool. Personal audio and runtime
data remain excluded from Git.

## Measured local behavior

A two-line RMS Natural-tone test on 2026-10-25 took 38.811 seconds as two single
GPU jobs and 19.359 seconds as one batch (about 50% less inference/loading time).
Both batch clean WAVs matched their corresponding single-job WAVs byte for byte;
the first also matched the owner's previously accepted RMS sample. Five status
calls while jobs were running took 4.35–8.54 ms. A running-service stdio connection
and tool discovery took about one second. These are local observations for that
test, not latency guarantees. Host-specific reports and generated audio stay
under ignored work/output folders.

## Implementation references

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
  pinned to 2.3.0 in this project.
- [Official mounted Streamable HTTP example](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/servers/streamable_starlette_mount.py).
- [Official Codex MCP connection documentation](https://learn.chatgpt.com/docs/extend/mcp).
