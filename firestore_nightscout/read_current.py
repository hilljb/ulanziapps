#!/usr/bin/env python3
"""Print the live glucose value from Firestore.

This is the request the clock will repeat. It uses the service-account JSON
key, not the gcloud user login:

1. Sign a JWT (RS256) with the key. openssl does the signature.
2. Exchange it at https://oauth2.googleapis.com/token for an access token.
   The only scope is https://www.googleapis.com/auth/datastore.
3. GET the document in secrets.toml, normally current/entries.
4. Read fields.sgv.integerValue and print "{sgv} {units_label}".

Stdout is only that line. Progress and errors go to stderr.

    python3 read_current.py
    python3 read_current.py --check-access

--check-access also lists collections (that must be denied) and GETs another
document path. See README.md for what those results mean.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from secrets_config import key_path, load_secrets, require

TOKEN_URL = "https://oauth2.googleapis.com/token"
FIRESTORE_API = "https://firestore.googleapis.com/v1"
DATASTORE_SCOPE = "https://www.googleapis.com/auth/datastore"
TIMEOUT_SECONDS = 30


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the live glucose value from Firestore.")
    parser.add_argument(
        "--document",
        help="Document path to read instead of secrets.toml document_path.",
    )
    parser.add_argument(
        "--check-access",
        action="store_true",
        help="After the reading, confirm list is denied and report a second GET.",
    )
    parser.add_argument(
        "--expect-denied",
        action="store_true",
        help="Exit 0 when this GET is rejected with 403. Prints nothing on success.",
    )
    args = parser.parse_args(argv)

    secrets = load_secrets()
    gcp = secrets["gcp"]
    project = require(secrets, "gcp", "project_id")
    database = require(secrets, "gcp", "database_id")
    document = args.document or require(secrets, "gcp", "document_path")
    units = require(secrets, "display", "units_label")
    account = json.loads(key_path(secrets).read_text())

    status, body = get_document(account, project, database, document)
    if args.expect_denied:
        if status == 403:
            print(f"GET {document} denied (403)", file=sys.stderr)
            return 0
        print(f"GET {document} returned {status}, expected 403", file=sys.stderr)
        _print_error_body(body)
        return 1
    if status != 200:
        print(f"GET {document} failed ({status})", file=sys.stderr)
        _print_error_body(body)
        return 2 if status == 403 else 1

    print(_format_reading(body, units), flush=True)
    if not args.check_access:
        return 0
    return _check_access(account, project, database, document)


def get_document(account: dict, project: str, database: str, document: str) -> tuple[int, dict]:
    """Return (HTTP status, parsed JSON body)."""
    token = access_token(account)
    url = document_url(project, database, document)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return _request(request)


def access_token(account: dict) -> str:
    """Exchange a signed service-account JWT for a Datastore-scoped access token.

    A key created a moment ago can be rejected with invalid_grant until Google
    has published its public half. Retry that case a few times.
    """
    last = None
    for attempt in range(6):
        assertion = _sign_jwt(account)
        body = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }
        ).encode()
        request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
        status, payload = _request(request)
        if status == 200 and payload.get("access_token"):
            return payload["access_token"]
        last = (status, payload)
        error = payload.get("error") if isinstance(payload, dict) else None
        if status == 400 and error == "invalid_grant" and attempt < 5:
            print("Token exchange rejected the new key; retrying", file=sys.stderr)
            time.sleep(5)
            continue
        break
    raise SystemExit(f"Token exchange failed ({last[0]}): {last[1]}")


def document_url(project: str, database: str, document: str) -> str:
    project_q = urllib.parse.quote(project, safe="")
    database_q = urllib.parse.quote(database, safe="")
    path_q = "/".join(urllib.parse.quote(part, safe="") for part in document.split("/"))
    return f"{FIRESTORE_API}/projects/{project_q}/databases/{database_q}/documents/{path_q}"


def _sign_jwt(account: dict) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT", "kid": account["private_key_id"]}
    claims = {
        "iss": account["client_email"],
        "scope": DATASTORE_SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = f"{_b64url(header)}.{_b64url(claims)}".encode()
    signature = _openssl_sign(account["private_key"], signing_input)
    return f"{signing_input.decode()}.{_b64url(signature)}"


def _openssl_sign(private_key_pem: str, signing_input: bytes) -> bytes:
    directory = tempfile.mkdtemp(prefix="tc002-reader-")
    try:
        pem_path = Path(directory) / "key.pem"
        pem_path.write_text(private_key_pem)
        pem_path.chmod(0o600)
        try:
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(pem_path)],
                input=signing_input,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            raise SystemExit("openssl is not on PATH. It signs the service-account JWT.")
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"openssl could not sign the JWT: {detail}")
    return result.stdout


def _format_reading(payload: dict, units: str) -> str:
    fields = payload.get("fields") or {}
    sgv = _decode(fields.get("sgv"))
    if sgv is None:
        raise SystemExit("Document has no sgv field.")
    if isinstance(sgv, float) and sgv.is_integer():
        sgv = int(sgv)
    return f"{sgv} {units}"


def _decode(value):
    """Turn one Firestore REST value into a plain Python value."""
    if not isinstance(value, dict):
        return value
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "timestampValue" in value:
        return value["timestampValue"]
    if "mapValue" in value:
        return {key: _decode(item) for key, item in (value["mapValue"].get("fields") or {}).items()}
    if "arrayValue" in value:
        return [_decode(item) for item in (value["arrayValue"].get("values") or [])]
    return value


def _check_access(account: dict, project: str, database: str, document: str) -> int:
    list_status, list_body = _list_collections(account, project, database)
    if list_status == 403:
        print("list collections denied (403)", file=sys.stderr)
    else:
        print(f"list collections returned {list_status}, expected 403", file=sys.stderr)
        _print_error_body(list_body)
        return 1

    other = "current/not-entries" if document == "current/entries" else f"{document}-other"
    other_status, other_body = get_document(account, project, database, other)
    if other_status == 403:
        print(f"GET {other} denied (403)", file=sys.stderr)
    elif other_status == 404:
        print(
            f"GET {other} returned 404. The key may read other documents in this database; "
            "that path is empty. Firestore IAM conditions name a database, not one document.",
            file=sys.stderr,
        )
    elif other_status == 200:
        print(f"GET {other} returned 200. This key can read another document.", file=sys.stderr)
        return 1
    else:
        print(f"GET {other} returned {other_status}", file=sys.stderr)
        _print_error_body(other_body)
        return 1
    return 0


def _list_collections(account: dict, project: str, database: str) -> tuple[int, dict]:
    token = access_token(account)
    project_q = urllib.parse.quote(project, safe="")
    database_q = urllib.parse.quote(database, safe="")
    url = f"{FIRESTORE_API}/projects/{project_q}/databases/{database_q}/documents:listCollectionIds"
    request = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    return _request(request)


def _request(request: urllib.request.Request) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return error.code, payload


def _print_error_body(body: dict) -> None:
    message = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
    if message:
        print(message, file=sys.stderr)
    elif body:
        print(json.dumps(body), file=sys.stderr)


def _b64url(value) -> str:
    if isinstance(value, (dict, list)):
        raw = json.dumps(value, separators=(",", ":")).encode()
    elif isinstance(value, str):
        raw = value.encode()
    else:
        raw = value
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


if __name__ == "__main__":
    sys.exit(main())
