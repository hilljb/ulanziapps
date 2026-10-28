#!/usr/bin/env python3
"""Create the read-only identity that read_current.py and the clock use.

Safe to run again. An account, role, binding, or key that already exists is
left in place. Requires gcloud, already signed in, with permission to create
a service account, a custom role, a JSON key, and a project IAM binding.

What it creates, in order:

1. Service account tc002-nightscout-reader@PROJECT_ID.iam.gserviceaccount.com
2. Custom role tc002NightscoutReader, permission datastore.entities.get only.
3. An IAM binding conditioned on this Firestore database. Conditions can name
   a database (projects/PROJECT/databases/DATABASE). They cannot name the
   document current/entries. See README.md.
4. A JSON key at the path in secrets.toml, mode 0600. A key already at that
   path is kept. The file is gitignored.

Empty project_id is filled from `gcloud config get-value project`. The
service-account email is written back into secrets.toml.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time

from secrets_config import SECRETS_PATH, key_path, load_secrets, require, set_string

SA_ID = "tc002-nightscout-reader"
ROLE_ID = "tc002NightscoutReader"
PERMISSION = "datastore.entities.get"
CONDITION_TITLE = "read-firestore-database"
IAM_WAIT_SECONDS = 360
IAM_POLL_SECONDS = 15


def main() -> int:
    secrets = load_secrets()
    project = (secrets.get("gcp") or {}).get("project_id") or ""
    if not str(project).strip():
        project = _gcloud_project()
        set_string(SECRETS_PATH, "project_id", project)
        print(f"Set project_id to {project} in secrets.toml", file=sys.stderr)
    database = require(secrets, "gcp", "database_id")
    email = f"{SA_ID}@{project}.iam.gserviceaccount.com"
    role = f"projects/{project}/roles/{ROLE_ID}"
    expression = f'resource.name=="projects/{project}/databases/{database}"'

    _ensure_service_account(project, email)
    _ensure_role(project, role)
    _ensure_binding(project, email, role, expression)
    _ensure_key(email)
    set_string(SECRETS_PATH, "service_account_email", email)
    print(f"Reader {email}", file=sys.stderr)
    print(f"Condition {expression}", file=sys.stderr)
    return _wait_until_readable()


def _ensure_service_account(project: str, email: str) -> None:
    described = _gcloud(
        ["iam", "service-accounts", "describe", email, f"--project={project}"],
        check=False,
    )
    if described.returncode == 0:
        print(f"Service account {email} already exists", file=sys.stderr)
        return
    _gcloud(
        [
            "iam", "service-accounts", "create", SA_ID,
            f"--project={project}",
            "--display-name=TC002 Nightscout reader",
            "--description=Reads Firestore documents for the TC002 Nightscout display. Get only.",
        ]
    )
    print(f"Created service account {email}", file=sys.stderr)


def _ensure_role(project: str, role: str) -> None:
    described = _gcloud(["iam", "roles", "describe", ROLE_ID, f"--project={project}", "--format=json"], check=False)
    if described.returncode != 0:
        _gcloud(
            [
                "iam", "roles", "create", ROLE_ID,
                f"--project={project}",
                "--title=TC002 Nightscout reader",
                "--description=Read documents in one Firestore database. No list, write, delete, or export.",
                f"--permissions={PERMISSION}",
                "--stage=GA",
            ]
        )
        print(f"Created role {role}", file=sys.stderr)
        return
    current = json.loads(described.stdout or "{}")
    granted = current.get("includedPermissions") or []
    if granted == [PERMISSION]:
        print(f"Role {role} already grants {PERMISSION}", file=sys.stderr)
        return
    _gcloud(
        [
            "iam", "roles", "update", ROLE_ID,
            f"--project={project}",
            f"--permissions={PERMISSION}",
        ]
    )
    print(f"Updated role {role} to {PERMISSION} only", file=sys.stderr)


def _ensure_binding(project: str, email: str, role: str, expression: str) -> None:
    policy = json.loads(
        _gcloud(["projects", "get-iam-policy", project, "--format=json"]).stdout or "{}"
    )
    member = f"serviceAccount:{email}"
    for binding in policy.get("bindings") or []:
        condition = binding.get("condition") or {}
        if (
            binding.get("role") == role
            and member in (binding.get("members") or [])
            and condition.get("expression") == expression
        ):
            print("IAM binding already matches this database", file=sys.stderr)
            return
    _gcloud(
        [
            "projects", "add-iam-policy-binding", project,
            f"--member={member}",
            f"--role={role}",
            "--condition",
            f"expression={expression},title={CONDITION_TITLE},description=Read documents in this Firestore database only",
        ]
    )
    print("Added IAM binding", file=sys.stderr)


def _ensure_key(email: str) -> None:
    destination = key_path(load_secrets())
    if destination.is_file():
        print(f"Keeping existing key {destination.relative_to(SECRETS_PATH.parent)}", file=sys.stderr)
        return
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    _gcloud(
        [
            "iam", "service-accounts", "keys", "create", str(destination),
            f"--iam-account={email}",
        ]
    )
    destination.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"Wrote key {destination.relative_to(SECRETS_PATH.parent)}", file=sys.stderr)


def _wait_until_readable() -> int:
    """A new binding can take a few minutes before Firestore honors it."""
    from read_current import main as read_main

    deadline = time.time() + IAM_WAIT_SECONDS
    while True:
        code = read_main(["--check-access"])
        if code == 0:
            return 0
        if code != 2:
            return code
        if time.time() >= deadline:
            print(
                "The reading is still failing. Firestore can cache IAM for several minutes; "
                "re-run python3 read_current.py once more before changing the binding.",
                file=sys.stderr,
            )
            return code
        print(f"Waiting {IAM_POLL_SECONDS}s for the IAM binding to take effect", file=sys.stderr)
        time.sleep(IAM_POLL_SECONDS)


def _gcloud_project() -> str:
    result = _gcloud(["config", "get-value", "project"])
    project = (result.stdout or "").strip()
    if not project or project == "(unset)":
        raise SystemExit("secrets.toml project_id is empty and gcloud has no project set.")
    return project


def _gcloud(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    result = subprocess.run(
        ["gcloud", *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"gcloud {' '.join(args)} failed ({result.returncode})\n{detail}")
    return result


if __name__ == "__main__":
    sys.exit(main())
