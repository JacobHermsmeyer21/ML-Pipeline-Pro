"""Opt-in browser/worker acceptance on a disposable upload-enabled local stack."""

import argparse
import hashlib
import io
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import torch
from playwright.sync_api import expect, sync_playwright
from sklearn.metrics import accuracy_score, f1_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    project = "logistic_browser_" + uuid4().hex[:12]
    report = {
        "project": project,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree": True,
        "torch": str(torch.__version__),
        "runs": [],
        "checks": [],
    }
    started = time.monotonic()
    with httpx.Client(
        base_url=args.origin + "/api/v1", headers={"X-Project-ID": project}, timeout=30
    ) as client:
        datasets = []
        for classes in (2, 3):
            rows = ["x,y,target,split"]
            centers = [(-4, -4), (4, -4), (0, 4)]
            for split, count in [("train", 20), ("validation", 6), ("test", 6)]:
                for label, (x, y) in enumerate(centers[:classes]):
                    rows.extend(
                        f"{x + i * 0.01},{y + (i % 3) * 0.02},{label},{split}" for i in range(count)
                    )
            content = ("\n".join(rows) + "\n").encode()
            response = client.post(
                "/datasets/upload",
                params=[
                    ("name", f"classes_{classes}"),
                    ("version", "v1"),
                    ("feature_columns", "x"),
                    ("feature_columns", "y"),
                ],
                content=content,
                headers={"Content-Type": "text/csv"},
            )
            assert response.status_code == 201, response.text
            datasets.append((response.json(), rows))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.origin + "/dashboard/")
            page.evaluate(
                "project => sessionStorage.setItem('mlpp:last-project', project)", project
            )
            # Use the real connection form, which is authoritative for current project selection.
            page.locator("#connection-open").click()
            page.locator("#connection-project").fill(project)
            page.locator("#connection-form button[type=submit]").click()
            expect(page.locator("#training-dataset option")).to_have_count(3)
            models = {}
            for algorithm in ("mlp", "logistic_regression"):
                page.locator("#model-create-open").click()
                expect(page.locator("#model-architecture")).to_have_value("mlp")
                page.locator("#model-architecture").select_option(algorithm)
                page.locator("#model-name").fill(algorithm)
                page.locator("#model-form button[type=submit]").click()
                expect(page.locator("#model-dialog")).not_to_be_visible()
                expect(page.locator("#global-message")).to_contain_text("Model created")
                models[algorithm] = next(
                    m for m in client.get("/models").json()["items"] if m["name"] == algorithm
                )
            for algorithm in ("mlp", "logistic_regression", "mlp", "logistic_regression"):
                page.locator("#training-model").select_option(models[algorithm]["id"])
                logistic = algorithm == "logistic_regression"
                # Settings are collapsed initially, so inspect applicability through disabled state.
                assert page.locator('[name="hidden_units"]').is_disabled() == logistic
                assert page.locator('[name="l2_strength"]').is_disabled() != logistic
            page.locator(".settings-details").first.locator("summary").click()
            submissions = []
            lose_next = [False]

            def intercept(route):
                if route.request.method == "POST":
                    submissions.append(
                        {
                            "body": route.request.post_data_json,
                            "key": route.request.headers.get("idempotency-key"),
                        }
                    )
                    if lose_next[0]:
                        lose_next[0] = False
                        route.fetch()  # Server accepts it; deliberately lose only the response.
                        route.abort()
                        return
                route.continue_()

            page.route("**/api/v1/experiments", intercept)
            for index, (algorithm, dataset_index) in enumerate(
                [("mlp", 0), ("logistic_regression", 0), ("logistic_regression", 1)]
            ):
                dataset, rows = datasets[dataset_index]
                model = models[algorithm]
                page.locator("#training-model").select_option(model["id"])
                page.locator("#training-dataset").select_option(dataset["id"])
                if page.locator(".settings-details").first.get_attribute("open") is None:
                    page.locator(".settings-details").first.locator("summary").click()
                page.locator('[name="epochs"]').fill("50")
                page.locator("#train-submit").click()
                text = page.locator("#review-content").inner_text()
                assert ("l2_strength" in text) == (algorithm == "logistic_regression")
                assert ("hidden_units" in text) == (algorithm == "mlp")
                before = len(submissions)
                lose_next[0] = index == 1
                page.locator("#review-confirm").click()
                if index == 1:
                    expect(page.locator("#training-recovery")).to_be_visible()
                    original = submissions[-1]
                    page.locator("#training-model").select_option(models["mlp"]["id"])
                    page.reload()
                    expect(page.locator("#training-recovery")).to_be_visible()
                    page.get_by_role("button", name="Check / retry same submission").click()
                    expect(page.locator("#training-recovery")).to_be_hidden(timeout=30000)
                    assert submissions[-1] == original
                    report["checks"].append(
                        "lost response, model switch, reload and immutable same-key replay"
                    )
                else:
                    expect(page.locator("#training-recovery")).to_be_hidden(timeout=30000)
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    records = client.get("/experiments").json()["items"]
                    matches = [
                        r
                        for r in records
                        if r["model_id"] == model["id"] and r["dataset_id"] == dataset["id"]
                    ]
                    if matches and matches[0]["status"] in {"succeeded", "failed"}:
                        record = matches[0]
                        break
                    time.sleep(0.25)
                else:
                    raise AssertionError("Worker did not finish")
                assert record["status"] == "succeeded", record
                assert len(submissions) > before
                artifacts = {}
                for artifact in record["artifacts"]:
                    response = client.get(
                        f"/experiments/{record['id']}/artifacts/{artifact['name']}"
                    )
                    assert response.status_code == 200
                    assert len(response.content) == artifact["size_bytes"]
                    assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
                    artifacts[artifact["name"]] = response.content
                checkpoint = torch.load(io.BytesIO(artifacts["model.pt"]), weights_only=True)
                features = len(dataset["feature_columns"])
                classes = dataset["num_classes"]
                if algorithm == "logistic_regression":
                    assert checkpoint["algorithm"] == algorithm
                    classifier = torch.nn.Linear(features, classes)
                else:
                    hidden = record["config"]["hidden_units"]
                    classifier = torch.nn.Sequential(
                        torch.nn.Linear(features, hidden),
                        torch.nn.ReLU(),
                        torch.nn.Linear(hidden, classes),
                    )
                classifier.load_state_dict(checkpoint["state_dict"])
                test = [row.split(",") for row in rows if row.endswith(",test")]
                x = torch.tensor([[float(r[0]), float(r[1])] for r in test])
                y = [int(r[2]) for r in test]
                predictions = (
                    classifier((x - checkpoint["mean"]) / checkpoint["std"]).argmax(1).tolist()
                )
                assert (
                    abs(accuracy_score(y, predictions) - record["metrics"]["test_accuracy"]) <= 1e-6
                )
                assert (
                    abs(f1_score(y, predictions, average="macro") - record["metrics"]["test_f1"])
                    <= 1e-6
                )
                # Force run details to refresh after terminal state.
                page.locator("#refresh-runs").click()
                row = page.locator("#runs-body tr").filter(has_text=record["id"][:8])
                row.get_by_role("button", name="View").click()
                expect(page.locator("#run-detail")).to_contain_text(
                    "Logistic regression" if algorithm == "logistic_regression" else "MLP"
                )
                page.screenshot(path=str(args.output / f"run-{index}.png"))
                report["runs"].append(record)
            # Last run uses the multiclass dataset; compare the two binary records through the API.
            ids = [r["id"] for r in report["runs"][:2]]
            comparison = client.get(
                "/experiments/compare", params=[("experiment_id", i) for i in ids]
            )
            assert comparison.status_code == 200, comparison.text
            report["comparison"] = comparison.json()
            page.locator('#run-detail [name="version"]').fill("v1")
            page.get_by_role("button", name="Register version", exact=True).click()
            expect(page.locator("#global-message")).to_contain_text("Model version registered")
            versions = client.get(f"/models/{models['logistic_regression']['id']}/versions").json()
            report["version"] = next(v for v in versions["items"] if v["version"] == "v1")
            assert report["version"]["experiment_id"] == report["runs"][-1]["id"]
            page.locator("#runs-body tr").filter(has_text=ids[1][:8]).get_by_role(
                "button", name="View"
            ).click()
            page.get_by_role("button", name="Compare validation results").click()
            expect(page.locator("#review-title")).to_have_text("Validation comparison")
            for identity in ids:
                expect(page.locator("#review-content")).to_contain_text(identity)
            page.screenshot(path=str(args.output / "comparison.png"))
            assert errors == [], errors
            report["checks"].extend(
                [
                    "model creation and switching; applicable review settings",
                    "three queued browser runs; binary comparison and multiclass logistic",
                    "hash/size; independent predictions and accuracy/macro-F1; registration",
                ]
            )
            browser.close()
    report["elapsed_seconds"] = time.monotonic() - started
    report["status"] = "passed"
    (args.output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "project": project, "runs": len(report["runs"])}))


if __name__ == "__main__":
    main()
