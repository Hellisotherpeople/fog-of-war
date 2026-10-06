#!/usr/bin/env python3
"""Exercise the installed OMP extension, tools, temperature commands and compaction.

Uses an isolated agent directory. The capture proxy records sampling fields only;
it never records credentials or prompt text, and forwards to the local SSH tunnel.
"""
from __future__ import annotations

import argparse
import collections
import http.client
import http.server
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

CLIENT = Path.home() / "glm53-vllm-client"
CHAIN = ["dry", "top_n_sigma", "p_less", "min_k", "xtc", "min_p", "temperature"]
FIELDS = ["model", "temperature", "min_p", "top_p", "top_k", "repetition_penalty",
          "presence_penalty", "frequency_penalty", "vllm_xargs", "reasoning_effort",
          "max_tokens", "max_completion_tokens", "max_output_tokens", "stream"]


def main(root: Path):
    root.mkdir(parents=True, mode=0o700)
    agent, project = root / "agent", root / "project"
    agent.mkdir(mode=0o700)
    project.mkdir()
    requests = []

    class Proxy(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            entry = {"method": self.command, "path": self.path}
            if body:
                payload = json.loads(body)
                entry.update({key: payload[key] for key in FIELDS if key in payload})
                entry["roles"] = dict(collections.Counter(m["role"] for m in payload.get("messages", [])))
                entry["tools"] = [t.get("function", {}).get("name") for t in payload.get("tools", [])]
            requests.append(entry)
            connection = http.client.HTTPConnection("127.0.0.1", 8800, timeout=1800)
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "connection", "accept-encoding")}
            try:
                connection.request(self.command, self.path, body=body or None, headers=headers)
                response = connection.getresponse()
                entry["status"] = response.status
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in ("transfer-encoding", "connection", "content-length"):
                        self.send_header(key, value)
                self.end_headers()
                while chunk := response.readline():
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                entry["client_disconnected"] = True
            finally:
                connection.close()
                with (root / "requests.jsonl").open("a") as output:
                    output.write(json.dumps(entry) + "\n")

        do_POST = do_GET = forward

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    provider = (CLIENT / "omp-provider.yml").read_text().replace(
        "http://127.0.0.1:8800/v1", f"http://127.0.0.1:{server.server_port}/v1")
    (agent / "models.yml").write_text(provider)
    (agent / "sampler-profile.json").write_text(json.dumps({
        "enabled": True, "mode": "manual", "chain": CHAIN,
        "params": {"dry_multiplier": 0.2, "dry_base": 1.75, "dry_allowed_length": 2,
                   "dry_penalty_last_n": -1, "top_n_sigma": 2, "p_less_exponent": 6,
                   "p_less_norm": False, "min_k_tau": 0.1, "xtc_probability": 0.1,
                   "xtc_threshold": 0.1, "min_p": 0.1, "temperature": 1},
        "scope": {"capture": True, "proxy": True, "probeMode": "post", "nProbs": 20,
                  "widget": False, "slots": True, "jsonl": True},
    }, indent=2))
    (root / "compact-test.yml").write_text("compaction:\n  keepRecentTokens: 1\n")
    (project / "totals.py").write_text(
        'def running_totals(values):\n    """Return each prefix sum without changing the input."""\n'
        '    result = []\n    total = 0\n    for value in values:\n'
        '        total = value\n        result.append(total)\n    return result\n')
    (project / "test_totals.py").write_text(
        (CLIENT / "omp-sampler-live-test/project/test_totals.py").read_text())

    stderr = (root / "stderr.log").open("w")
    events = (root / "events.jsonl").open("w")
    process = subprocess.Popen([
        str(Path.home() / ".local/bin/omp-glm53"), "--cwd", str(project),
        "--config", str(root / "compact-test.yml"), "--no-session", "--no-extensions",
        "-e", str(Path.home() / "Downloads/omp-samplers/index.ts"),
        "--no-skills", "--no-rules", "--no-title", "--no-lsp", "--no-pty",
        "--tools", "read,edit,bash", "--auto-approve", "--mode", "rpc", "--max-time", "30m",
    ], env=dict(os.environ, PI_CODING_AGENT_DIR=str(agent)), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    inbox = queue.Queue()
    tool_names = set()

    def read_events():
        for line in process.stdout:
            events.write(line)
            events.flush()
            try:
                inbox.put(json.loads(line))
            except json.JSONDecodeError:
                pass
        inbox.put(None)

    threading.Thread(target=read_events, daemon=True).start()

    def next_event():
        event = inbox.get(timeout=1800)
        if event is None:
            raise RuntimeError("OMP exited: " + (root / "stderr.log").read_text()[-2000:])
        if event.get("type") == "extension_error":
            raise RuntimeError(event)
        if event.get("type") == "tool_execution_start":
            tool_names.add(event["toolName"])
            print("Tool:", event["toolName"], flush=True)
        if event.get("type") == "message_end" and event.get("message", {}).get("stopReason") == "error":
            raise RuntimeError(event["message"].get("errorMessage"))
        return event

    def prompt(identifier, message):
        process.stdin.write(json.dumps({"id": identifier, "type": "prompt", "message": message}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            event = next_event()
            if event.get("id") != identifier:
                continue
            if event.get("type") == "response":
                if not event.get("success"):
                    raise RuntimeError(event)
                if event.get("data", {}).get("agentInvoked") is False:
                    return
            if event.get("type") == "prompt_result":
                if event.get("status") != "completed":
                    raise RuntimeError(event)
                return
        raise TimeoutError(identifier)

    try:
        while next_event().get("type") != "ready":
            pass
        prompt("settings", "/samplers show")
        prompt("coding", "Fix running_totals in totals.py so all test_totals.py cases pass. Use read to inspect both files, edit to make the fix, and bash to run python3 -m unittest -v. Do not change test_totals.py, install anything, access the network, or delegate. Finish with a brief test result.")
        subprocess.run(["python3", "-m", "unittest", "-v"], cwd=project, check=True)
        assert {"read", "edit", "bash"} <= tool_names, tool_names
        coding_end = len(requests)
        # Restrict the survivor set while exercising real requests above the
        # OpenAI temperature cap and at infinity; no top-p/top-k is enabled.
        prompt("test-chain", "/samplers chain min_p temperature")
        prompt("test-min-p", "/samplers min_p 1")
        for identifier, value in [("ten", "10"), ("infinity", "inf")]:
            prompt("temperature-" + identifier, "/temp " + value)
            prompt("request-" + identifier, "Reply with exactly OK.")
        prompt("restore-temperature", "/temp 1")
        prompt("restore-min-p", "/samplers min_p 0.1")
        prompt("restore-chain", "/samplers chain " + " ".join(CHAIN))
        compact_start = len(requests)
        process.stdin.write(json.dumps({"id": "compact", "type": "compact",
            "customInstructions": "Briefly preserve the code fix, test result and sampler settings."}) + "\n")
        process.stdin.flush()
        while True:
            event = next_event()
            if event.get("type") == "response" and event.get("id") == "compact":
                assert event.get("success"), event
                assert event.get("data", {}).get("summary"), event
                (root / "compaction-result.json").write_text(json.dumps(event, indent=2) + "\n")
                break
        process.stdin.close()
        process.wait(timeout=30)
        assert process.returncode == 0, process.returncode
        generations = [r for r in requests if r["method"] == "POST" and r["path"].endswith("/chat/completions")]
        assert generations
        configs = []
        for req in generations:
            assert req.get("status") == 200, req
            assert not any(k in req for k in ["max_tokens", "max_completion_tokens", "max_output_tokens"]), req
            assert all(req.get(k) == v for k, v in {"temperature": 1, "min_p": 0, "top_p": 1, "top_k": -1,
                "repetition_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0}.items()), req
            configs.append(json.loads(req["vllm_xargs"]["omp_sampler_config"]))
        assert any(c["params"].get("temperature") == 10 for c in configs)
        assert any(c["params"].get("temperature") == "inf" for c in configs)
        compact_requests = [r for r in requests[compact_start:] if r["method"] == "POST"]
        assert compact_requests
        assert all(json.loads(r["vllm_xargs"]["omp_sampler_config"])["chain"] == CHAIN for r in compact_requests)
        assert all(json.loads(r["vllm_xargs"]["omp_sampler_config"])["chain"] == CHAIN
                   for r in requests[:coding_end] if r["method"] == "POST")
        assert not any("/props" in r["path"] for r in requests)
        assert "Unauthorized" not in (root / "stderr.log").read_text()
        result = {"passed": True, "coding_tools": sorted(tool_names), "code_tests": 4,
                  "generations": len(generations), "chain": CHAIN, "temperature_10_and_infinity": True,
                  "compaction_custom_chain": True, "fixed_output_cap_absent": True,
                  "native_filters_neutral": True, "llama_props_requests": 0}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        server.shutdown()
        server.server_close()
        stderr.close()
        events.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output.resolve())
