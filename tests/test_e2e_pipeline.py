"""End-to-end pipeline test.

Tests the complete content generation flow:
  1. Create an idea in the Idea Pool
  2. Generate angles from a persona
  3. Dispatch an angle to a content pipeline
  4. Poll until pipeline completes
  5. Verify content record was created in status service
  6. Approve the content
  7. Verify final status

Run with:
    python -m pytest tests/test_e2e_pipeline.py -v
    # or standalone:
    python tests/test_e2e_pipeline.py --base-url http://localhost:8000
"""

import argparse
import sys
import time
from typing import Any

import requests

# ─── Config ────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds
POLL_TIMEOUT = 120  # seconds


class PipelineE2ETest:
    """Runs the full pipeline flow against a live FastAPI server."""

    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"
        self.results: list[dict[str, Any]] = []

    def _step(self, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append({"name": name, "passed": passed, "detail": detail})
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
        return passed

    def _get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base}{path}", **kwargs)

    def _post(self, path: str, json: dict | None = None) -> requests.Response:
        return self.session.post(f"{self.base}{path}", json=json)

    def _poll(self, path: str, done_statuses: set[str], timeout: int = POLL_TIMEOUT) -> dict:
        """Poll an endpoint until status is in done_statuses or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            resp = self._get(path)
            if resp.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue
            data = resp.json()
            status = data.get("status", "")
            if status in done_statuses:
                return data
            time.sleep(POLL_INTERVAL)
        return {"status": "timeout", "error": f"Timed out after {timeout}s"}

    # ─── Steps ─────────────────────────────────────────────

    def step_1_health_check(self) -> bool:
        """Verify API is reachable."""
        try:
            resp = self._get("/health")
            ok = resp.status_code == 200
            return self._step("Health check", ok, f"status={resp.status_code}")
        except requests.ConnectionError:
            return self._step("Health check", False, "Connection refused")

    def step_2_create_idea(self) -> str | None:
        """Create a test idea in the Idea Pool."""
        resp = self._post("/api/ideas", json={
            "title": "[E2E TEST] AI-powered content scheduling",
            "source": "e2e_test",
            "source_type": "manual",
            "raw_data": {
                "description": "How AI can optimize content publishing schedules",
                "keywords": ["ai", "content", "scheduling"],
            },
        })
        if resp.status_code in (200, 201):
            idea_id = resp.json().get("id")
            self._step("Create idea", True, f"id={idea_id}")
            return idea_id
        self._step("Create idea", False, f"status={resp.status_code} body={resp.text[:200]}")
        return None

    def step_3_generate_angles(self) -> dict | None:
        """Generate content angles from a test persona."""
        resp = self._post("/api/psychology/generate-angles", json={
            "persona_data": {
                "name": "E2E Test Persona",
                "pain_points": ["Too many tools", "Content burnout"],
                "goals": ["Automate content", "Grow audience"],
            },
            "content_type": "article",
            "count": 1,
        })
        if resp.status_code != 200:
            self._step("Generate angles (submit)", False,
                       f"status={resp.status_code} body={resp.text[:200]}")
            return None

        data = resp.json()
        task_id = data.get("task_id")
        self._step("Generate angles (submit)", True, f"task_id={task_id}")

        # Poll for completion
        result = self._poll(f"/api/psychology/angles-status/{task_id}",
                           {"completed", "failed"})
        status = result.get("status", "unknown")
        if status == "completed":
            angles = result.get("result", {}).get("angles", [])
            self._step("Generate angles (poll)", True, f"got {len(angles)} angle(s)")
            return result.get("result")
        self._step("Generate angles (poll)", False, f"status={status}")
        return None

    def step_4_dispatch_pipeline(self, angle_data: dict | None = None) -> tuple[str | None, str | None]:
        """Dispatch an angle to the content pipeline."""
        if angle_data is None:
            angle_data = {
                "title": "[E2E TEST] Content scheduling article",
                "hook": "Stop guessing when to publish.",
                "angle": "Data-driven approach to content timing",
                "content_type": "article",
                "narrative_thread": "Automation",
                "pain_point_addressed": "Content burnout",
                "confidence": 85,
            }

        resp = self._post("/api/psychology/dispatch-pipeline", json={
            "angle_data": angle_data,
            "target_format": "article",
        })
        if resp.status_code != 200:
            self._step("Dispatch pipeline", False,
                       f"status={resp.status_code} body={resp.text[:200]}")
            return None, None

        data = resp.json()
        task_id = data.get("task_id")
        content_id = data.get("content_record_id")
        self._step("Dispatch pipeline", True,
                   f"task_id={task_id} content_id={content_id}")

        # Poll for completion
        result = self._poll(f"/api/psychology/pipeline-status/{task_id}",
                           {"completed", "failed"}, timeout=POLL_TIMEOUT)
        status = result.get("status", "unknown")
        passed = status == "completed"
        self._step("Pipeline completion", passed, f"status={status}")
        return task_id, content_id

    def step_5_verify_content_record(self, content_id: str) -> bool:
        """Verify the content record exists in the status service."""
        resp = self._get(f"/api/status/content/{content_id}")
        if resp.status_code == 200:
            data = resp.json()
            title = data.get("title", "")
            status = data.get("status", "")
            return self._step("Verify content record", True,
                            f"title='{title[:40]}' status={status}")
        return self._step("Verify content record", False,
                         f"status={resp.status_code}")

    def step_6_approve_content(self, content_id: str) -> bool:
        """Transition content to approved."""
        resp = self._post(f"/api/status/content/{content_id}/transition", json={
            "to_status": "pending_review",
            "changed_by": "e2e_test",
        })
        if resp.status_code != 200:
            # Maybe already in pending_review, try approve directly
            pass

        resp = self._post(f"/api/status/content/{content_id}/transition", json={
            "to_status": "approved",
            "changed_by": "e2e_test",
        })
        passed = resp.status_code == 200
        return self._step("Approve content", passed,
                         f"status={resp.status_code}")

    def step_7_verify_final_status(self, content_id: str) -> bool:
        """Verify content is now approved."""
        resp = self._get(f"/api/status/content/{content_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            passed = status == "approved"
            return self._step("Final status check", passed, f"status={status}")
        return self._step("Final status check", False,
                         f"http_status={resp.status_code}")

    # ─── Runner ────────────────────────────────────────────

    def run(self) -> bool:
        """Run the full E2E pipeline test."""
        print("\n" + "=" * 60)
        print("E2E PIPELINE TEST")
        print("=" * 60)
        print(f"Target: {self.base}\n")

        # Step 1: Health
        if not self.step_1_health_check():
            print("\nAPI not reachable. Aborting.")
            return False

        # Step 2: Create idea
        idea_id = self.step_2_create_idea()
        # Non-blocking — idea pool is optional

        # Step 3: Generate angles
        angle_result = self.step_3_generate_angles()
        angle_data = None
        if angle_result and angle_result.get("angles"):
            angle_data = angle_result["angles"][0]

        # Step 4: Dispatch pipeline
        task_id, content_id = self.step_4_dispatch_pipeline(angle_data)
        if not content_id:
            print("\nPipeline dispatch failed. Aborting remaining steps.")
            return self._print_summary()

        # Step 5: Verify content record
        self.step_5_verify_content_record(content_id)

        # Step 6: Approve
        self.step_6_approve_content(content_id)

        # Step 7: Final status
        self.step_7_verify_final_status(content_id)

        return self._print_summary()

    def _print_summary(self) -> bool:
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        all_passed = passed == total

        print(f"\n{'=' * 60}")
        print(f"RESULTS: {passed}/{total} passed")
        if not all_passed:
            print("FAILED steps:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['name']}: {r['detail']}")
        print("=" * 60 + "\n")
        return all_passed


# ─── pytest integration ────────────────────────────────────

def test_e2e_pipeline_health():
    """Smoke test: API must be reachable."""
    t = PipelineE2ETest(DEFAULT_BASE_URL)
    assert t.step_1_health_check()


def test_e2e_pipeline_idea_creation():
    """Test idea creation in the pool."""
    t = PipelineE2ETest(DEFAULT_BASE_URL)
    idea_id = t.step_2_create_idea()
    assert idea_id is not None


def test_e2e_pipeline_full():
    """Full pipeline flow — requires all agents to be configured."""
    t = PipelineE2ETest(DEFAULT_BASE_URL)
    assert t.run()


# ─── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E pipeline test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--auth-token", default=None)
    args = parser.parse_args()

    test = PipelineE2ETest(args.base_url, args.auth_token)
    success = test.run()
    sys.exit(0 if success else 1)
