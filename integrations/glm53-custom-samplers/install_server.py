#!/usr/bin/env python3
"""Run ON alpha-h200 with /home/ubuntu/glm53-vllm/.venv/bin/python.

Activates an immutable release on PYTHONPATH, backs up config/launcher, restarts,
verifies CUDA and HTTP behavior, and restores the original files on failure.
It never changes model weights, context/output limits, or sampling defaults.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    import yaml
    from vllm.version import __version__
    if __version__.split("+")[0] != "0.30.0":
        raise RuntimeError("Expected existing vLLM 0.30.0 environment")
    if os.uname().nodename != "alpha-h200":
        raise RuntimeError("Expected alpha-h200; refusing to alter a different server")
    app = Path("/home/ubuntu/glm53-vllm")
    release = Path(__file__).resolve().parent
    server = app / "server.yaml"
    launcher = app / "serve.sh"
    config = yaml.safe_load(server.read_text())
    if config.get("max-model-len") != 1048576:
        raise RuntimeError("Full context setting changed; inspect configuration before deploying")
    if config.get("speculative-config"):
        raise RuntimeError("This port requires speculative decoding disabled")
    env = os.environ.copy()
    src = str(release / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    # Import and API validation before modifying the live service.
    subprocess.run([sys.executable, "-c", "from glm53_samplers.processor import OrderedSamplers; print('Processor import OK')"], env=env, check=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = app / "sampler-backups" / stamp
    backup.mkdir(parents=True, mode=0o700)
    for path in (server, launcher):
        shutil.copy2(path, backup / path.name)
    constructors = config.setdefault("logits-processors", [])
    if constructors and constructors != ["glm53_samplers.processor:OrderedSamplers"]:
        raise RuntimeError("Other custom processors are configured; inspect ordering before deploying")
    config["logits-processors"] = ["glm53_samplers.processor:OrderedSamplers"]
    script = launcher.read_text()
    lines = [line for line in script.splitlines() if "# glm53-ordered-samplers" not in line]
    insert = f'export PYTHONPATH={shlex.quote(src)}${{PYTHONPATH:+:$PYTHONPATH}} # glm53-ordered-samplers'
    at = next((i for i, line in enumerate(lines) if line.startswith("exec ")), None)
    if at is None:
        raise RuntimeError("Unexpected server launcher; no exec line")
    lines.insert(at, insert)
    changed = False
    try:
        changed = True
        server.write_text(yaml.safe_dump(config, sort_keys=False))
        launcher.write_text("\n".join(lines) + "\n")
        print("Restarting vllm-glm53; current generations will disconnect.", flush=True)
        subprocess.run(["sudo", "-n", "systemctl", "restart", "vllm-glm53"], check=True, timeout=300)
        # /health is unauthenticated in this service; wait without exposing the key.
        import urllib.request
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen("http://192.168.200.207:8000/health", timeout=10) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(5)
        else:
            raise RuntimeError("vLLM did not become healthy within 20 minutes")
        subprocess.run([sys.executable, str(release / "verify_server.py"), "--result", str(release / "server-validation.json")],
                       env=env, check=True, timeout=7200)
    except BaseException:
        if changed:
            for path in (server, launcher):
                shutil.copy2(backup / path.name, path)
            subprocess.run(["sudo", "-n", "systemctl", "restart", "vllm-glm53"], timeout=300, check=False)
            print(f"Restored original server configuration from {backup}", file=sys.stderr)
        raise
    print(json.dumps({"installed": True, "release": str(release), "backup": str(backup),
                      "validation": str(release / "server-validation.json")}))


if __name__ == "__main__":
    main()
