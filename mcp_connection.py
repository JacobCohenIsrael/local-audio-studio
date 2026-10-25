"""Small local MCP connection helpers; no audio/model imports."""
import json
import secrets
from urllib.request import urlopen
from runtime import ROOT

BASE_URL = "http://127.0.0.1:7865"
MCP_URL = BASE_URL + "/agent/mcp"


def read_token(root=ROOT):
    path = root / "work" / "mcp-token.txt"
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        try:
            with path.open("x",encoding="utf-8") as f:
                f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    token = path.read_text(encoding="utf-8").strip()
    if len(token)<32:
        raise RuntimeError("Invalid local MCP token file; preserve it and repair the connection setup.")
    return token


def check_service():
    try:
        with urlopen(BASE_URL+"/healthz",timeout=2) as response:
            health = json.load(response)
    except OSError:
        return False
    if health.get("service")!="local-audio-studio" or health.get("project_root")!=str(ROOT):
        raise RuntimeError("Port 7865 belongs to a different service/check-out; no process was stopped.")
    if not health.get("mcp"):
        raise RuntimeError("Restart Local Audio Studio to load its MCP support.")
    return True


def ensure_service():
    # The shared service must not be a child of an MCP client. On Windows,
    # closing a stdio client can kill its entire child-process Job Object.
    if not check_service():
        raise RuntimeError(f"Start Local Audio Studio independently with {ROOT / 'Start Audio.cmd'}, then reconnect MCP. This keeps other sessions' jobs alive when a client closes.")
