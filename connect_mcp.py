"""Print client configuration or install only the Local Audio Studio Codex entry."""
import argparse
import json
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path
import tomlkit
from runtime import ROOT

NAME = "local_audio_studio"


def configuration(root=ROOT):
    python = root / ".venv" / ("Scripts/python.exe" if os.name=="nt" else "bin/python")
    return {"command":str(python),"args":["-X","utf8","-u",str(root/"mcp_bridge.py")],
        "cwd":str(root),"startup_timeout_sec":120,"tool_timeout_sec":30}


def install(path, root=ROOT):
    path = Path(path).expanduser().resolve()
    original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    before = tomllib.loads(original)
    expected = configuration(root)
    existing = before.get("mcp_servers",{}).get(NAME)
    if existing is not None:
        if existing!=expected:
            raise ValueError("An existing local_audio_studio entry has different settings; it was not overwritten.")
        return False
    document = tomlkit.parse(original)
    if "mcp_servers" not in document:
        document["mcp_servers"] = tomlkit.table()
    document["mcp_servers"][NAME] = expected
    updated = tomlkit.dumps(document)
    after = tomllib.loads(updated)
    del after["mcp_servers"][NAME]
    if "mcp_servers" not in before and not after["mcp_servers"]:
        del after["mcp_servers"]
    if after!=before:
        raise RuntimeError("Other configuration would change; no files were written.")
    backups = root/"work"/"mcp-config-backups"
    backups.mkdir(parents=True,exist_ok=True)
    if original:
        backup = backups/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".toml")
        backup.write_text(original,encoding="utf-8")
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_name(path.name+".audio-mcp.partial")
    temporary.write_text(updated,encoding="utf-8")
    temporary.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-user",action="store_true",help="Add only this server to ~/.codex/config.toml; preserve all other settings.")
    args = parser.parse_args()
    if args.install_user:
        changed = install(Path.home()/".codex"/"config.toml")
        print("Local Audio Studio MCP registered." if changed else "Local Audio Studio MCP already registered.")
    else:
        document = tomlkit.document()
        document["mcp_servers"] = {NAME:configuration()}
        print(tomlkit.dumps(document))
        print("Generic stdio clients:")
        config = configuration()
        print(json.dumps({"mcpServers":{NAME:{k:config[k] for k in ("command","args","cwd")}}},indent=2))


if __name__=="__main__":
    main()
