"""End-to-end backend tests for Galaxy Legal — public preview URL, live Supabase + OpenAI.

Covers:
- Public URL routing and auth gating (health, 401s)
- Supabase password grant → Bearer token
- /api/auth/me
- Case CRUD (create + list + get)
- Document upload, dedupe by SHA-256, indexing
- Runs: types, create, poll, draft + evidences
- Anti-fantasma: each evidence.quote_excerpt is a verbatim substring of source text
- Draft approve (from workflow) + revision (201, version=2) + approve-revision (400)
"""
from __future__ import annotations

import io
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = "https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com"
SUPABASE_URL = "https://irzervhlczzzrydqfisn.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_ii9pbB_4IEbcCQduLxqlMg_-RitzSyv"
TEST_EMAIL = "e2e-test@galaxylegal.dev"
TEST_PASSWORD = "GalaxyLegal_e2e_2026!"

SPANISH_DOC = (
    "# Contrato de arrendamiento urbano\n\n"
    "El arrendador D. Juan Pérez García, con DNI 12345678A, cede en arrendamiento "
    "al arrendatario D. Carlos López Martínez, con DNI 87654321B, la vivienda sita "
    "en calle Mayor 42, 3º B, Madrid.\n\n"
    "El precio de la renta mensual se fija en mil doscientos euros (1.200 €) pagaderos "
    "por adelantado dentro de los primeros cinco días de cada mes mediante transferencia "
    "bancaria a la cuenta ES12 1234 5678 9012 3456 7890.\n\n"
    "La duración del contrato será de cinco años, prorrogables conforme al artículo 10 "
    "de la Ley de Arrendamientos Urbanos. El arrendatario entrega dos mensualidades "
    "en concepto de fianza, que quedarán depositadas según la normativa vigente.\n\n"
    "En caso de impago de dos mensualidades consecutivas, el arrendador podrá instar "
    "el desahucio conforme al artículo 27 de la LAU. Cualquier controversia se someterá "
    "a los juzgados de Madrid capital.\n\n"
    "Firmado en Madrid, a 15 de marzo de 2026.\n"
)


# ------------------------- fixtures -------------------------
@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Supabase login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="session")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def user_id(headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=20)
    assert r.status_code == 200
    return r.json()["id"]


