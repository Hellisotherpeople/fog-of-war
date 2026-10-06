#!/usr/bin/env python3
"""Deploy from this Mac in a session that permits SSH and home-directory writes.

No credentials are embedded: SSH uses the existing agent; API authentication stays in api.env.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTENSION = Path("/Users/lain/Downloads/omp-samplers")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remote(command, data=None):
    inner = shlex.join(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                       "-o", "StrictHostKeyChecking=yes", "ubuntu@192.168.200.207", command])
    subprocess.run(["ssh", "-T", "-i", str(Path.home() / ".ssh/id_ed25519"),
                    "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                    "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=30",
                    "ubuntu@47.47.180.93", inner], input=data, check=True)


def main():
    original = json.loads((ROOT / "omp-original-sha256.json").read_text())
    changes = []
    for path in (ROOT / "omp-samplers").rglob("*"):
        relative = path.relative_to(ROOT / "omp-samplers")
        if any(part in {"node_modules", ".git"} for part in relative.parts) or not path.is_file():
            continue
        before = original.get(str(relative))
        if sha(path) == before:
            continue
        target = EXTENSION / relative
        if (target.exists() and sha(target) not in {before, sha(path)}) or (before and not target.exists()):
            raise RuntimeError(f"Extension changed since staging: {target}; merge before deploying")
        changes.append((path, target))
    # Real local integration checks must pass before restarting the remote service.
    bun = Path.home() / ".bun/bin/bun"
    subprocess.run([str(bun), "test"], cwd=ROOT / "omp-samplers", check=True)
    subprocess.run([str(bun), "run", "typecheck"], cwd=ROOT / "omp-samplers", check=True)
    remote("test \"$(hostname)\" = alpha-h200 && test -r /home/ubuntu/glm53-vllm/server.yaml")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    release = f"/home/ubuntu/glm53-vllm/custom-samplers-releases/{stamp}"
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for name in ["src", "install_server.py", "verify_server.py", "pyproject.toml", "README.md"]:
            tar.add(ROOT / name, arcname=name, filter=lambda info: None if "__pycache__" in info.name else info)
    remote(f"mkdir -p {shlex.quote(release)} && tar -xzf - -C {shlex.quote(release)}", archive.getvalue())
    remote(shlex.join(["/home/ubuntu/glm53-vllm/.venv/bin/python", release + "/install_server.py"]))
    # Remote CUDA/API validation has passed. Only now activate the client adapter.
    backup = Path.home() / "glm53-vllm-client" / ("sampler-backup-" + stamp)
    backup.mkdir(mode=0o700)
    written = []
    try:
        for source, target in changes:
            rel = target.relative_to(EXTENSION)
            if target.exists():
                saved = backup / rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            written.append(target)
            shutil.copy2(source, target)
    except BaseException:
        for target in reversed(written):
            saved = backup / target.relative_to(EXTENSION)
            if saved.exists():
                shutil.copy2(saved, target)
            else:
                target.unlink()
        raise
    print(json.dumps({"deployed": True, "server_release": release, "extension_backup": str(backup),
                      "next": "Restart oh-my-pi with omp-glm53 --continue; saved sampler profile is preserved"}, indent=2))


if __name__ == "__main__":
    main()
