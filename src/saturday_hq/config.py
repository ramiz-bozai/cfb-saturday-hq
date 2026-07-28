"""Saturday HQ shared configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# CFBD labels a season by its starting year, so the rollover happens in August:
# runs before August target the last completed season, runs from August on target the new one.
SEASON_START_MONTH = 8


def current_cfb_season(today: Optional[date] = None) -> int:
    """Season CFBD is currently publishing: the in-progress one, else the last completed one."""
    today = today or date.today()
    return today.year if today.month >= SEASON_START_MONTH else today.year - 1


# Bronze/silver/gold are built once per environment, each in its own catalog. The raw CFBD
# files are NOT: they land in one shared volume that neither environment owns, so the API is
# only ever called once and dev reads exactly what prod reads.
CATALOG_PREFIX = "cfb_saturday_hq"
ENVIRONMENTS = ("dev", "prod")
DEFAULT_ENV = "dev"
ENV_VAR = "SATURDAY_HQ_ENV"

RAW_CATALOG = f"{CATALOG_PREFIX}_raw"
RAW_SCHEMA = "landing"


def catalog_for_env(env: str) -> str:
    if env not in ENVIRONMENTS:
        raise ValueError(f"env must be one of {ENVIRONMENTS}, got {env!r}")
    return f"{CATALOG_PREFIX}_{env}"


def current_env(override: Optional[str] = None) -> str:
    """Environment for this run: an explicit override, else SATURDAY_HQ_ENV, else dev.

    Jobs set SATURDAY_HQ_ENV on their cluster from the bundle target, so scheduled runs write
    to prod while an interactive notebook run stays in dev without anyone editing a constant.
    """
    env = (override or os.environ.get(ENV_VAR) or DEFAULT_ENV).strip().lower()
    if env not in ENVIRONMENTS:
        raise ValueError(f"{ENV_VAR} must be one of {ENVIRONMENTS}, got {env!r}")
    return env


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


@dataclass(frozen=True)
class SaturdayHQConfig:
    env: str = ""  # blank => SATURDAY_HQ_ENV, else dev
    catalog: str = ""  # blank => cfb_saturday_hq_<env>
    schema_bronze: str = "cfb_bronze"
    schema_silver: str = "cfb_silver"
    schema_gold: str = "cfb_gold"
    schema_ml: str = "cfb_ml"
    schema_app: str = "cfb_app"
    raw_catalog: str = RAW_CATALOG
    raw_schema: str = RAW_SCHEMA
    volume_name: str = "cfbd_landing"
    secret_scope: str = "cfb_saturday_hq"
    secret_key: str = "cfbd_api_key"
    history_start_year: int = 2015
    current_season: int = field(default_factory=current_cfb_season)
    classification: str = "fbs"
    cfbd_base_url: str = "https://api.collegefootballdata.com"
    request_pause_seconds: float = 0.25

    def __post_init__(self) -> None:
        env = current_env(self.env)
        object.__setattr__(self, "env", env)
        if not self.catalog:
            object.__setattr__(self, "catalog", catalog_for_env(env))

    @property
    def volume_path(self) -> str:
        """Shared landing volume, outside both environment catalogs."""
        return f"/Volumes/{self.raw_catalog}/{self.raw_schema}/{self.volume_name}"

    @property
    def model_name(self) -> str:
        """Unity Catalog registered model, so the model follows the environment."""
        return self.ml("matchup")

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

