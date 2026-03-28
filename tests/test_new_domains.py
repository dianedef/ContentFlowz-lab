"""Tests for newly added domain endpoints (affiliations, activity, work-domains).

Run with:
    python -m pytest tests/test_new_domains.py -v
    # or standalone:
    python tests/test_new_domains.py --base-url http://localhost:8000
"""

import argparse
import sys

import requests

DEFAULT_BASE_URL = "http://localhost:8000"


class DomainTests:
    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"
        self.results: list[dict] = []

    def _step(self, name: str, passed: bool, detail: str = "") -> bool:
        status = "PASS" if passed else "FAIL"
        self.results.append({"name": name, "passed": passed, "detail": detail})
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
        return passed

    def _get(self, path: str) -> requests.Response:
        return self.session.get(f"{self.base}{path}")

    def _post(self, path: str, json: dict) -> requests.Response:
        return self.session.post(f"{self.base}{path}", json=json)

    def _put(self, path: str, json: dict) -> requests.Response:
        return self.session.put(f"{self.base}{path}", json=json)

    def _delete(self, path: str) -> requests.Response:
        return self.session.delete(f"{self.base}{path}")

    # ─── Affiliations ──────────────────────────────────────

    def test_affiliations_crud(self) -> bool:
        print("\n--- Affiliations CRUD ---")

        # List (may be empty)
        resp = self._get("/api/affiliations")
        self._step("List affiliations", resp.status_code == 200,
                   f"count={len(resp.json()) if resp.status_code == 200 else 'error'}")

        # Create
        resp = self._post("/api/affiliations", json={
            "name": "[TEST] Amazon Associates",
            "url": "https://affiliate-program.amazon.com",
            "category": "tech",
            "commission": "3-10%",
            "keywords": ["hosting", "tools", "software"],
            "status": "active",
            "notes": "E2E test affiliation",
        })
        if resp.status_code != 201:
            self._step("Create affiliation", False, f"status={resp.status_code} {resp.text[:100]}")
            return False
        aff_id = resp.json().get("id")
        self._step("Create affiliation", True, f"id={aff_id}")

        # Read
        resp = self._get(f"/api/affiliations/{aff_id}")
        self._step("Get affiliation", resp.status_code == 200)

        # Update
        resp = self._put(f"/api/affiliations/{aff_id}", json={
            "commission": "5-12%",
            "status": "paused",
        })
        if resp.status_code == 200:
            updated = resp.json()
            self._step("Update affiliation", True,
                       f"commission={updated.get('commission')} status={updated.get('status')}")
        else:
            self._step("Update affiliation", False, f"status={resp.status_code}")

        # Delete
        resp = self._delete(f"/api/affiliations/{aff_id}")
        self._step("Delete affiliation", resp.status_code == 200)

        # Verify deleted
        resp = self._get(f"/api/affiliations/{aff_id}")
        self._step("Verify deleted", resp.status_code == 404)

        return True

    # ─── Activity ──────────────────────────────────────────

    def test_activity(self) -> bool:
        print("\n--- Activity Log ---")

        # Create
        resp = self._post("/api/activity", json={
            "action": "e2e_test_run",
            "robotId": "test",
            "status": "completed",
            "details": {"test": True},
        })
        if resp.status_code == 201:
            self._step("Create activity", True, f"id={resp.json().get('id')}")
        else:
            self._step("Create activity", False, f"status={resp.status_code} {resp.text[:100]}")

        # List
        resp = self._get("/api/activity?limit=5")
        if resp.status_code == 200:
            items = resp.json()
            self._step("List activity", True, f"count={len(items)}")
        else:
            self._step("List activity", False, f"status={resp.status_code}")

        return True

    # ─── Work Domains ──────────────────────────────────────

    def test_work_domains(self) -> bool:
        print("\n--- Work Domains ---")

        # Create
        resp = self._post("/api/work-domains", json={
            "projectId": "test-project",
            "domain": "e2e_test",
            "status": "idle",
        })
        if resp.status_code == 201:
            domain_id = resp.json().get("id")
            self._step("Create work domain", True, f"id={domain_id}")
        else:
            self._step("Create work domain", False, f"status={resp.status_code} {resp.text[:100]}")
            return False

        # List
        resp = self._get("/api/work-domains")
        if resp.status_code == 200:
            self._step("List work domains", True, f"count={len(resp.json())}")
        else:
            self._step("List work domains", False, f"status={resp.status_code}")

        # Update
        resp = self._put(f"/api/work-domains/{domain_id}", json={
            "status": "running",
            "itemsPending": 5,
        })
        if resp.status_code == 200:
            data = resp.json()
            self._step("Update work domain", True,
                       f"status={data.get('status')} pending={data.get('itemsPending')}")
        else:
            self._step("Update work domain", False, f"status={resp.status_code}")

        return True

    # ─── Runner ────────────────────────────────────────────

    def run(self) -> bool:
        print("\n" + "=" * 60)
        print("NEW DOMAINS TEST")
        print("=" * 60)
        print(f"Target: {self.base}\n")

        # Health check first
        try:
            resp = self._get("/health")
            if resp.status_code != 200:
                print("API not healthy. Aborting.")
                return False
        except requests.ConnectionError:
            print("API not reachable. Aborting.")
            return False

        self.test_affiliations_crud()
        self.test_activity()
        self.test_work_domains()

        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        print(f"\n{'=' * 60}")
        print(f"RESULTS: {passed}/{total} passed")
        print("=" * 60 + "\n")
        return passed == total


# ─── pytest integration ────────────────────────────────────

def test_health():
    t = DomainTests(DEFAULT_BASE_URL)
    resp = t._get("/health")
    assert resp.status_code == 200


def test_new_domains_full():
    t = DomainTests(DEFAULT_BASE_URL)
    assert t.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="New domains test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--auth-token", default=None)
    args = parser.parse_args()

    test = DomainTests(args.base_url, args.auth_token)
    success = test.run()
    sys.exit(0 if success else 1)
