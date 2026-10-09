import stat
import sys
from pathlib import Path

import pytest

from dxforge.stack import (
    IMAGE_PLACEHOLDER,
    TEMPLATE_SUFFIX,
    StackError,
    init_stack,
    render_compose,
    require_stack,
    stack_dir,
)
from dxforge.stack.secrets import read_secret

SCRIPTS = (
    "bootstrap/minio/init.sh",
    "bootstrap/openbao/init-unseal.sh",
    "bootstrap/registry/init.sh",
)


def test_init_renders_stack_and_generates_secrets(tmp_path: Path) -> None:
    result = init_stack(tmp_path, image="ghcr.io/example/dxforge:1.2.3")

    compose = (tmp_path / "docker-compose.yml").read_text()
    assert "ghcr.io/example/dxforge:1.2.3" in compose
    assert IMAGE_PLACEHOLDER not in compose
    assert result.image == "ghcr.io/example/dxforge:1.2.3"
    assert not list(tmp_path.rglob(f"*{TEMPLATE_SUFFIX}"))

    for script in SCRIPTS:
        path = tmp_path / script
        assert path.is_file(), script
        assert stat.S_IMODE(path.stat().st_mode) & stat.S_IXUSR, script

    assert (tmp_path / "bootstrap/minio/policies/worker.json").is_file()
    assert (tmp_path / ".env.example").is_file()

    assert read_secret(tmp_path, "postgres_app_user.txt") == "forge_app"
    assert read_secret(tmp_path, "minio_root_user.txt") == "forge-root"
    for name in ("postgres_password.txt", "api_key_pepper.txt", "minio_root_password.txt"):
        path = tmp_path / "secrets" / name
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert len(path.read_text().strip()) >= 32


def test_init_refuses_to_clobber_then_force_keeps_secrets(tmp_path: Path) -> None:
    init_stack(tmp_path)

    with pytest.raises(StackError, match="refusing to overwrite"):
        init_stack(tmp_path)

    existing = read_secret(tmp_path, "postgres_password.txt")
    init_stack(tmp_path, image="ghcr.io/example/dxforge:9.9.9", force=True)

    assert "ghcr.io/example/dxforge:9.9.9" in (tmp_path / "docker-compose.yml").read_text()
    assert read_secret(tmp_path, "postgres_password.txt") == existing


def test_require_stack_reports_missing_compose(tmp_path: Path) -> None:
    with pytest.raises(StackError, match="forge init"):
        require_stack(tmp_path)


def test_render_compose_rejects_template_without_placeholder() -> None:
    with pytest.raises(StackError, match=IMAGE_PLACEHOLDER):
        _ = render_compose(b"services: {}", "ghcr.io/example/dxforge:1")


def test_stack_dir_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_STACK_DIR", str(tmp_path / "from-env"))
    monkeypatch.chdir(tmp_path)

    assert stack_dir(str(tmp_path / "explicit")) == (tmp_path / "explicit").resolve()
    assert stack_dir() == (tmp_path / "from-env").resolve()

    monkeypatch.delenv("FORGE_STACK_DIR")
    assert stack_dir() == tmp_path.resolve()


def test_run_api_seeds_credentials_before_the_engine_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn

    from dxforge.cli import main as cli

    init_stack(tmp_path)
    monkeypatch.delenv("FORGE_DATABASE_URL", raising=False)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    # Drop what a fresh process would not have imported: the engine and settings
    # built before seeding would keep the default password and hide the bug.
    for module in [
        name
        for name in sys.modules
        if name == "dxforge.config"
        or name == "dxforge.db.session"
        or name.startswith("dxforge.api.")
    ]:
        monkeypatch.delitem(sys.modules, module, raising=False)

    cli.run_api(directory=tmp_path)

    from dxforge.db.session import engine

    assert engine.url.password == read_secret(tmp_path, "postgres_app_password.txt")
    assert engine.url.username == read_secret(tmp_path, "postgres_app_user.txt")
