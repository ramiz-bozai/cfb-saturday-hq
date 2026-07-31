"""Ingest nflverse undrafted free agents into the shared landing volume.

UDFA rookie_year N exits the college season-N constructed roster (same semantics as
CFBD draft_year N). Filtered as: rookie_season == year and draft_number is null.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from saturday_hq.config import SaturdayHQConfig, preview_season
from saturday_hq.ingest.download_historical import _ensure_dir, write_jsonl


def fetch_udfa_records(rookie_year: int) -> List[Dict[str, Any]]:
    """Pull unique UDFAs for a rookie/draft year from nflverse via nflreadpy."""
    import nflreadpy as nfl
    import polars as pl

    players = nfl.load_players()
    rosters = nfl.load_rosters(rookie_year)
    udfas = (
        rosters.join(players, on="gsis_id", how="left")
        .filter(
            (pl.col("rookie_season") == rookie_year)
            & pl.col("draft_number").is_null()
        )
        .unique(subset=["gsis_id"])
    )

    records: List[Dict[str, Any]] = []
    for row in udfas.iter_rows(named=True):
        first = row.get("first_name") or row.get("first_name_right")
        last = row.get("last_name") or row.get("last_name_right")
        records.append(
            {
                "rookie_year": rookie_year,
                "gsis_id": row.get("gsis_id"),
                "first_name": first,
                "last_name": last,
                "display_name": row.get("display_name") or row.get("full_name"),
                "football_name": row.get("football_name") or row.get("football_name_right"),
                "college": row.get("college"),
                "college_name": row.get("college_name") or row.get("college"),
                "nfl_team": row.get("team"),
                "position": row.get("position"),
                "draft_number": row.get("draft_number"),
                "rookie_season": row.get("rookie_season"),
            }
        )
    return records


def download_udfa_to_volume(
    config: SaturdayHQConfig,
    rookie_year: Optional[int] = None,
) -> Dict[str, Any]:
    """Write UDFA JSONL under manual/nfl_udfa/year=YYYY/ on the shared landing volume."""
    year = rookie_year or preview_season()
    records = fetch_udfa_records(year)
    root = f"{config.manual_path}/nfl_udfa/year={year}"
    _ensure_dir(root)
    out = f"{root}/nfl_udfa.jsonl"
    n = write_jsonl(out, records)
    manifest = {
        "domain": "nfl_udfa",
        "rookie_year": year,
        "path": out,
        "rows": n,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(f"{root}/_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
