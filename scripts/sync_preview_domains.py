#!/usr/bin/env python3
"""Download Offseason Preview CFBD domains locally and sync to the UC Volume.

Usage (from repo root):

  source .venv/bin/activate && set -a && source .env && set +a
  PYTHONPATH=src python scripts/sync_preview_domains.py
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from saturday_hq.cfbd_client import CFBDClient
from saturday_hq.config import PREVIEW_DOMAINS, preview_season
from saturday_hq.ingest.download_historical import (
    download_historical_to_volume,
    download_preview_to_volume,
)


def _api_key() -> str:
    env_key = os.environ.get("CFBD_API_KEY")
    if env_key:
        return env_key
    out = subprocess.check_output(
        ["databricks", "secrets", "get-secret", "cfb_saturday_hq", "cfbd_api_key"],
        text=True,
    )
    return base64.b64decode(json.loads(out)["value"]).decode()


def _upload(local_path: Path, remote_path: str) -> None:
    cmd = [
        "databricks",
        "fs",
        "cp",
        "-r",
        "--overwrite",
        str(local_path),
        remote_path if remote_path.endswith("/") else remote_path + "/",
    ]
    print(" ".join(cmd))
    subprocess.check_call(cmd)


def main() -> None:
    upcoming = int(os.environ.get("PREVIEW_SEASON") or preview_season())
    prior = upcoming - 1
    hist_years = list(range(max(2021, prior - 1), prior + 1))

    local_root = Path(tempfile.mkdtemp(prefix="cfbd_preview_"))
    local = SimpleNamespace(
        historical_path=str(local_root / "historical"),
        incremental_path=str(local_root / "incremental"),
        volume_path=str(local_root),
        request_pause_seconds=0.15,
        history_start_year=hist_years[0],
        current_season=prior,
        cfbd_base_url="https://api.collegefootballdata.com",
    )

    print(f"local staging: {local_root}")
    print(f"historical years: {hist_years}")
    print(f"preview upcoming={upcoming} prior={prior}")

    client = CFBDClient(_api_key(), verify_ssl=False)
    client.config = local  # type: ignore[assignment]

    hist_domains = list(PREVIEW_DOMAINS)
    hist_manifest = download_historical_to_volume(
        client,
        local,  # type: ignore[arg-type]
        years=hist_years,
        domains=hist_domains,
    )
    print(
        "historical rows:",
        sum(m.get("rows", 0) for m in hist_manifest),
        "errors:",
        sum(1 for m in hist_manifest if m.get("error")),
    )

    preview_manifest = download_preview_to_volume(
        client,
        local,  # type: ignore[arg-type]
        upcoming_season=upcoming,
        domains=list(PREVIEW_DOMAINS),
    )
    print(
        "preview rows:",
        sum(m.get("rows", 0) for m in preview_manifest),
        "errors:",
        sum(1 for m in preview_manifest if m.get("error")),
    )
    for row in preview_manifest:
        if row.get("error"):
            print("  error:", row["domain"], row["year"], row["error"][:120])

    remote = "dbfs:/Volumes/cfb_saturday_hq_raw/landing/cfbd_landing"
    for domain_dir in (local_root / "historical").iterdir():
        if domain_dir.is_dir() and domain_dir.name != "_manifest":
            _upload(domain_dir, f"{remote}/historical/{domain_dir.name}")
    for dt_dir in (local_root / "incremental").glob("dt=*"):
        _upload(dt_dir, f"{remote}/incremental/{dt_dir.name}")

    print("sync complete")


if __name__ == "__main__":
    main()
