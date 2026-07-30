"""Saturday HQ — demo-able Streamlit Databricks App.

Deploy as a Databricks App with a SQL warehouse / UC access to gold + app schemas.
"""

from __future__ import annotations

import os
from datetime import date
from typing import List

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

# Mirrors current_cfb_season() in src/saturday_hq/config.py; the app ships without the package.
SEASON_START_MONTH = 8


def default_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= SEASON_START_MONTH else today.year - 1

DISCLAIMER_MARKET = (
    "For analysis and entertainment only. Not gambling advice. "
    "Lines are public market context shown next to the model."
)
DISCLAIMER_CFP = (
    "Playoff projections use Saturday HQ ratings plus published CFP structure. "
    "Not an official College Football Playoff selection."
)

# The App serves prod. Point SATURDAY_HQ_CATALOG at cfb_saturday_hq_dev to preview dev data.
CATALOG = os.getenv("SATURDAY_HQ_CATALOG", "cfb_saturday_hq_prod")
GOLD_SCHEMA = os.getenv("SATURDAY_HQ_GOLD_SCHEMA", "cfb_gold")
APP_SCHEMA = os.getenv("SATURDAY_HQ_APP_SCHEMA", "cfb_app")


def get_connection():
    config = Config()
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    if not http_path:
        if not warehouse_id:
            raise RuntimeError(
                "Set DATABRICKS_WAREHOUSE_ID through an App SQL warehouse resource."
            )
        http_path = f"/sql/1.0/warehouses/{warehouse_id}"
    server_hostname = config.host.removeprefix("https://").removeprefix("http://").rstrip("/")
    return sql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        credentials_provider=lambda: config.authenticate,
        _use_arrow_native_complex_types=True,
    )


@st.cache_data(ttl=300)
def load_table(query: str) -> pd.DataFrame:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


def main():
    st.set_page_config(page_title="Saturday HQ", page_icon="🏈", layout="wide")
    st.title("Saturday HQ")
    st.caption("FBS college football intelligence — SP+, PPA, model vs market")
    st.info(DISCLAIMER_MARKET)
    st.warning(DISCLAIMER_CFP)

    season = st.sidebar.number_input(
        "Season", min_value=2015, max_value=2030, value=default_season()
    )
    season_type = st.sidebar.selectbox(
        "Season type", options=("regular", "postseason"), format_func=str.title
    )
    week = st.sidebar.number_input("Week", min_value=0, max_value=16, value=1)

    profiles = load_table(f"SELECT * FROM {CATALOG}.{APP_SCHEMA}.demo_profiles ORDER BY display_name")
    profile_name = st.sidebar.selectbox(
        "Demo profile",
        options=profiles["display_name"].tolist() if not profiles.empty else ["(none)"],
    )
    my_teams: List[str] = []
    if not profiles.empty:
        row = profiles[profiles["display_name"] == profile_name].iloc[0]
        my_teams = list(row["teams"]) if row["teams"] is not None else []

    st.sidebar.write("My Teams:", ", ".join(my_teams) if my_teams else "—")

    tab_home, tab_slate, tab_matchup, tab_proj, tab_brief = st.tabs(
        ["Home", "Slate", "Matchup", "Projections", "Brief"]
    )

    with tab_home:
        st.subheader("Welcome")
        st.write(
            "Use **Slate** for this week's model vs market view, **Matchup** for a deep dive, "
            "**Projections** for win totals / playoff odds, and **Brief** for team writeups."
        )
        st.write(f"Active profile teams: {', '.join(my_teams)}")

    with tab_slate:
        st.subheader(f"{season_type.title()} Week {week} slate — model vs market")
        slate = load_table(
            f"""
            SELECT season_type, week, home_team, away_team,
                   round(model_home_win_prob, 3) AS model_home_win_prob,
                   round(market_home_win_prob_novig, 3) AS market_home_win_prob,
                   round(model_minus_market_home, 3) AS model_minus_market,
                   market_spread,
                   round(home_sp_overall, 1) AS home_sp,
                   round(away_sp_overall, 1) AS away_sp
            FROM {CATALOG}.{GOLD_SCHEMA}.matchup_card
            WHERE season = {int(season)}
              AND lower(season_type) = '{season_type}'
              AND week = {int(week)}
            ORDER BY abs(coalesce(model_minus_market_home, 0)) DESC
            """
        )
        if my_teams:
            mask = slate["home_team"].isin(my_teams) | slate["away_team"].isin(my_teams)
            st.write("My Teams games")
            st.dataframe(slate[mask], use_container_width=True)
        st.write("Full slate")
        st.dataframe(slate, use_container_width=True)

    with tab_matchup:
        st.subheader("Matchup card")
        slate_all = load_table(
            f"""
            SELECT home_team, away_team
            FROM {CATALOG}.{GOLD_SCHEMA}.matchup_card
            WHERE season = {int(season)}
              AND lower(season_type) = '{season_type}'
              AND week = {int(week)}
            ORDER BY home_team
            """
        )
        if slate_all.empty:
            st.write("No games for this week yet.")
        else:
            labels = slate_all.apply(lambda r: f"{r['away_team']} @ {r['home_team']}", axis=1)
            choice = st.selectbox("Game", labels)
            home = slate_all.iloc[labels.tolist().index(choice)]["home_team"]
            away = slate_all.iloc[labels.tolist().index(choice)]["away_team"]
            card = load_table(
                f"""
                SELECT *
                FROM {CATALOG}.{GOLD_SCHEMA}.matchup_card
                WHERE season = {int(season)}
                  AND lower(season_type) = '{season_type}'
                  AND week = {int(week)}
                  AND home_team = '{home}' AND away_team = '{away}'
                """
            )
            st.dataframe(card.T, use_container_width=True)

    with tab_proj:
        st.subheader("Season / playoff projections")
        proj = load_table(
            f"""
            SELECT team, conference,
                   round(mean_wins, 2) AS mean_wins,
                   round(playoff_odds, 3) AS playoff_odds,
                   round(avg_seed_if_in, 2) AS avg_seed_if_in
            FROM {CATALOG}.{GOLD_SCHEMA}.playoff_projections
            WHERE season = {int(season)}
            ORDER BY playoff_odds DESC
            LIMIT 40
            """
        )
        st.dataframe(proj, use_container_width=True)

    with tab_brief:
        st.subheader("Weekly briefs")
        team = st.selectbox("Team", my_teams or ["Alabama"])
        briefs = load_table(
            f"""
            SELECT game_id, season, season_type, week, team, opponent, is_home, headline, summary,
                   round(model_win_prob, 3) AS model_win_prob,
                   round(market_win_prob, 3) AS market_win_prob,
                   market_spread
            FROM {CATALOG}.{GOLD_SCHEMA}.weekly_brief
            WHERE season = {int(season)}
              AND lower(season_type) = '{season_type}'
              AND week = {int(week)}
              AND team = '{team}'
            """
        )
        if briefs.empty:
            st.write("No brief for this team/week.")
        else:
            row = briefs.iloc[0]
            st.markdown(f"### {row['headline']}")
            st.write(row["summary"])
            st.write(briefs)


if __name__ == "__main__":
    main()
