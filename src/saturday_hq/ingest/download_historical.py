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
from saturday_hq.config import (
    HISTORICAL_DOMAINS,
    MARKET_DOMAINS,
    SEASON_STATIC_DOMAINS,
    STATIC_DOMAINS,
    WEEKLY_DOMAINS,
    SaturdayHQConfig,
)


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _season_static_marker(config: SaturdayHQConfig, season: int) -> Path:
    return Path(f"{config.incremental_path}/_state/season_static_{season}.json")


def plan_domains(
    config: SaturdayHQConfig,
    season: int,
    mode: str = "weekly",
) -> List[str]:
    """Domains worth calling for this run, cheapest correct set.

    CFBD calls are the scarce resource, so a run pulls only what can have changed:

    - "market" -> lines only. This is the mid-week refresh.
    - "weekly" -> everything that moves when games are played, plus the season-static
      domains on the first in-season run of a season, plus static reference data if its
      file is missing.
    """
    if mode == "market":
        return list(MARKET_DOMAINS)

    domains = list(WEEKLY_DOMAINS)

    # Reference data that is published once. Only fetch when no copy exists anywhere yet,
    # checking the incremental drops too so a fetched copy is not re-fetched every week.
    for domain in STATIC_DOMAINS:
        in_historical = Path(
            f"{config.historical_path}/{domain}/year=0/{domain}.jsonl"
        ).exists()
        in_incremental = any(
            Path(config.incremental_path).glob(f"dt=*/{domain}/{domain}.jsonl")
        )
        if not in_historical and not in_incremental:
            domains.append(domain)

    # FBS membership, talent, recruiting: settled before kickoff, so once per season.
    if not _season_static_marker(config, season).exists():
        domains += list(SEASON_STATIC_DOMAINS)

    return domains


def mark_season_static_done(config: SaturdayHQConfig, season: int, manifest: List[dict]) -> None:
    """Record that a season's static domains were pulled, so later runs skip them.

    Only writes when every season-static domain came back without an error, so a partial
    failure retries next run instead of being silently skipped for the rest of the season.
    """
    pulled = {
        row["domain"]: row
        for row in manifest
        if row["domain"] in SEASON_STATIC_DOMAINS and not row.get("error")
    }
    if not all(domain in pulled for domain in SEASON_STATIC_DOMAINS):
        return
    marker = _season_static_marker(config, season)
    _ensure_dir(str(marker.parent))
    marker.write_text(
        json.dumps(
            {
                "season": season,
                "domains": list(SEASON_STATIC_DOMAINS),
                "written_at": datetime.now(timezone.utc).isoformat(),
                "rows": {d: pulled[d]["rows"] for d in SEASON_STATIC_DOMAINS},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


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
    season_types: Sequence[str] = ("regular", "postseason"),
) -> List[dict]:
    """In-season refresh path: write a dated drop under incremental/.

    Pass `domains` from plan_domains() rather than defaulting to every domain — the default
    is the full list, which costs 13 calls.
    """
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
                records = client.fetch_domain(
                    domain, year=year, week=week, season_types=season_types
                )
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
