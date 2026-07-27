"""Saturday HQ shared configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


POWER4_CANONICAL = {"ACC", "Big Ten", "Big 12", "SEC"}

G6_CANONICAL = {"American", "CUSA", "MAC", "Mountain West", "Pac-12", "Sun Belt"}

CONFERENCE_ALIASES = {
    "B1G": "Big Ten",
    "Big Ten": "Big Ten",
    "SEC": "SEC",
    "ACC": "ACC",
    "Big 12": "Big 12",
    "American Athletic": "American",
    "AAC": "American",
    "American": "American",
    "Conference USA": "CUSA",
    "CUSA": "CUSA",
    "Mid-American": "MAC",
    "MAC": "MAC",
    "Mountain West": "Mountain West",
    "MWC": "Mountain West",
    "Pac-12": "Pac-12",
    "Sun Belt": "Sun Belt",
    "FBS Independents": "FBS Independents",
    "Ind": "FBS Independents",
}

HISTORICAL_DOMAINS = (
    "teams_fbs",
    "conferences",
    "games",
    "team_season_stats",
    "sp_plus",
    "ppa_teams",
    "ppa_games",
    "talent",
    "recruiting_teams",
    "rankings",
    "lines",
)

DISCLAIMER_MARKET = (
    "For analysis and entertainment only. Not gambling advice. "
    "Lines are public market context shown next to the model."
)

DISCLAIMER_CFP = (
    "Playoff projections use Saturday HQ ratings plus published CFP structure. "
    "Not an official College Football Playoff selection."
)

# CFBD labels a season by its starting calendar year: season 2026 runs Aug 2026 -> Jan 2027.
SEASON_START_MONTH = 8


def current_cfb_season(today: Optional[date] = None) -> int:
    """Season CFBD is currently publishing: the in-progress one, else the last completed one."""
    today = today or date.today()
    return today.year if today.month >= SEASON_START_MONTH else today.year - 1


@dataclass(frozen=True)
class SaturdayHQConfig:
    catalog: str = "cfb_saturday_hq"
    schema_bronze: str = "cfb_bronze"
    schema_silver: str = "cfb_silver"
    schema_gold: str = "cfb_gold"
    schema_ml: str = "cfb_ml"
    schema_app: str = "cfb_app"
    volume_name: str = "cfbd_landing"
    secret_scope: str = "cfb_saturday_hq"
    secret_key: str = "cfbd_api_key"
    history_start_year: int = 2015
    current_season: int = field(default_factory=current_cfb_season)
    classification: str = "fbs"
    cfbd_base_url: str = "https://api.collegefootballdata.com"
    request_pause_seconds: float = 0.25

    @property
    def volume_path(self) -> str:
        return f"/Volumes/{self.catalog}/{self.schema_bronze}/{self.volume_name}"

    @property
    def historical_path(self) -> str:
        return f"{self.volume_path}/historical"

    @property
    def incremental_path(self) -> str:
        return f"{self.volume_path}/incremental"

    @property
    def manual_path(self) -> str:
        return f"{self.volume_path}/manual"

    def table(self, schema: str, name: str) -> str:
        return f"{self.catalog}.{schema}.{name}"

    def bronze(self, name: str) -> str:
        return self.table(self.schema_bronze, name)

    def silver(self, name: str) -> str:
        return self.table(self.schema_silver, name)

    def gold(self, name: str) -> str:
        return self.table(self.schema_gold, name)

    def ml(self, name: str) -> str:
        return self.table(self.schema_ml, name)

    def app(self, name: str) -> str:
        return self.table(self.schema_app, name)

