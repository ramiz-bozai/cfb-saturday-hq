"""Saturday HQ — demo-able Streamlit Databricks App.

Deploy as a Databricks App with a SQL warehouse / UC access to gold + app schemas.
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

# Mirrors current_cfb_season() in src/saturday_hq/config.py; the app ships without the package.
SEASON_START_MONTH = 8


def default_season(today: date | None = None) -> int:
    """In-season / completed-season default for Slate and related tabs."""
    today = today or date.today()
    return today.year if today.month >= SEASON_START_MONTH else today.year - 1


def preview_season(today: date | None = None) -> int:
    """Upcoming season for Offseason Preview (July 2026 -> 2026)."""
    today = today or date.today()
    return today.year if today.month < SEASON_START_MONTH else default_season(today)

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


def _number(value) -> Optional[float]:
    return None if value is None or pd.isna(value) else float(value)


def _flag(value) -> bool:
    return False if value is None or pd.isna(value) else bool(value)


def _percent(value: Optional[float]) -> str:
    return "Not available" if value is None else f"{value:.0%}"


def _difference(left, right) -> Optional[float]:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is None or right_number is None:
        return None
    return left_number - right_number


def _record(row: pd.Series, side: str) -> str:
    games = _number(row.get(f"{side}_games_played"))
    win_pct = _number(row.get(f"{side}_win_pct"))
    if games is None or win_pct is None:
        return "0-0" if int(row.get("week", 0)) <= 1 else "Record unavailable"
    wins = round(games * win_pct)
    return f"{wins}-{round(games) - wins}"


def _kickoff_label(value) -> str:
    kickoff = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(kickoff):
        return "Kickoff time unavailable"
    return kickoff.strftime("%a, %b %d · %I:%M %p UTC").replace(" 0", " ")


def _spread_label(row: pd.Series) -> str:
    spread = _number(row.get("market_spread"))
    if spread is None:
        return "Not posted"
    if spread == 0:
        return "Pick'em"
    return f"-{abs(spread):g}"


def _interest_score(row: pd.Series) -> float:
    model_probability = _number(row.get("model_home_win_prob"))
    disagreement = abs(_number(row.get("model_minus_market")) or 0.0)
    toss_up = 0.0 if model_probability is None else 1.0 - 2.0 * abs(model_probability - 0.5)
    return toss_up + 1.5 * disagreement


def _matchup_insights(row: pd.Series) -> List[str]:
    home = str(row["home_team"])
    away = str(row["away_team"])
    insights: List[str] = []
    available_comparisons = 0

    comparisons = [
        (
            _number(row.get("sp_overall_diff_prior")),
            3.0,
            "the stronger prior-season SP+ profile",
        ),
        (
            _number(row.get("talent_diff")),
            40.0,
            "the roster-talent advantage",
        ),
        (
            _difference(row.get("home_win_pct_fbs"), row.get("away_win_pct_fbs")),
            0.15,
            "the better record against FBS opponents",
        ),
        (
            _difference(
                row.get("home_avg_margin_l3_fbs"), row.get("away_avg_margin_l3_fbs")
            ),
            7.0,
            "the stronger recent FBS form",
        ),
    ]
    for difference, threshold, description in comparisons:
        if difference is None:
            continue
        available_comparisons += 1
        if abs(difference) < threshold:
            continue
        team = home if difference > 0 else away
        insights.append(f"{team} has {description}.")
        if len(insights) == 2:
            break

    if available_comparisons == 0:
        insights.append("Pregame team-strength context is not available for this matchup.")
    elif not insights:
        insights.append("The available team-strength indicators are closely matched.")
    return insights


def _game_tags(row: pd.Series, my_teams: List[str]) -> List[str]:
    tags = []
    home = str(row["home_team"])
    away = str(row["away_team"])
    model_probability = _number(row.get("model_home_win_prob"))
    market_probability = _number(row.get("market_home_win_prob"))
    disagreement = _number(row.get("model_minus_market"))

    if home in my_teams or away in my_teams:
        tags.append("⭐ My Team")
    if (
        _number(row.get("sp_overall_diff_prior")) is None
        and _number(row.get("talent_diff")) is None
    ):
        tags.append("Limited model context")
    if model_probability is not None and abs(model_probability - 0.5) <= 0.08:
        tags.append("Toss-up")
    if (
        model_probability is not None
        and market_probability is not None
        and (model_probability >= 0.5) != (market_probability >= 0.5)
    ):
        tags.append("Upset watch")
    elif disagreement is not None and abs(disagreement) >= 0.08:
        tags.append("Big model-market disagreement")
    return tags


def render_game_card(row: pd.Series, my_teams: List[str]) -> None:
    home = str(row["home_team"])
    away = str(row["away_team"])
    home_probability = _number(row.get("model_home_win_prob"))
    market_home_probability = _number(row.get("market_home_win_prob"))
    disagreement = _number(row.get("model_minus_market"))
    tags = _game_tags(row, my_teams)
    completed = _flag(row.get("completed"))
    model_favorite = (
        home
        if home_probability is not None and home_probability >= 0.5
        else away
        if home_probability is not None
        else None
    )
    market_favorite = (
        home
        if market_home_probability is not None and market_home_probability >= 0.5
        else away
        if market_home_probability is not None
        else None
    )

    with st.container(border=True):
        st.caption(" · ".join(tags) if tags else "Weekly matchup")
        st.markdown(f"### {away} at {home}")
        st.caption(
            f"{away} {_record(row, 'away')}  ·  {home} {_record(row, 'home')}  ·  "
            f"{'Final' if completed else _kickoff_label(row.get('start_date'))}"
        )

        if completed:
            st.markdown(
                f"**Final: {away} {int(row['away_points'])}, "
                f"{home} {int(row['home_points'])}**"
            )
        elif home_probability is not None:
            favorite = home if home_probability >= 0.5 else away
            favorite_probability = max(home_probability, 1.0 - home_probability)
            st.markdown(f"**Saturday HQ pick: {favorite} ({favorite_probability:.0%})**")
        else:
            st.markdown("**Saturday HQ prediction not available yet**")

        model_column, market_column, spread_column = st.columns(3)
        model_column.metric(
            f"Model · {model_favorite}" if model_favorite else "Model",
            _percent(
                max(home_probability, 1.0 - home_probability)
                if home_probability is not None
                else None
            ),
            help="Win probability for the model's favored team.",
        )
        market_column.metric(
            f"Market · {market_favorite}" if market_favorite else "Market",
            _percent(
                max(market_home_probability, 1.0 - market_home_probability)
                if market_home_probability is not None
                else None
            ),
            help="De-vigged moneyline probability for the market favorite.",
        )
        spread_column.metric(
            f"Spread · {market_favorite}" if market_favorite else "Spread",
            _spread_label(row),
            help="The posted spread for the market favorite.",
        )

        if disagreement is not None and market_home_probability is not None:
            side = home if disagreement > 0 else away
            if abs(disagreement) < 0.03:
                st.caption("Saturday HQ and the market broadly agree.")
            else:
                st.caption(
                    f"Saturday HQ is {abs(disagreement):.0%} more optimistic about {side} "
                    "than the market."
                )

        for insight in _matchup_insights(row):
            st.write(f"• {insight}")


def render_game_grid(games: pd.DataFrame, my_teams: List[str]) -> None:
    for start in range(0, len(games), 2):
        columns = st.columns(2)
        for position, (_, game) in enumerate(games.iloc[start : start + 2].iterrows()):
            with columns[position]:
                render_game_card(game, my_teams)


def _fmt_pct(value) -> str:
    number = _number(value)
    return "—" if number is None else f"{number:.0%}"


def _fmt_num(value, digits: int = 1) -> str:
    number = _number(value)
    return "—" if number is None else f"{number:.{digits}f}"


def render_preview_tab(catalog: str, gold_schema: str, my_teams: List[str]) -> None:
    st.subheader("Offseason Preview")
    st.caption(
        "Roster continuity, portal impact, and QB rooms for the upcoming season. "
        "Transfers are weighted by prior usage and production, not stars alone. "
        "When CFBD has not published the upcoming roster yet, Saturday HQ constructs it "
        "from the prior roster plus portal moves."
    )

    preview = st.sidebar.number_input(
        "Preview season",
        min_value=2015,
        max_value=2030,
        value=preview_season(),
        key="preview_season",
    )
    view = st.radio("View", options=("Overview", "Team"), horizontal=True, key="preview_view")

    teams = load_table(
        f"""
        SELECT DISTINCT team
        FROM {catalog}.{gold_schema}.roster_snapshot
        WHERE season = {int(preview)}
        ORDER BY team
        """
    )
    if teams.empty:
        st.info(
            f"No Preview tables for {int(preview)} yet. "
            "Run notebook 06 (preview ingest) and `dbt build` for the player models."
        )
        return

    team_list = teams["team"].tolist()
    default_team = next((t for t in my_teams if t in team_list), team_list[0])

    if view == "Overview":
        returning = load_table(
            f"""
            SELECT team, conference,
                   round(percent_ppa, 3) AS pct_ppa_returning,
                   round(percent_offense_returning, 3) AS pct_offense_returning,
                   round(percent_defense_returning, 3) AS pct_defense_returning,
                   round(percent_usage, 3) AS pct_usage_returning,
                   round(percent_production, 3) AS pct_production_returning,
                   round(percent_sacks, 3) AS pct_sacks_returning,
                   source
            FROM {catalog}.{gold_schema}.returning_production_team
            WHERE season = {int(preview)}
            ORDER BY coalesce(percent_ppa, percent_production) ASC NULLS LAST
            LIMIT 40
            """
        )
        dependency = load_table(
            f"""
            SELECT team,
                   round(transfer_dependency_score, 1) AS dependency_score,
                   round(pct_usage_from_transfers, 3) AS pct_usage_from_transfers,
                   critical_units_on_transfers,
                   impact_additions,
                   impact_losses
            FROM {catalog}.{gold_schema}.transfer_dependency
            WHERE season = {int(preview)}
            ORDER BY transfer_dependency_score DESC
            LIMIT 25
            """
        )
        portal = load_table(
            f"""
            SELECT team,
                   impact_additions, depth_additions,
                   impact_losses, depth_losses,
                   round(net_production_gained, 1) AS net_production_gained,
                   round(net_talent_gained, 2) AS net_talent_gained,
                   projected_starters_added, projected_starters_lost,
                   round(avg_continuity_score, 1) AS avg_continuity
            FROM {catalog}.{gold_schema}.portal_team_ledger
            WHERE season = {int(preview)}
            ORDER BY net_production_gained DESC
            LIMIT 25
            """
        )
        risk = load_table(
            f"""
            SELECT team, position_group, replacement_risk, metric_name,
                   round(departed_share, 3) AS departed_share,
                   round(best_returner_metric, 1) AS best_returner_metric,
                   round(continuity_score, 1) AS continuity_score, callout
            FROM {catalog}.{gold_schema}.replacement_risk
            WHERE season = {int(preview)}
            ORDER BY coalesce(departed_share, 0) DESC, continuity_score ASC
            LIMIT 30
            """
        )
        qb_rooms = load_table(
            f"""
            SELECT team, room_class, count(*) AS qbs
            FROM {catalog}.{gold_schema}.qb_room
            WHERE season = {int(preview)}
            GROUP BY team, room_class
            ORDER BY
              case room_class
                when 'Major uncertainty' then 1
                when 'Unproven competition' then 2
                when 'High-upside transfer' then 3
                when 'Experienced but limited' then 4
                when 'Proven average starter' then 5
                when 'Proven elite starter' then 6
                else 7
              end,
              team
            """
        )

        st.markdown("#### Lowest returning production")
        st.dataframe(returning, width="stretch")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Highest transfer dependency")
            st.dataframe(dependency, width="stretch")
        with col_b:
            st.markdown("#### Portal winners (net production)")
            st.dataframe(portal, width="stretch")
        st.markdown("#### Replacement risk callouts")
        st.dataframe(risk, width="stretch")
        st.markdown("#### QB rooms by class")
        st.dataframe(qb_rooms, width="stretch")
        return

    team = st.selectbox(
        "Team",
        options=team_list,
        index=team_list.index(default_team),
        key="preview_team",
    )
    safe_team = team.replace("'", "''")

    ret = load_table(
        f"""
        SELECT *
        FROM {catalog}.{gold_schema}.returning_production_team
        WHERE season = {int(preview)} AND team = '{safe_team}'
        """
    )
    units = load_table(
        f"""
        SELECT position_group,
               round(continuity_score, 1) AS continuity_score,
               round(production_returning_pct, 3) AS production_returning,
               round(usage_returning_pct, 3) AS usage_returning,
               impact_additions, impact_losses,
               depth_additions, depth_losses,
               round(net_production_gained, 1) AS net_production,
               round(talent_returning, 2) AS talent_returning,
               round(talent_added, 2) AS talent_added,
               round(talent_lost, 2) AS talent_lost,
               round(net_talent_gained, 2) AS net_talent,
               projected_starters_added, projected_starters_lost,
               replacement_risk
        FROM {catalog}.{gold_schema}.unit_continuity
        WHERE season = {int(preview)} AND team = '{safe_team}'
        ORDER BY continuity_score ASC
        """
    )
    ledger = load_table(
        f"""
        SELECT *
        FROM {catalog}.{gold_schema}.portal_team_ledger
        WHERE season = {int(preview)} AND team = '{safe_team}'
        """
    )
    dep = load_table(
        f"""
        SELECT *
        FROM {catalog}.{gold_schema}.transfer_dependency
        WHERE season = {int(preview)} AND team = '{safe_team}'
        """
    )
    risks = load_table(
        f"""
        SELECT position_group, replacement_risk, metric_name,
               round(departed_share, 3) AS departed_share,
               round(best_returner_metric, 1) AS best_returner_metric,
               callout
        FROM {catalog}.{gold_schema}.replacement_risk
        WHERE season = {int(preview)} AND team = '{safe_team}'
        ORDER BY coalesce(departed_share, 0) DESC, continuity_score ASC
        """
    )
    moves = load_table(
        f"""
        SELECT first_name, last_name, position_group, origin, destination,
               impact_class, projected_starter,
               round(prior_usage_overall, 3) AS prior_usage,
               round(prior_production_score, 1) AS prior_production,
               transfer_stars
        FROM {catalog}.{gold_schema}.portal_moves
        WHERE season = {int(preview)}
          AND (origin = '{safe_team}' OR destination = '{safe_team}')
        ORDER BY prior_production_score DESC NULLS LAST
        """
    )
    qbs = load_table(
        f"""
        SELECT first_name, last_name, qb_class, room_class,
               is_returning_starter, is_backup, is_transfer_addition,
               prior_pass_att, career_pass_att,
               round(career_avg_ppa_weighted, 3) AS career_avg_ppa,
               round(avg_ppa_all, 3) AS avg_ppa,
               round(turnover_rate, 3) AS turnover_rate,
               career_rush_yds, transfer_count, last_transfer_origin,
               stars, round(recruiting_rating, 4) AS recruiting_rating
        FROM {catalog}.{gold_schema}.qb_room
        WHERE season = {int(preview)} AND team = '{safe_team}'
        ORDER BY qb_rank ASC
        """
    )

    st.markdown(f"### {team}")
    if not ret.empty:
        row = ret.iloc[0]
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Offense returning", _fmt_pct(row.get("percent_offense_returning")))
        m2.metric("Defense returning", _fmt_pct(row.get("percent_defense_returning")))
        m3.metric("PPA returning", _fmt_pct(row.get("percent_ppa")))
        m4.metric("Sacks returning", _fmt_pct(row.get("percent_sacks")))
        m5.metric("Source", str(row.get("source") or "—"))

    if not dep.empty:
        d = dep.iloc[0]
        st.markdown(
            f"**Transfer dependency:** {_fmt_num(d.get('transfer_dependency_score'), 0)} / 100 "
            f"· {_fmt_pct(d.get('pct_usage_from_transfers'))} of roster prior usage from transfers "
            f"· {int(d.get('critical_units_on_transfers') or 0)} critical units on new arrivals"
        )

    if not ledger.empty:
        led = ledger.iloc[0]
        st.caption(
            f"Portal ledger — impact +{int(led.get('impact_additions') or 0)} / "
            f"-{int(led.get('impact_losses') or 0)}, "
            f"depth +{int(led.get('depth_additions') or 0)} / "
            f"-{int(led.get('depth_losses') or 0)}, "
            f"net production {_fmt_num(led.get('net_production_gained'), 1)}, "
            f"net talent {_fmt_num(led.get('net_talent_gained'), 2)}, "
            f"projected starters +{int(led.get('projected_starters_added') or 0)} / "
            f"-{int(led.get('projected_starters_lost') or 0)}"
        )

    st.markdown("#### Unit continuity")
    st.dataframe(units, width="stretch")

    if not risks.empty:
        st.markdown("#### Replacement risk")
        for _, risk_row in risks.iterrows():
            st.write(f"• {risk_row['callout']}")

    st.markdown("#### Portal moves")
    st.dataframe(moves, width="stretch")

    st.markdown("#### QB room")
    if qbs.empty:
        st.write("No quarterbacks on the constructed roster.")
    else:
        st.caption(f"Room class: **{qbs.iloc[0]['room_class']}**")
        st.dataframe(qbs, width="stretch")


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

    tab_home, tab_slate, tab_matchup, tab_proj, tab_brief, tab_preview = st.tabs(
        ["Home", "Slate", "Matchup", "Projections", "Brief", "Preview"]
    )

    with tab_home:
        st.subheader("Welcome")
        st.write(
            "Use **Slate** for this week's model vs market view, **Matchup** for a deep dive, "
            "**Projections** for win totals / playoff odds, **Brief** for team writeups, and "
            "**Preview** for offseason roster / portal / QB continuity."
        )
        st.write(f"Active profile teams: {', '.join(my_teams)}")

    with tab_slate:
        st.subheader(f"{season_type.title()} Week {week} slate — model vs market")
        slate = load_table(
            f"""
            SELECT game_id, season_type, week, start_date, completed, neutral_site,
                   home_team, away_team, home_conference, away_conference,
                   home_points, away_points,
                   model_home_win_prob,
                   market_home_win_prob_novig AS market_home_win_prob,
                   model_minus_market_home AS model_minus_market,
                   market_spread,
                   home_games_played, away_games_played,
                   home_win_pct, away_win_pct,
                   home_win_pct_fbs, away_win_pct_fbs,
                   home_avg_margin_l3_fbs, away_avg_margin_l3_fbs,
                   sp_overall_diff_prior,
                   talent_diff
            FROM {CATALOG}.{GOLD_SCHEMA}.matchup_card
            WHERE season = {int(season)}
              AND lower(season_type) = '{season_type}'
              AND week = {int(week)}
            ORDER BY start_date, game_id
            """
        )
        if slate.empty:
            st.info("No games are available for this week yet.")
        else:
            slate["_interest_score"] = slate.apply(_interest_score, axis=1)
            my_team_mask = slate["home_team"].isin(my_teams) | slate["away_team"].isin(my_teams)
            my_team_games = slate[my_team_mask].sort_values("_interest_score", ascending=False)
            other_games = slate[~my_team_mask].sort_values("_interest_score", ascending=False)

            st.caption(
                "Cards prioritize close games and meaningful model-market disagreements. "
                "Market percentages are de-vigged."
            )
            if not my_team_games.empty:
                st.markdown("#### My Teams")
                render_game_grid(my_team_games, my_teams)
            if not other_games.empty:
                st.markdown("#### Games to Watch")
                render_game_grid(other_games, my_teams)

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
            st.dataframe(card.T.astype(str), width="stretch")

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
        st.dataframe(proj, width="stretch")

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

    with tab_preview:
        render_preview_tab(CATALOG, GOLD_SCHEMA, my_teams)


if __name__ == "__main__":
    main()
