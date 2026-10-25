param([switch]$SkipSamples)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
foreach ($name in @('work','models','voices','inputs','outputs')) { New-Item -ItemType Directory -Path $name -Force | Out-Null }
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot 'work\uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot 'work\python'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv from https://docs.astral.sh/uv/getting-started/installation/ and rerun.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv venv --python 3.11.17 .venv
    if ($LASTEXITCODE) { throw 'Python environment creation failed.' }
}
if (-not (Test-Path -LiteralPath 'work\vendor\chatterbox')) {
    git clone https://github.com/resemble-ai/chatterbox.git work/vendor/chatterbox
    if ($LASTEXITCODE) { throw 'Chatterbox source download failed.' }
    git -C work/vendor/chatterbox checkout 5de7a54aa4e5e2baadb0182dde554908b48b85c2
    if ($LASTEXITCODE) { throw 'Chatterbox source pin failed.' }
}
$revision = git -C work/vendor/chatterbox rev-parse HEAD
if ($revision -ne '5de7a54aa4e5e2baadb0182dde554908b48b85c2') { throw 'Existing Chatterbox source is a different revision; no files were reset.' }
uv pip install --python .venv/Scripts/python.exe torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
if ($LASTEXITCODE) { throw 'CUDA dependency installation failed.' }
if (Test-Path -LiteralPath 'requirements.lock.txt') {
    uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
} else {
    uv pip install --python .venv/Scripts/python.exe -r requirements.in
}
if ($LASTEXITCODE) { throw 'Audio dependency installation failed.' }
$prepareArgs = @('-u','prepare.py')
if ($SkipSamples -or (Test-Path -LiteralPath 'voices\attribution.json')) { $prepareArgs += '--models-only' }
& '.venv\Scripts\python.exe' @prepareArgs
if ($LASTEXITCODE) { throw 'Model or sample preparation failed; current files were retained.' }
if (-not $SkipSamples -and -not (Test-Path -LiteralPath 'voices\profiles.json')) {
    & '.venv\Scripts\python.exe' -X utf8 -u add_voice_profiles.py
    if ($LASTEXITCODE) { throw 'Additional voice reference preparation failed; existing files were retained.' }
}
& '.venv\Scripts\python.exe' -c "import torch; from chatterbox.vc import ChatterboxVC; assert torch.cuda.is_available(); print('CUDA and Chatterbox imports are ready. No speech was generated.')"
if ($LASTEXITCODE) { throw 'GPU readiness check failed.' }
Write-Output 'Ready. Double-click Start Audio.cmd.'