# ------------------------- public URL & auth gating -------------------------
class TestPublicRoutes:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    @pytest.mark.parametrize("path", [
        "/api/cases",
        "/api/auth/me",
        "/api/documents?case_id=00000000-0000-0000-0000-000000000000",
        "/api/runs/types",
        "/api/drafts?case_id=00000000-0000-0000-0000-000000000000",
    ])
    def test_requires_auth(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert r.status_code == 401, f"{path} expected 401 got {r.status_code}"


# ------------------------- auth -------------------------
class TestAuth:
    def test_me(self, headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == TEST_EMAIL
        assert isinstance(data["id"], str) and len(data["id"]) > 0


# ------------------------- cases + full e2e -------------------------
class TestFullFlow:
    shared: dict = {}

    def test_create_case(self, headers):
        title = f"TEST_Reclamación ACME — e2e run {uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{BASE_URL}/api/cases",
            json={"title": title, "jurisdiccion": "civil", "materia": "arrendamientos"},
            headers=headers,
            timeout=20,
        )
        assert r.status_code == 201, r.text
        case = r.json()
        assert case["title"] == title
        assert "id" in case
        TestFullFlow.shared["case_id"] = case["id"]
        TestFullFlow.shared["case_title"] = title

    def test_list_and_get_case(self, headers):
        case_id = TestFullFlow.shared["case_id"]
        r = requests.get(f"{BASE_URL}/api/cases", headers=headers, timeout=20)
        assert r.status_code == 200
        assert any(c["id"] == case_id for c in r.json())

        r2 = requests.get(f"{BASE_URL}/api/cases/{case_id}", headers=headers, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["id"] == case_id

    def test_upload_document_and_dedupe(self, headers):
        case_id = TestFullFlow.shared["case_id"]
        file_bytes = SPANISH_DOC.encode("utf-8")
        files = {"file": ("contrato_test.txt", io.BytesIO(file_bytes), "text/plain")}
        data = {"case_id": case_id}
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )
        assert r.status_code == 201, r.text
        doc = r.json()
        for k in ["id", "filename", "status", "storage_path", "mime_type",
                  "size_bytes", "hash_sha256", "case_id", "pages_count"]:
            assert k in doc, f"missing field {k} in upload response: {doc}"
        assert doc["case_id"] == case_id
        assert doc["size_bytes"] == len(file_bytes)
        TestFullFlow.shared["doc_id"] = doc["id"]
        TestFullFlow.shared["doc_hash"] = doc["hash_sha256"]

        # Dedupe: re-upload same content → existing row returned (same id)
        files2 = {"file": ("contrato_test.txt", io.BytesIO(file_bytes), "text/plain")}
        r2 = requests.post(
            f"{BASE_URL}/api/documents/upload",
            headers=headers,
            files=files2,
            data={"case_id": case_id},
            timeout=60,
        )
        assert r2.status_code in (200, 201), r2.text
        assert r2.json()["id"] == doc["id"], "Dedupe failed: new row created for identical SHA-256"

    def test_document_indexing_ready(self, headers):
        doc_id = TestFullFlow.shared["doc_id"]
        deadline = time.time() + 30
        last = None
        while time.time() < deadline:
            r = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers, timeout=20)
            assert r.status_code == 200
            last = r.json()
            if last.get("status") == "ready":
                break
            time.sleep(2)
        assert last and last.get("status") == "ready", f"Document not ready in time: {last}"
        assert last.get("pages_count", 0) > 0
        assert last.get("indexed_at") is not None
        TestFullFlow.shared["texto_extraido"] = None  # filled next step

    def test_runs_types(self, headers):
        r = requests.get(f"{BASE_URL}/api/runs/types", headers=headers, timeout=20)
        assert r.status_code == 200
        types = r.json()
        assert isinstance(types, list) and len(types) >= 1
        ia = next((t for t in types if t["workflow_type"] == "initial_analysis"), None)
        assert ia is not None, f"initial_analysis not in registry: {types}"
        assert ia["title"] == "Análisis inicial"
        assert ia["draft_type"] == "initial_analysis"

    def test_create_and_poll_run(self, headers):
        case_id = TestFullFlow.shared["case_id"]
        r = requests.post(
            f"{BASE_URL}/api/runs",
            headers=headers,
            json={"case_id": case_id, "workflow_type": "initial_analysis"},
            timeout=30,
        )
        assert r.status_code == 202, r.text
        run = r.json()
        assert run["status"] == "queued"
        run_id = run["id"]
        TestFullFlow.shared["run_id"] = run_id

        deadline = time.time() + 120
        last = None
        statuses_seen = set()
        while time.time() < deadline:
            r = requests.get(f"{BASE_URL}/api/runs/{run_id}", headers=headers, timeout=20)
            assert r.status_code == 200
            last = r.json()
            statuses_seen.add(last.get("status"))
            if last.get("status") in ("completed", "failed", "needs_human"):
                break
            time.sleep(3)
        assert last is not None
        TestFullFlow.shared["run_final"] = last
        assert last["status"] in ("completed", "needs_human"), \
            f"Run did not reach a valid terminal state: {last}"
        if last["status"] == "completed":
            assert float(last.get("cost_usd", 0)) > 0, f"Expected cost > 0 got {last.get('cost_usd')}"

    def test_draft_and_evidences_antifantasma(self, headers):
        run_final = TestFullFlow.shared.get("run_final")
        if not run_final or run_final.get("status") != "completed":
            pytest.skip(f"Run not completed, skipping draft/evidence assertions. "
                        f"Status={run_final.get('status') if run_final else 'N/A'}")

        run_id = TestFullFlow.shared["run_id"]
        doc_id = TestFullFlow.shared["doc_id"]

        r = requests.get(f"{BASE_URL}/api/runs/{run_id}/draft", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        draft = r.json()
        assert "content_md" in draft and draft["content_md"]
        assert re.search(r"\[E:e\d+\]", draft["content_md"]), \
            f"No [E:exxx] markers in draft content_md: {draft['content_md'][:500]}"
        TestFullFlow.shared["draft_id"] = draft["id"]

        # Evidences
        r = requests.get(f"{BASE_URL}/api/runs/{run_id}/evidences", headers=headers, timeout=20)
        assert r.status_code == 200
        evidences = r.json()
        assert len(evidences) >= 1, "Expected at least 1 evidence"

        # Source text for anti-fantasma check
        r = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers, timeout=20)
        assert r.status_code == 200
        src_text = r.json().get("texto_extraido") or ""
        assert src_text, "Source document texto_extraido is empty"

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "")).strip().lower()

        src_norm = _norm(src_text)
        failures = []
        for ev in evidences:
            assert ev.get("verified") is True, f"Evidence not verified: {ev}"
            q = ev.get("quote_excerpt") or ""
            if _norm(q) not in src_norm:
                failures.append((ev.get("claim_id") or ev.get("external_id"), q))
        assert not failures, f"Anti-fantasma violation — quotes not substring of source: {failures}"

    def test_draft_approve_revision_and_revalidate(self, headers):
        """Fase 2-b: revisions now re-validate citations.

        - A revision that only adds prose with no new [E:xxx] markers is still
          valid because existing markers remain verified.
        - A revision that adds an UNKNOWN [E:xxx] marker must fail approval
          with HTTP 422.
        """
        draft_id = TestFullFlow.shared.get("draft_id")
        if not draft_id:
            pytest.skip("No draft to approve (run did not complete)")

        # Approve original (no parent_draft_id)
        r = requests.post(f"{BASE_URL}/api/drafts/{draft_id}/approve", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        approved = r.json()
        assert approved.get("status") == "approved"
        assert approved.get("approved_at") is not None

        # Revision A: plain text append, no new markers → revalidation passes.
        r = requests.post(
            f"{BASE_URL}/api/drafts/{draft_id}/revision",
            headers=headers,
            json={"content_md": (approved.get("content_md") or "") + "\n\n[revision manual para test]"},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        rev_ok = r.json()
        assert int(rev_ok.get("version", 0)) == 2
        assert rev_ok.get("citations_valid") is True
        # Approving it should succeed because all existing [E:xxx] markers are still verified.
        r = requests.post(f"{BASE_URL}/api/drafts/{rev_ok['id']}/approve", headers=headers, timeout=20)
        assert r.status_code == 200, f"Valid revision should approve, got {r.status_code}: {r.text}"

        # Revision B: introduces a fake [E:e999] → revalidation must flag and block approval.
        r = requests.post(
            f"{BASE_URL}/api/drafts/{draft_id}/revision",
            headers=headers,
            json={"content_md": (approved.get("content_md") or "") + "\n\nInvented reference [E:e999]"},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        rev_bad = r.json()
        assert rev_bad.get("citations_valid") is False
        assert "e999" in (rev_bad.get("unverified_markers") or [])
        r = requests.post(f"{BASE_URL}/api/drafts/{rev_bad['id']}/approve", headers=headers, timeout=20)
        assert r.status_code == 422, f"Bad revision should be blocked (422), got {r.status_code}: {r.text}"
