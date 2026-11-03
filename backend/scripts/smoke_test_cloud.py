"""Non-destructive smoke test for a deployed ExamFlow FastAPI service.

Usage:
  python scripts/smoke_test_cloud.py
  python scripts/smoke_test_cloud.py --base-url https://examflow-api.fastapicloud.dev
  python scripts/smoke_test_cloud.py --pdf "D:/path/to/question-paper.pdf"

The script prompts for the Admin email/password; credentials are not stored in source.
It tests public endpoints, login/session, OpenAPI route registration, and optionally PDF preview.
It does not create exams, students, moderators, or database records.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import httpx


def check(client: httpx.Client, method: str, path: str, expected: tuple[int, ...] = (200,)) -> bool:
    try:
        response = client.request(method, path)
    except httpx.HTTPError as exc:
        print(f"FAIL {method} {path}: connection error: {exc}")
        return False
    if response.status_code not in expected:
        print(f"FAIL {method} {path}: HTTP {response.status_code}: {response.text[:400]}")
        return False
    print(f"PASS {method} {path}: HTTP {response.status_code}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://examflow-api.fastapicloud.dev")
    parser.add_argument("--pdf", help="Optional local PDF to test authenticated extraction")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures = 0

    with httpx.Client(base_url=base, timeout=60, follow_redirects=True) as client:
        for path in ("/api/v1/health", "/api/v1/site/content", "/api/v1/public/exams"):
            if not check(client, "GET", path):
                failures += 1

        try:
            spec_response = client.get("/openapi.json")
            spec_response.raise_for_status()
            spec = spec_response.json()
            print(f"PASS GET /openapi.json: {len(spec.get('paths', {}))} paths registered")
            for path, operations in sorted(spec.get("paths", {}).items()):
                methods = ", ".join(method.upper() for method in operations if method.lower() in {"get", "post", "put", "patch", "delete"})
                print(f"  {methods:20} {path}")
        except Exception as exc:
            print(f"FAIL GET /openapi.json: {exc}")
            failures += 1

        email = input("Admin email: ").strip()
        password = getpass.getpass("Admin password: ")
        try:
            response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
            if response.status_code != 200:
                print(f"FAIL POST /api/v1/auth/login: HTTP {response.status_code}: {response.text[:400]}")
                failures += 1
            else:
                print("PASS POST /api/v1/auth/login: HTTP 200")
                if check(client, "GET", "/api/v1/auth/me") is False:
                    failures += 1

                if args.pdf:
                    pdf_path = Path(args.pdf)
                    if not pdf_path.is_file():
                        print(f"FAIL PDF preview: file not found: {pdf_path}")
                        failures += 1
                    else:
                        with pdf_path.open("rb") as stream:
                            upload = client.post(
                                "/api/v1/imports/pdf/preview",
                                files={"file": (pdf_path.name, stream, "application/pdf")},
                                timeout=180,
                            )
                        if upload.status_code == 200:
                            data = upload.json()
                            print(f"PASS PDF preview: {data.get('question_count_detected', 0)} questions; OCR used={data.get('ocr_used')}")
                            print(f"  metadata={data.get('metadata', {})}")
                            for warning in data.get("warnings", []):
                                print(f"  WARNING: {warning}")
                        else:
                            print(f"FAIL PDF preview: HTTP {upload.status_code}: {upload.text[:800]}")
                            failures += 1

                logout = client.post("/api/v1/auth/logout")
                if logout.status_code == 200:
                    print("PASS POST /api/v1/auth/logout: HTTP 200")
                else:
                    print(f"FAIL POST /api/v1/auth/logout: HTTP {logout.status_code}: {logout.text[:300]}")
                    failures += 1
        except httpx.HTTPError as exc:
            print(f"FAIL authentication smoke test: {exc}")
            failures += 1

    print(f"\nResult: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
