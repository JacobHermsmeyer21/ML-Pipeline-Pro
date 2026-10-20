"""Verify native locks across Compose containers and late delivery of an erased job."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from uuid import UUID, uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", default="mlpp-deletion-validation-20261019")
    parser.add_argument("--browser-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch(r"mlpp-deletion-validation-[a-zA-Z0-9_-]+", args.compose_project)
    browser = json.loads(args.browser_result.read_text(encoding="utf-8"))
    assert browser["status"] == "passed" and browser["project"].startswith("deletion_browser_")
    experiment_id = str(UUID(browser["runs"][1]))
    command = [
        "docker",
        "compose",
        "--project-name",
        args.compose_project,
        "-f",
        "compose.yaml",
        "-f",
        "tests/integration/compose.validation.yaml",
    ]

    def compose(*values):
        return subprocess.run(
            [*command, *values], check=True, capture_output=True, text=True, timeout=30
        ).stdout

    project = "native_lock_" + uuid4().hex
    prefix = (
        "import json, os, sys; from pathlib import Path; "
        "from ml_pipeline_pro.config import Settings; "
        "from ml_pipeline_pro.storage_control import control_root, native_lock; "
        "directory = control_root(Settings(), sys.argv[1]); "
        "path = directory / 'publication.lock'; "
    )
    holder = prefix + (
        "import time; lock = native_lock(path); lock.acquire(); "
        "(directory / 'holder.json').write_text(json.dumps({'pid': os.getpid()})); time.sleep(90)"
    )
    compose("exec", "-T", "-d", "api", "python", "-c", holder, project)
    ready = prefix + "print((directory / 'holder.json').exists())"
    for _ in range(30):
        if compose("exec", "-T", "worker", "python", "-c", ready, project).strip() == "True":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Container lock holder did not start")
    contender = prefix + (
        "\nfrom filelock import Timeout\n"
        "try:\n    lock = native_lock(path); lock.acquire()\n"
        "except Timeout:\n    print('blocked')\n"
        "else:\n    lock.release(); raise AssertionError('Native lock did not exclude worker')\n"
    )
    assert compose("exec", "-T", "worker", "python", "-c", contender, project).strip() == "blocked"
    kill = (
        prefix + "import signal; "
        "os.kill(json.loads((directory / 'holder.json').read_text())['pid'], signal.SIGKILL)"
    )
    compose("exec", "-T", "api", "python", "-c", kill, project)
    released = (
        prefix + "lock = native_lock(path); lock.acquire(); print('released'); lock.release()"
    )
    assert compose("exec", "-T", "worker", "python", "-c", released, project).strip() == "released"

    publish = (
        "import sys; from ml_pipeline_pro.config import Settings; "
        "from ml_pipeline_pro.queue import Publisher; "
        "Publisher(Settings()).publish(sys.argv[1], sys.argv[2])"
    )
    compose("exec", "-T", "worker", "python", "-c", publish, browser["project"], experiment_id)
    observed = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        lines = compose("logs", "--no-color", "--since", "90s", "worker").splitlines()
        observed = next(
            (line for line in lines if experiment_id in line and "not_claimed" in line), None
        )
        if observed:
            break
        time.sleep(0.2)
    assert observed, "Late erased job delivery was not observed"
    missing = (
        "import sys; from ml_pipeline_pro.config import Settings; "
        "print(not (Settings().artifact_root / sys.argv[1] / sys.argv[2]).exists())"
    )
    assert (
        compose(
            "exec", "-T", "api", "python", "-c", missing, browser["project"], experiment_id
        ).strip()
        == "True"
    )
    report = {
        "status": "passed",
        "compose_project": args.compose_project,
        "native_cross_container_exclusion": True,
        "native_process_death_release": True,
        "late_erased_job_not_claimed": True,
        "late_delivery_log": observed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
