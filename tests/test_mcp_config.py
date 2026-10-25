import tomllib
import pytest
from connect_mcp import install, configuration


def test_install_adds_only_audio_entry_and_is_idempotent(tmp_path):
    path = tmp_path/"client"/"config.toml"
    path.parent.mkdir()
    original = '# Keep this comment\nmodel = "existing-model"\n[mcp_servers.other]\ncommand = "existing.exe"\n'
    path.write_text(original)
    assert install(path,root=tmp_path)
    updated = path.read_text()
    data = tomllib.loads(updated)
    assert data["model"]=="existing-model" and data["mcp_servers"]["other"]=={"command":"existing.exe"}
    assert data["mcp_servers"]["local_audio_studio"]==configuration(tmp_path)
    assert '# Keep this comment' in updated
    assert not install(path,root=tmp_path)
    assert path.read_text()==updated
    assert len(list((tmp_path/"work"/"mcp-config-backups").glob("*.toml")))==1


def test_install_does_not_overwrite_a_conflicting_server(tmp_path):
    path=tmp_path/"config.toml"
    original='[mcp_servers.local_audio_studio]\ncommand = "someone-else.exe"\n'
    path.write_text(original)
    with pytest.raises(ValueError,match="not overwritten"):
        install(path,root=tmp_path)
    assert path.read_text()==original
