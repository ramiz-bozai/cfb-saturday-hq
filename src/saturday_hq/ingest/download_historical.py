"""Download CFBD historical JSONL files into a Unity Catalog Volume.

Usage pattern:
1. Notebook calls download_historical_to_volume(...)
2. Files land under /Volumes/<catalog>/bronze/cfbd_landing/historical/<domain>/year=YYYY/*.jsonl
3. Bronze load reads those files (and later incremental/ API drops).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from saturday_hq.cfbd_client import CFBDClient, dumps_jsonl
from saturday_hq.config import HISTORICAL_DOMAINS, SaturdayHQConfig


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def write_jsonl(path: str, records: list) -> int:
    _ensure_dir(str(Path(path).parent))
    payload = dumps_jsonl(records)
    Path(path).write_text(payload, encoding="utf-8")
    return len(records)


def download_historical_to_volume(
    client: CFBDClient,
    config: SaturdayHQConfig,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    domains: Optional[Sequence[str]] = None,
    years: Optional[Iterable[int]] = None,
) -> List[dict]:
    """Pull CFBD domains year-by-year and write JSONL into the Volume.

    Conferences are written once under year=0.
    """
    start = start_year or config.history_start_year
    end = end_year or config.current_season
    year_list = list(years) if years is not None else list(range(start, end + 1))
    domain_list = list(domains) if domains is not None else list(HISTORICAL_DOMAINS)
    pulled_at = datetime.now(timezone.utc).isoformat()
    manifest: List[dict] = []

    root = config.historical_path
    _ensure_dir(root)

    if "conferences" in domain_list:
        records = client.fetch_domain("conferences", year=0)
        out = f"{root}/conferences/year=0/conferences.jsonl"
        n = write_jsonl(out, records)
        manifest.append(
            {
                "domain": "conferences",
                "year": 0,
                "path": out,
                "rows": n,
                "pulled_at": pulled_at,
                "mode": "historical",
            }
        )

    for year in year_list:
        for domain in domain_list:
            if domain == "conferences":
                continue
            # Lines exist from ~2013; talent/recruiting/sp/ppa vary by year availability.
            try:
                records = client.fetch_domain(domain, year=year)
            except Exception as exc:  # noqa: BLE001 - continue backfill; log failure
                manifest.append(
                    {
                        "domain": domain,
                        "year": year,
                        "path": None,
                        "rows": 0,
                        "pulled_at": pulled_at,
                        "mode": "historical",
                        "error": str(exc),
                    }
                )
                continue

            out = f"{root}/{domain}/year={year}/{domain}.jsonl"
            n = write_jsonl(out, records)
            manifest.append(
                {
                    "domain": domain,
                    "year": year,
                    "path": out,
                    "rows": n,
                    "pulled_at": pulled_at,
                    "mode": "historical",
                }
            )

    manifest_path = f"{root}/_manifest/manifest_{pulled_at.replace(':', '-')}.json"
    _ensure_dir(str(Path(manifest_path).parent))
    Path(manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def download_incremental_to_volume(
    client: CFBDClient,
    config: SaturdayHQConfig,
    year: int,
    domains: Optional[Sequence[str]] = None,
    week: Optional[int] = None,
) -> List[dict]:
    """Daily/API path: write a dated drop under incremental/."""
    domain_list = list(domains) if domains is not None else list(HISTORICAL_DOMAINS)
    pulled_at = datetime.now(timezone.utc)
    date_str = pulled_at.strftime("%Y-%m-%d")
    ts = pulled_at.isoformat()
    root = f"{config.incremental_path}/dt={date_str}"
    _ensure_dir(root)
    manifest: List[dict] = []

    for domain in domain_list:
        try:
            if domain == "conferences":
                records = client.fetch_domain("conferences", year=0)
            else:
                records = client.fetch_domain(domain, year=year, week=week)
        except Exception as exc:  # noqa: BLE001
            manifest.append(
                {
                    "domain": domain,
                    "year": year,
                    "week": week,
                    "path": None,
                    "rows": 0,
                    "pulled_at": ts,
                    "mode": "incremental",
                    "error": str(exc),
                }
            )
            continue

        out = f"{root}/{domain}/{domain}.jsonl"
        n = write_jsonl(out, records)
        manifest.append(
            {
                "domain": domain,
                "year": year,
                "week": week,
                "path": out,
                "rows": n,
                "pulled_at": ts,
                "mode": "incremental",
            }
        )

    manifest_path = f"{root}/_manifest.json"
    Path(manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
