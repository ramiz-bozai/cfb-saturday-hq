"""CFBD REST client used for historical Volume downloads and the weekly API refresh."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from saturday_hq.config import SaturdayHQConfig


class CFBDClient:
    def __init__(self, api_key: str, config: Optional[SaturdayHQConfig] = None):
        if not api_key:
            raise ValueError("CFBD API key is required")
        self.config = config or SaturdayHQConfig()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(5))
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.config.cfbd_base_url}{path}"
        resp = self.session.get(url, params=params or {}, timeout=60)
        if resp.status_code == 429:
            raise requests.HTTPError("Rate limited", response=resp)
        resp.raise_for_status()
        time.sleep(self.config.request_pause_seconds)
        return resp.json()

    def get_conferences(self) -> List[Dict[str, Any]]:
        return self._get("/conferences")

    def get_fbs_teams(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {}
        if year is not None:
            params["year"] = year
        return self._get("/teams/fbs", params)

    def get_games(
        self,
        year: int,
        week: Optional[int] = None,
        season_type: str = "regular",
        division: str = "fbs",
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "year": year,
            "seasonType": season_type,
            "division": division,
        }
        if week is not None:
            params["week"] = week
        return self._get("/games", params)

    def get_team_season_stats(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/stats/season", {"year": year})

    def get_sp_plus(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/ratings/sp", {"year": year})

    def get_ppa_teams(self, year: int, exclude_garbage_time: bool = True) -> List[Dict[str, Any]]:
        return self._get(
            "/ppa/teams",
            {"year": year, "excludeGarbageTime": str(exclude_garbage_time).lower()},
        )

    def get_ppa_games(self, year: int, week: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"year": year}
        if week is not None:
            params["week"] = week
        return self._get("/ppa/games", params)

    def get_talent(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/talent", {"year": year})

    def get_recruiting_teams(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/recruiting/teams", {"year": year})

    def get_rankings(self, year: int, week: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"year": year}
        if week is not None:
            params["week"] = week
        return self._get("/rankings", params)

    def get_lines(
        self,
        year: int,
        week: Optional[int] = None,
        season_type: str = "regular",
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        return self._get("/lines", params)

    def fetch_domain(
        self,
        domain: str,
        year: int,
        week: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if domain == "teams_fbs":
            return self.get_fbs_teams(year)
        if domain == "conferences":
            return self.get_conferences()
        if domain == "games":
            # Regular + postseason for completed seasons; schedule year may be regular only.
            regular = self.get_games(year, week=week, season_type="regular")
            post = self.get_games(year, week=week, season_type="postseason")
            return regular + post
        if domain == "team_season_stats":
            return self.get_team_season_stats(year)
        if domain == "sp_plus":
            return self.get_sp_plus(year)
        if domain == "ppa_teams":
            return self.get_ppa_teams(year)
        if domain == "ppa_games":
            return self.get_ppa_games(year, week=week)
        if domain == "talent":
            return self.get_talent(year)
        if domain == "recruiting_teams":
            return self.get_recruiting_teams(year)
        if domain == "rankings":
            return self.get_rankings(year, week=week)
        if domain == "lines":
            regular = self.get_lines(year, week=week, season_type="regular")
            post = self.get_lines(year, week=week, season_type="postseason")
            return regular + post
        raise ValueError(f"Unknown domain: {domain}")


def dumps_jsonl(records: List[Dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, default=str) for r in records) + ("\n" if records else "")
