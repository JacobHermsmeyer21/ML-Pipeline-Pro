"""Opt-in browser deletion acceptance against an isolated, unauthenticated test stack."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:18000")
    parser.add_argument(
        "--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    project = "deletion_browser_" + uuid4().hex[:12]
    raw = Path("examples/data/classification.csv").read_bytes()
    report = {
        "project": project,
        "origin": args.origin,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "checks": [],
    }
    with httpx.Client(
        base_url=args.origin + "/api/v1",
        headers={"X-Project-ID": project},
        trust_env=False,
        timeout=30,
    ) as client:

        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            assert response.is_success, response.text
            return response.json()

        def upload(name):
            return post(
                "/datasets/upload",
                content=raw,
                headers={"Content-Type": "text/csv"},
                params=[
                    ("name", name),
                    ("version", "v1"),
                    ("feature_columns", "feature_1"),
                    ("feature_columns", "feature_2"),
                ],
            )

        data = upload("erase_dataset")
        shared = post(
            "/datasets",
            json={
                "name": "shared_input",
                "version": "v1",
                "uri": data["uri"],
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        model = post("/models", json={"name": "keep_classifier"})
        erased_model = post("/models", json={"name": "erase_classifier"})

        def train(dataset, classifier):
            body = {
                "dataset_id": dataset["id"],
                "model_id": classifier["id"],
                "config": {"epochs": 1, "hidden_units": 4, "max_runtime_seconds": 30},
            }
            key = uuid4().hex
            run = post("/experiments", json=body, headers={"Idempotency-Key": key})
            deadline = time.monotonic() + 90
            while run["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(0.2)
                response = client.get("/experiments/" + run["id"])
                response.raise_for_status()
                run = response.json()
            assert run["status"] == "succeeded", run
            for artifact in run["artifacts"]:
                content = client.get(
                    f"/experiments/{run['id']}/artifacts/{artifact['name']}"
                ).content
                assert len(content) == artifact["size_bytes"]
                assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
            version = post(
                f"/models/{classifier['id']}/versions",
                json={"version": "v1", "experiment_id": run["id"]},
            )
            return run, version, body, key

        run1, version1, body1, key1 = train(data, model)
        run2, version2, body2, key2 = train(shared, erased_model)
        report["runs"] = [run1["id"], run2["id"]]
        report["checks"].append("two real serial training jobs and hash-verified artifacts")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            try:
                page.goto(args.origin + "/dashboard/")
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(project)
                page.locator("#connection-form button[type=submit]").click()
                expect(page.locator("#project-label")).to_have_text(project)
                expect(page.locator("#training-dataset option")).to_have_count(3)
                page.locator('[data-view="datasets"]').click()
                card = page.locator("#datasets-list .record-card").filter(
                    has_text="erase_dataset / v1"
                )
                card.get_by_role("button", name="Delete dataset", exact=True).click()
                expect(page.locator("#review-confirm")).to_have_text("Permanently delete")
                expect(page.locator("#review-content")).to_contain_text("Shared files kept")
                page.screenshot(path=str(args.output / "dataset-confirmation-1440.png"))
                page.locator("#review-dialog").get_by_role(
                    "button", name="Back", exact=True
                ).click()
                assert client.get("/datasets/" + data["id"]).status_code == 200
                report["checks"].append("cancel leaves data unchanged")
                card.get_by_role("button", name="Delete dataset", exact=True).click()
                page.locator("#review-confirm").click(click_count=2)
                expect(page.locator("#global-message")).to_contain_text(
                    "Permanently deleted", timeout=30000
                )
                expect(card).to_have_count(0)
                assert client.get("/datasets/" + data["id"]).status_code == 404
                assert client.get("/experiments/" + run1["id"]).status_code == 404
                assert (
                    client.get(f"/models/{model['id']}/versions/{version1['id']}").status_code
                    == 404
                )
                assert client.get("/models/" + model["id"]).status_code == 200
                assert client.get("/datasets/" + shared["id"]).status_code == 200
                assert client.get("/experiments/" + run2["id"]).status_code == 200
                assert (
                    client.post(
                        "/experiments", json=body1, headers={"Idempotency-Key": key1}
                    ).status_code
                    == 410
                )
                report["checks"].append(
                    "dataset cascade, double click, shared input and unrelated run survive"
                )

                page.locator('[data-view="runs"]').click()
                active = post(
                    "/experiments",
                    json={
                        "dataset_id": shared["id"],
                        "model_id": erased_model["id"],
                        "config": {
                            "epochs": 500,
                            "batch_size": 1,
                            "hidden_units": 512,
                            "max_runtime_seconds": 8,
                        },
                    },
                    headers={"Idempotency-Key": uuid4().hex},
                )
                page.locator("#models-manage-open").click()
                page.locator("#models-list .record-card").filter(
                    has_text="erase_classifier"
                ).get_by_role("button", name="Delete model", exact=True).click()
                expect(page.locator("#review-content")).to_contain_text(
                    "wait for these jobs to finish"
                )
                expect(page.locator("#review-confirm")).to_be_hidden()
                page.screenshot(path=str(args.output / "active-worker-blocked.png"))
                page.locator("#review-dialog").get_by_role(
                    "button", name="Back", exact=True
                ).click()
                deadline = time.monotonic() + 45
                while active["status"] in {"queued", "running"} and time.monotonic() < deadline:
                    time.sleep(0.2)
                    active = client.get("/experiments/" + active["id"]).json()
                assert active["status"] in {"succeeded", "failed"}, active
                report["active_worker_terminal_status"] = active["status"]
                report["checks"].append("actual queued/running worker blocks browser confirmation")
                page.locator("#models-manage-open").click()
                model_card = page.locator("#models-list .record-card").filter(
                    has_text="erase_classifier"
                )
                model_card.get_by_role("button", name="Delete model", exact=True).click()
                page.set_viewport_size({"width": 1280, "height": 800})
                page.screenshot(path=str(args.output / "model-confirmation-1280.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                lost = []
                pattern = f"**/api/v1/models/{erased_model['id']}"

                def lose_response(route):
                    if route.request.method != "DELETE":
                        route.continue_()
                        return
                    response = route.fetch()
                    assert response.status == 200, response.text()
                    lost.append(response.json())
                    route.abort("failed")

                page.route(pattern, lose_response)
                page.locator("#review-confirm").click()
                expect(page.locator("#deletion-recovery")).to_be_visible(timeout=30000)
                expect(
                    page.get_by_role("button", name="Check / resume same deletion", exact=True)
                ).to_be_enabled(timeout=30000)
                assert len(lost) == 1
                page.screenshot(path=str(args.output / "lost-response-recovery-1280.png"))
                page.unroute(pattern, lose_response)
                page.reload()
                expect(page.locator("#deletion-recovery")).to_be_visible()
                page.get_by_role("button", name="Check / resume same deletion", exact=True).click()
                expect(page.locator("#deletion-recovery")).to_be_hidden(timeout=30000)
                expect(page.locator("#global-message")).to_contain_text("Permanently deleted")
                assert client.get("/models/" + erased_model["id"]).status_code == 404
                assert client.get("/experiments/" + run2["id"]).status_code == 404
                assert client.get("/datasets/" + shared["id"]).status_code == 200
                assert (
                    client.post(
                        "/experiments", json=body2, headers={"Idempotency-Key": key2}
                    ).status_code
                    == 410
                )
                report["checks"].append(
                    "model cascade, lost response, reload and same-key recovery"
                )

                assert (
                    post("/models", json={"name": erased_model["name"]})["id"] != erased_model["id"]
                )
                assert upload(data["name"])["id"] != data["id"]
                # Real training proves the surviving shared input remains readable.
                train(shared, model)
                page.reload()
                expect(page.locator("#training-dataset option")).to_have_count(3)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(args.output / "completed-workspace-1280.png"))
                report["checks"].append(
                    "name reuse, surviving shared-file training and 1280/1440 layouts"
                )
                # Hold an old project's preview while switching to a new project.
                held = []
                preview_pattern = f"**/api/v1/datasets/{shared['id']}/deletion-preview"

                def hold_preview(route):
                    held.append((route, route.fetch()))

                page.route(preview_pattern, hold_preview)
                page.locator('[data-view="datasets"]').click()
                page.locator("#datasets-list .record-card").filter(
                    has_text="shared_input / v1"
                ).get_by_role("button", name="Delete dataset", exact=True).click()
                for _ in range(40):
                    if held:
                        break
                    page.wait_for_timeout(25)
                assert held
                other_project = "deletion_other_" + uuid4().hex[:12]
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(other_project)
                page.locator("#connection-form button[type=submit]").click()
                expect(page.locator("#project-label")).to_have_text(other_project)
                held[0][0].fulfill(response=held[0][1])
                expect(page.locator("#review-dialog")).not_to_be_visible()
                expect(page.locator("#datasets-list")).not_to_contain_text("shared_input")
                report["checks"].append("late deletion preview cannot enter a different project")
                assert not errors, errors
                report["page_errors"] = errors
                report["browser"] = browser.version
                report["status"] = "passed"
            except BaseException:
                report["status"] = "failed"
                page.screenshot(path=str(args.output / "failure.png"))
                raise
            finally:
                (args.output / "result.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                browser.close()
        # Only this freshly generated test project is eligible for fixture cleanup.
        assert project.startswith("deletion_browser_")
        for kind in ("models", "datasets"):
            items = client.get(f"/{kind}?limit=100").json()["items"]
            for item in items:
                preview = client.get(f"/{kind}/{item['id']}/deletion-preview").json()
                response = client.request(
                    "DELETE",
                    f"/{kind}/{item['id']}",
                    json={"preview_sha256": preview["preview_sha256"]},
                    headers={"Idempotency-Key": uuid4().hex},
                )
                assert response.status_code == 200, response.text
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
