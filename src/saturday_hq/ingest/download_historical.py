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
    PREVIEW_DOMAINS,
    PREVIEW_PRIOR_DOMAINS,
    PREVIEW_UPCOMING_ONLY_DOMAINS,
    SEASON_STATIC_DOMAINS,
    STATIC_DOMAINS,
    WEEKLY_DOMAINS,
    SaturdayHQConfig,
    preview_season,
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
    """Domains worth calling for this run.

    - "market" -> lines only. Mid-week refresh.
    - "weekly" -> game/rating domains, plus season-static on first in-season run.
    - "preview" -> player-level Season Preview domains.
    """
    if mode == "market":
        return list(MARKET_DOMAINS)

    if mode == "preview":
        return list(PREVIEW_DOMAINS)

    domains = list(WEEKLY_DOMAINS)

    # Reference data that is published once, so it is fetched a single time ever.
    #
    # The check deliberately looks at the incremental tree only, ignoring the backfill's copy
    # under historical/. bronze models union a per-domain glob over incremental/, and
    # read_files() fails on a glob matching zero files — so every domain needs at least one
    # incremental file. Fetching this once costs one call and keeps that invariant true: the
    # first in-season run covers all of HISTORICAL_DOMAINS between the three tiers.
    for domain in STATIC_DOMAINS:
        if not any(Path(config.incremental_path).glob(f"dt=*/{domain}/{domain}.jsonl")):
            domains.append(domain)

    # FBS membership, talent, recruiting: settled before kickoff, so once per season.
    if not _season_static_marker(config, season).exists():
        domains += list(SEASON_STATIC_DOMAINS)

    return domains


def preview_years(today=None) -> List[int]:
    """Years a Season Preview pull should cover: upcoming season + prior completed season."""
    upcoming = preview_season(today)
    return [upcoming - 1, upcoming]


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


def _tag_teams_fbs_year(records: list, year: int) -> list:
    """Inject year into /teams/fbs rows so season does not depend on the landing path.

    Needed for Season Preview drops in July: landing_season() from dt=2026-07-30 would
    otherwise resolve to 2025.
    """
    tagged = []
    for row in records:
        copy = dict(row)
        copy["year"] = year
        tagged.append(copy)
    return tagged


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
            try:
                records = client.fetch_domain(domain, year=year)
                if domain == "teams_fbs":
                    records = _tag_teams_fbs_year(records, year)
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
    """Dated drop under incremental/. Pass domains from plan_domains()."""
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
                if domain == "teams_fbs":
                    records = _tag_teams_fbs_year(records, year)
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


def download_preview_to_volume(
    client: CFBDClient,
    config: SaturdayHQConfig,
    upcoming_season: Optional[int] = None,
    domains: Optional[Sequence[str]] = None,
) -> List[dict]:
    """Season Preview pull: upcoming season + prior-season production domains.

    Writes under incremental/dt=YYYY-MM-DD/ like other refreshes. Prior-only domains
    (usage, stats, PPA, returning, prior rosters) are fetched for upcoming-1; portal,
    recruiting, teams_fbs, and rosters are fetched for both years so constructed 2026
    rosters can fall back when CFBD has not published the upcoming roster yet.
    Draft picks are upcoming-year only (draft year N exits the college season-N roster).
    """
    upcoming = upcoming_season or preview_season()
    prior = upcoming - 1
    domain_list = list(domains) if domains is not None else list(PREVIEW_DOMAINS)
    pulled_at = datetime.now(timezone.utc)
    date_str = pulled_at.strftime("%Y-%m-%d")
    ts = pulled_at.isoformat()
    root = f"{config.incremental_path}/dt={date_str}"
    _ensure_dir(root)
    manifest: List[dict] = []

    # Teams first so roster fan-out can reuse the same season membership if needed.
    ordered = [d for d in domain_list if d == "teams_fbs"] + [
        d for d in domain_list if d != "teams_fbs"
    ]

    for year in (prior, upcoming):
        for domain in ordered:
            if year == prior and domain in PREVIEW_UPCOMING_ONLY_DOMAINS:
                continue
            # Skip prior-only domains for the upcoming year when CFBD typically has nothing
            # yet — still attempt portal/recruiting/teams/rosters for the upcoming year.
            if year == upcoming and domain in PREVIEW_PRIOR_DOMAINS and domain not in (
                "rosters",
                "player_returning",
            ):
                # usage / stats / ppa are prior-season facts; skip empty upcoming pulls.
                if domain in ("player_usage", "player_season_stats", "ppa_players_season"):
                    continue
            try:
                records = client.fetch_domain(domain, year=year)
                if domain == "teams_fbs":
                    records = _tag_teams_fbs_year(records, year)
            except Exception as exc:  # noqa: BLE001
                manifest.append(
                    {
                        "domain": domain,
                        "year": year,
                        "path": None,
                        "rows": 0,
                        "pulled_at": ts,
                        "mode": "preview",
                        "error": str(exc),
                    }
                )
                continue

            # Incremental layout is one file per domain per drop. When pulling two years in
            # one preview run, write year-partitioned filenames so both survive.
            out = f"{root}/{domain}/{domain}_year={year}.jsonl"
            n = write_jsonl(out, records)
            manifest.append(
                {
                    "domain": domain,
                    "year": year,
                    "path": out,
                    "rows": n,
                    "pulled_at": ts,
                    "mode": "preview",
                }
            )

    manifest_path = f"{root}/_manifest_preview.json"
    Path(manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
