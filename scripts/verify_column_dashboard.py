"""Opt-in Chrome acceptance for column editing on an isolated local test stack."""

import argparse
import csv
import hashlib
import io
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    project = "columns_browser_" + uuid4().hex[:12]
    data = io.StringIO(newline="")
    writer = csv.writer(data)
    writer.writerow(["Age", "Category", "Missing", "Identifier", "__proto__", "Outcome"])
    for i in range(200):
        writer.writerow(
            [
                i % 20,
                "HIGH" if i % 4 < 2 else "LOW",
                "",
                f"id_{i}",
                f"code_{i}",
                "alpha" if i % 2 == 0 else "beta",
            ]
        )
    source = args.output / "raw-columns.csv"
    source.write_text(data.getvalue(), encoding="utf-8", newline="")
    report = {
        "project": project,
        "origin": args.origin,
        "checks": [],
        "runs": [],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
    }
    with httpx.Client(
        base_url=args.origin + "/api/v1",
        headers={"X-Project-ID": project},
        timeout=90,
        trust_env=False,
    ) as client:
        response = client.post("/models", json={"name": "column_classifier"})
        assert response.status_code == 201, response.text
        model = response.json()

        def datasets():
            response = client.get("/datasets?limit=100")
            assert response.status_code == 200, response.text
            return response.json()["items"]

        def train(dataset):
            response = client.post(
                "/experiments",
                headers={"Idempotency-Key": uuid4().hex},
                json={
                    "dataset_id": dataset["id"],
                    "model_id": model["id"],
                    "config": {"epochs": 2, "hidden_units": 4, "max_runtime_seconds": 30},
                },
            )
            assert response.status_code == 202, response.text
            run = response.json()
            deadline = time.monotonic() + 120
            while run["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(0.2)
                response = client.get("/experiments/" + run["id"])
                assert response.status_code == 200, response.text
                run = response.json()
            assert run["status"] == "succeeded", run
            for artifact in run["artifacts"]:
                response = client.get(f"/experiments/{run['id']}/artifacts/{artifact['name']}")
                assert response.status_code == 200, response.text
                assert len(response.content) == artifact["size_bytes"]
                assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
            report["runs"].append(run)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def connect():
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(project)
                page.locator("#connection-form button[type=submit]").click()
                expect(page.locator("#project-label")).to_have_text(project)

            try:
                page.goto(args.origin + "/dashboard/")
                connect()
                page.locator('[data-view="datasets"]').click()
                page.locator("#dataset-file").set_input_files(source)
                page.locator("#dataset-name").fill("raw_columns")
                page.locator("#dataset-target").select_option("Outcome")
                page.get_by_role("checkbox", name="Keep column Missing", exact=True).uncheck()
                page.get_by_role("checkbox", name="Keep column Identifier", exact=True).uncheck()
                page.get_by_role("checkbox", name="Keep column __proto__", exact=True).uncheck()
                expect(
                    page.get_by_role("checkbox", name="Keep column Outcome", exact=True)
                ).to_be_disabled()
                page.screenshot(path=str(args.output / "upload-column-selection-1440.png"))
                page.locator("#upload-submit").click()
                expect(page.locator("#encoding-summary")).to_contain_text(
                    "3 encoded features", timeout=30000
                )
                page.locator("#prepare-save").click()
                expect(page.locator("#upload-result")).to_contain_text(
                    "Dataset verified and saved", timeout=30000
                )
                parent = next(item for item in datasets() if item["name"] == "raw_columns")
                assert parent["row_counts"] == {"train": 140, "validation": 30, "test": 30}
                train(parent)
                report["checks"].append(
                    "drop missing/high-cardinality columns before preview; "
                    "upload and actual worker training"
                )

                def card(name, version):
                    return page.locator("#datasets-list .record-card").filter(
                        has=page.get_by_role("heading", name=f"{name} / {version}", exact=True)
                    )

                def edit(name, version, dropped, new_version):
                    card(name, version).get_by_role(
                        "button", name="Edit columns", exact=True
                    ).click()
                    expect(page.locator("#column-dialog")).to_be_visible()
                    page.locator("#column-version").fill(new_version)
                    page.locator("#column-version").press("Tab")
                    expect(page.locator("#column-choices input").first).to_be_focused()
                    page.get_by_role("checkbox", name=f"Keep {dropped}", exact=True).uncheck()
                    page.get_by_role("button", name="Preview column changes", exact=True).click()
                    expect(page.locator("#column-save")).to_be_enabled(timeout=30000)

                edit("raw_columns", "v1", "Category", "v2")
                expect(page.locator("#column-preview-result")).to_contain_text(
                    "3 → 1 encoded features"
                )
                page.locator("#column-save").click()
                page.locator("#review-dialog").get_by_role(
                    "button", name="Back", exact=True
                ).click()
                page.get_by_role("button", name="Close column editor", exact=True).click()
                assert len(datasets()) == 1
                report["checks"].append(
                    "cancel leaves the original dataset and file references unchanged"
                )
                edit("raw_columns", "v1", "Category", "v2")
                page.locator("#column-version").fill("v3")
                expect(page.locator("#column-save")).to_be_disabled()
                page.locator("#column-version").fill("v2")
                page.get_by_role("button", name="Preview column changes", exact=True).click()
                expect(page.locator("#column-save")).to_be_enabled(timeout=30000)
                page.set_viewport_size({"width": 1280, "height": 800})
                page.screenshot(path=str(args.output / "saved-column-editor-1280.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.locator("#column-save").click()
                page.locator("#review-confirm").click(click_count=2)
                expect(page.locator("#global-message")).to_contain_text(
                    "Saved raw_columns / v2", timeout=30000
                )
                child = next(item for item in datasets() if item["version"] == "v2")
                assert (
                    len(child["feature_columns"]) == 1
                    and child["row_counts"] == parent["row_counts"]
                )
                assert len(datasets()) == 2
                train(child)
                report["checks"].append(
                    "saved categorical group removal; invalidated preview; "
                    "duplicate-click protection; actual worker training"
                )

                csv_data = Path("examples/data/classification.csv").read_bytes()
                response = client.post(
                    "/datasets/upload",
                    params={
                        "name": "numeric",
                        "version": "v1",
                        "feature_columns": ["feature_1", "feature_2"],
                    },
                    content=csv_data,
                    headers={"Content-Type": "text/csv"},
                )
                assert response.status_code == 201, response.text
                numeric_parent = response.json()
                page.reload()
                connect()
                page.locator('[data-view="datasets"]').click()
                edit("numeric", "v1", "feature_1", "v2")

                def lose_response(route):
                    response = route.fetch()
                    assert response.status == 201
                    route.abort("failed")

                endpoint = f"**/api/v1/datasets/{numeric_parent['id']}/columns"
                page.route(endpoint, lose_response, times=1)
                page.locator("#column-save").click()
                page.locator("#review-confirm").click()
                expect(page.locator("#column-recovery")).to_be_visible(timeout=30000)
                expect(page.locator("#column-recovery")).to_contain_text("uncertain")
                page.reload()
                connect()
                page.locator('[data-view="datasets"]').click()
                expect(page.locator("#column-recovery")).to_be_visible()
                page.get_by_role(
                    "button", name="Check / retry same column save", exact=True
                ).click()
                expect(page.locator("#global-message")).to_contain_text(
                    "Saved numeric / v2", timeout=30000
                )
                numeric_child = next(
                    item
                    for item in datasets()
                    if item["name"] == "numeric" and item["version"] == "v2"
                )
                assert len([item for item in datasets() if item["name"] == "numeric"]) == 2
                train(numeric_child)
                report["checks"].append(
                    "numeric saved edit; committed response loss; refresh restores "
                    "same-request recovery; no duplicate; real worker training"
                )

                def erase(dataset):
                    path = f"/datasets/{dataset['id']}"
                    preview = client.get(path + "/deletion-preview")
                    assert preview.status_code == 200, preview.text
                    response = client.request(
                        "DELETE",
                        path,
                        headers={"Idempotency-Key": uuid4().hex},
                        json={"preview_sha256": preview.json()["preview_sha256"]},
                    )
                    assert response.status_code == 200, response.text
                    assert client.get(path).status_code == 404

                erase(parent)
                replay = client.post(
                    f"/datasets/{parent['id']}/columns",
                    json={
                        "version": child["version"],
                        "drop_columns": child["selection"]["drop_columns"],
                        "source_sha256": parent["sha256"],
                        "reviewed_sha256": child["selection"]["reviewed_sha256"],
                    },
                )
                assert replay.status_code == 200 and replay.json() == child
                train(child)
                erase(numeric_child)
                train(numeric_parent)
                report["checks"].append(
                    "actual shared-volume parent/child erasure preserves surviving "
                    "training inputs and parentless replay"
                )
                page.reload()
                connect()
                page.locator('[data-view="datasets"]').click()
                page.set_viewport_size({"width": 1440, "height": 900})
                page.screenshot(path=str(args.output / "saved-versions-1440.png"))
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(project + "_other")
                page.locator("#connection-form button[type=submit]").click()
                expect(page.locator("#datasets-list")).to_contain_text("Your first dataset")
                expect(page.locator("#column-recovery")).to_be_hidden()
                assert not page.locator("#column-dialog").is_visible()
                report["checks"].append(
                    "project switching clears editor state and scopes saved requests"
                )
                assert not errors, errors
                report["browser_errors"] = errors
                report["datasets"] = datasets()
                report["status"] = "passed"
            finally:
                browser.close()
                (args.output / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
    print(
        json.dumps(
            {
                "status": report.get("status", "failed"),
                "project": project,
                "checks": report["checks"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
