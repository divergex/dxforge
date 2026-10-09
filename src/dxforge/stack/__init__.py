from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from importlib import metadata, resources
from pathlib import Path

from dxforge.stack.secrets import generate_root_secrets, write_compose_env

STACK_ENV = "FORGE_STACK_DIR"
IMAGE_REPOSITORY = "ghcr.io/divergex/dxforge"
IMAGE_PLACEHOLDER = "@@DXFORGE_IMAGE@@"
COMPOSE_FILE = "docker-compose.yml"
TEMPLATE_SUFFIX = ".tmpl"
PACKAGE = "dxforge.stack"


class StackError(RuntimeError):
    pass


def package_version() -> str:
    try:
        return metadata.version("dxforge")
    except metadata.PackageNotFoundError:
        return "dev"


def default_image() -> str:
    return f"{IMAGE_REPOSITORY}:{package_version()}"


def stack_dir(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    from_env = os.environ.get(STACK_ENV)
    if from_env:
        return Path(from_env).expanduser().resolve()
    return Path.cwd()


def require_stack(root: Path) -> Path:
    if not (root / COMPOSE_FILE).is_file():
        raise StackError(
            f"{root} is not a dxforge stack directory (no {COMPOSE_FILE}); "
            f"run 'forge init {root}' first"
        )
    return root


def _uid_for_compose(primary: str, fallback: str) -> str:
    get = getattr(os, "get" + primary, None)
    return str(get()) if callable(get) else fallback


def compose_env() -> dict[str, str]:
    """Export APP_UID/APP_GID so the bootstrap containers chown ./secrets back to this user."""
    env = dict(os.environ)
    env.setdefault("APP_UID", _uid_for_compose("uid", "1000"))
    env.setdefault("APP_GID", _uid_for_compose("gid", "1000"))
    return env


def run_compose(
    root: Path,
    args: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    # Regenerated from ./secrets on every call, so the credentials compose
    # interpolates cannot drift from the stored ones; .env is layered on top.
    env_files = [write_compose_env(root)]
    override = root / ".env"
    if override.is_file():
        env_files.append(override)

    command = [
        "docker",
        "compose",
        "--project-directory",
        str(root),
        "-f",
        str(root / COMPOSE_FILE),
        *(f"--env-file={path}" for path in env_files),
        *args,
    ]
    return subprocess.run(
        command,
        cwd=root,
        env=compose_env(),
        check=check,
        capture_output=capture,
        text=True,
    )


def compose_logs(root: Path, tail: int = 40) -> str:
    result = run_compose(root, ["logs", "--tail", str(tail)], check=False, capture=True)
    return result.stdout or result.stderr


def _rendered_name(relative: Path) -> Path:
    if relative.name.endswith(TEMPLATE_SUFFIX):
        return relative.with_name(relative.name[: -len(TEMPLATE_SUFFIX)])
    return relative


def _stack_files() -> Iterator[tuple[Path, bytes]]:
    root = resources.files(PACKAGE)
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        relative = entry.relative_to(root)
        if "__pycache__" in relative.parts or relative.suffix in {".py", ".pyc"}:
            continue
        yield _rendered_name(relative), entry.read_bytes()


def render_compose(template: bytes, image: str) -> str:
    text = template.decode("utf-8")
    if IMAGE_PLACEHOLDER not in text:
        raise StackError(f"compose template lacks {IMAGE_PLACEHOLDER}")
    return text.replace(IMAGE_PLACEHOLDER, image)


@dataclass(frozen=True)
class InitResult:
    root: Path
    image: str
    files: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)


def init_stack(
    dest: str | os.PathLike[str],
    *,
    image: str | None = None,
    force: bool = False,
) -> InitResult:
    root = Path(dest).expanduser().resolve()
    resolved_image = image or default_image()

    contents: list[tuple[Path, bytes]] = []
    for relative, data in _stack_files():
        if relative == Path(COMPOSE_FILE):
            data = render_compose(data, resolved_image).encode("utf-8")
        contents.append((relative, data))

    conflicts = [
        str(root / relative) for relative, _ in contents if (root / relative).exists()
    ]
    if conflicts and not force:
        raise StackError(
            "refusing to overwrite existing files (pass --force):\n  "
            + "\n  ".join(conflicts)
        )

    root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for relative, data in contents:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if target.suffix == ".sh":
            target.chmod(0o755)
        written.append(str(relative))

    created_secrets = generate_root_secrets(root)
    return InitResult(
        root=root,
        image=resolved_image,
        files=sorted(written),
        secrets=created_secrets,
    )
