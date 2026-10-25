# Local Audio Studio agent instructions

Read README.md and NEXT_STEPS.md before changes.

The owner authorized this separate local Chatterbox experiment: microphone recording,
male/female voice conversion, radio processing and actual audio quality tests.
The local-3d-generator project must remain untouched. Do not modify its files,
environment, jobs, models or shared Strata configuration.

Use this project's Python environment, models and caches. Initial code and model
revisions are pinned in setup.ps1, prepare.py and models/manifest.json.
Keep recordings, weights, generated audio, environments and machine-specific
reports out of version control. Preserve original uploads and each job separately.

Run GPU work sequentially with a 300-second deadline and an owned cancellable
worker process. Do not retry failed inference automatically. Stop only processes
owned by this project. Launch background helpers hidden on Windows.
Do not change drivers, hardware settings, other services or global configurations.

Use Chatterbox's reference-conditioned voice conversion, not pitch shifting as a
substitute. Keep clean and radio audio separately. Preserve the upstream Perth
watermark. Compare actual output by listening; signal checks establish only valid
files and resource measurements. Do not call the user's microphone test complete
without their recording and listening feedback.

Strata is explicitly deferred until audio quality is accepted by the owner.
The owner subsequently authorized public GitHub publication of this project's
source code under MIT. Recordings, generated audio, weights, environments, caches,
credentials and machine-specific reports must remain local and untracked.
No paid service, training or live voice routing is authorized. The normal app
listens only on loopback.

Update one current NEXT_STEPS.md checkpoint after meaningful changes.
