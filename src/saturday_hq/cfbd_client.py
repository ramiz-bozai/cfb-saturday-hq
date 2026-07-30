"""CFBD REST client used for historical Volume downloads and the weekly API refresh."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Sequence

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from saturday_hq.config import SaturdayHQConfig


class CFBDClient:
    def __init__(
        self,
        api_key: str,
        config: Optional[SaturdayHQConfig] = None,
        verify_ssl: bool = True,
    ):
        if not api_key:
            raise ValueError("CFBD API key is required")
        self.config = config or SaturdayHQConfig()
        self.verify_ssl = verify_ssl
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
        resp = self.session.get(
            url, params=params or {}, timeout=120, verify=self.verify_ssl
        )
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

    def get_roster(self, year: int, team: str) -> List[Dict[str, Any]]:
        return self._get("/roster", {"year": year, "team": team})

    def get_rosters(self, year: int, teams: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        """One CFBD call per team — /roster requires team. Tag each row with season.

        If the first team returns an empty roster, assume the year is unpublished and
        skip the remaining ~130 calls (common for the upcoming season before camp).
        """
        if teams is None:
            teams = [row["school"] for row in self.get_fbs_teams(year)]
        team_list = list(teams)
        if not team_list:
            return []

        records: List[Dict[str, Any]] = []
        first_team = team_list[0]
        try:
            first_rows = self.get_roster(year, first_team)
        except Exception:  # noqa: BLE001
            first_rows = []
        if not first_rows:
            return []

        for row in first_rows:
            tagged = dict(row)
            tagged.setdefault("team", first_team)
            tagged["season"] = year
            records.append(tagged)

        for team in team_list[1:]:
            try:
                rows = self.get_roster(year, team)
            except Exception:  # noqa: BLE001 - keep backfill moving; empty roster is common
                rows = []
            for row in rows:
                tagged = dict(row)
                tagged.setdefault("team", team)
                tagged["season"] = year
                records.append(tagged)
        return records

    def get_player_portal(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/player/portal", {"year": year})

    def get_player_returning(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/player/returning", {"year": year})

    def get_player_usage(self, year: int, team: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"year": year}
        if team is not None:
            params["team"] = team
        return self._get("/player/usage", params)

    def get_player_season_stats(
        self,
        year: int,
        team: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"year": year}
        if team is not None:
            params["team"] = team
        if category is not None:
            params["category"] = category
        return self._get("/stats/player/season", params)

    def get_ppa_players_season(
        self,
        year: int,
        team: Optional[str] = None,
        exclude_garbage_time: bool = True,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "year": year,
            "excludeGarbageTime": str(exclude_garbage_time).lower(),
        }
        if team is not None:
            params["team"] = team
        return self._get("/ppa/players/season", params)

    def get_recruiting_players(self, year: int) -> List[Dict[str, Any]]:
        return self._get("/recruiting/players", {"year": year})

    def get_draft_picks(self, year: int) -> List[Dict[str, Any]]:
        """NFL draft picks for a draft year (collegeAthleteId links back to CFBD rosters)."""
        return self._get("/draft/picks", {"year": year})

    def fetch_domain(
        self,
        domain: str,
        year: int,
        week: Optional[int] = None,
        season_types: Sequence[str] = ("regular", "postseason"),
        teams: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch one domain. `games` and `lines` cost one call per season type requested.

        Backfills want both types; an in-season refresh before December should pass
        ("regular",) only, since the postseason endpoints have nothing to return yet.

        `rosters` costs one call per FBS team (~130).
        """
        if domain == "teams_fbs":
            return self.get_fbs_teams(year)
        if domain == "conferences":
            return self.get_conferences()
        if domain == "games":
            records: List[Dict[str, Any]] = []
            for season_type in season_types:
                records += self.get_games(year, week=week, season_type=season_type)
            return records
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
            records = []
            for season_type in season_types:
                records += self.get_lines(year, week=week, season_type=season_type)
            return records
        if domain == "rosters":
            return self.get_rosters(year, teams=teams)
        if domain == "player_portal":
            return self.get_player_portal(year)
        if domain == "player_returning":
            return self.get_player_returning(year)
        if domain == "player_usage":
            return self.get_player_usage(year)
        if domain == "player_season_stats":
            return self.get_player_season_stats(year)
        if domain == "ppa_players_season":
            return self.get_ppa_players_season(year)
        if domain == "recruiting_players":
            return self.get_recruiting_players(year)
        if domain == "draft_picks":
            return self.get_draft_picks(year)
        raise ValueError(f"Unknown domain: {domain}")


def dumps_jsonl(records: List[Dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, default=str) for r in records) + ("\n" if records else "")
