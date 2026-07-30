"""Column comments for the gold tables that Python writes.

dbt persists descriptions for its own models (persist_docs in dbt_project.yml), but these tables
come out of Spark, so Unity Catalog only carries a comment if it is applied here. Without it Genie
and Catalog Explorer see bare column names.

It matters most for `preseason_team_ratings`, where two columns are actively misleading if
undocumented: `rating` is in standard deviations rather than points, and `sp_overall` holds LAST
season's rating despite the unqualified name.

Long-form definitions for every column in the project live in docs/DATA_DICTIONARY.md.
"""

from __future__ import annotations

from typing import Mapping

_PRESEASON_TEAM_RATINGS = {
    "season": "Season these ratings project, named for the calendar year it kicks off in.",
    "conference": "Conference as of this season.",
    "is_notre_dame": "Drives the Notre Dame automatic-qualifier rule in the CFP logic.",
    "sp_overall": (
        "LAST season's SP+ in net points per game, not this season's — preseason ratings can only "
        "use what is known before kickoff. Higher is better."
    ),
    "ppa_offense": "Last season's offensive PPA per play. Higher is better.",
    "ppa_defense": "Last season's PPA allowed per play. LOWER IS BETTER.",
    "talent": (
        "This season's 247Sports composite roster talent, known before kickoff via signing day. "
        "A 0 for Air Force, Army or Navy is a real value meaning almost no composite-rated "
        "recruits, not a missing one."
    ),
    "rating": (
        "Weighted blend of standardised inputs, so the unit is STANDARD DEVIATIONS, not points: "
        "45% sp_overall, 20% sp_offense, 15% sp_defense inverted, 10% ppa_offense, 5% ppa_defense "
        "inverted, 5% talent. Do not read it as a scoring margin the way SP+ can be read."
    ),
    "preseason_rank": "Rank by rating, 1 = best. A model stand-in for a poll, not an actual poll.",
    "disclaimer": "Projection disclaimer carried alongside the numbers.",
}

# season_projections and playoff_projections share a schema; the latter is the same rows ordered
# by playoff odds.
_SEASON_PROJECTIONS = {
    "season": "Season being simulated.",
    "conference": "Conference as of this season.",
    "mean_wins": "Average regular-season wins across all simulations.",
    "median_wins": "Median simulated win total, less sensitive to blowout tails than the mean.",
    "win_total_p10": "10th percentile of simulated wins — a realistic floor.",
    "win_total_p90": "90th percentile of simulated wins — a realistic ceiling.",
    "playoff_odds": (
        "Share of simulations in which the team made the 12-team field, 0 to 1. A projection from "
        "published CFP automatic-qualifier structure, never an official forecast."
    ),
    "avg_seed_if_in": "Average seed in the simulations where the team qualified. Null if it never did.",
    "n_sims": "Number of Monte Carlo simulations behind these numbers.",
    "disclaimer": "Projection disclaimer carried alongside the numbers.",
}

_GAME_PREDICTIONS = {
    "model_home_win_prob": (
        "Probability the home team wins, from the logistic model. Trained on prior-season SP+/PPA, "
        "talent and FBS-only form; betting lines are deliberately excluded."
    ),
    "model_version": "Registered Unity Catalog model version that produced the probability.",
    "scored_at": "UTC timestamp of the scoring run.",
}

_WEEKLY_BRIEF = {
    "game_id": "CFBD game identifier. Together with team, this is the row's unique grain.",
    "season": "Year the season kicked off in.",
    "season_type": "regular or postseason; required because both can use the same week number.",
    "week": "Week within season_type.",
    "start_date": "Scheduled game start from the matchup card.",
    "team": "The team this brief is written for. Each game produces two rows, one per side.",
    "opponent": "Who they play.",
    "is_home": "Whether this team is at home.",
    "model_win_prob": "Model probability that THIS team wins, flipped for the away row.",
    "market_win_prob": "De-vigged market probability that this team wins. Null when unpriced.",
    "market_spread": "Spread from THIS team's perspective; negative means they are favoured.",
    "team_sp": "This team's current-season SP+ in net points per game. Higher is better.",
    "opp_sp": "The opponent's current-season SP+.",
    "team_ppa_off": "This team's offensive PPA per play. Higher is better.",
    "opp_ppa_off": "The opponent's offensive PPA per play.",
    "model_minus_market": (
        "model_win_prob minus market_win_prob for this team. A disagreement, not an edge."
    ),
    "headline": "Generated one-line matchup title.",
    "summary": "Generated prose summary of the model, market and rating comparison.",
    "disclaimer_market": "Reminder that market comparisons are analytical, not betting advice.",
    "disclaimer_cfp": "Reminder that playoff figures are projections, not official.",
    "generated_at": "UTC timestamp the brief was generated.",
}

COLUMN_COMMENTS: Mapping[str, Mapping[str, str]] = {
    "preseason_team_ratings": _PRESEASON_TEAM_RATINGS,
    "season_projections": _SEASON_PROJECTIONS,
    "playoff_projections": _SEASON_PROJECTIONS,
    "game_predictions": _GAME_PREDICTIONS,
    "weekly_brief": _WEEKLY_BRIEF,
}


def document_table(spark, table: str, key: str) -> int:
    """Apply only missing or changed Unity Catalog column comments.

    A previous implementation submitted one ALTER TABLE per documented column after every write,
    even when the comments were already correct. DESCRIBE is one metadata request; steady-state
    runs now issue zero ALTERs. The return value is the number of comments changed.
    """
    desired = COLUMN_COMMENTS.get(key, {})
    if not desired:
        return 0

    current = {
        row["col_name"]: row["comment"]
        for row in spark.sql(f"DESCRIBE TABLE {table}").collect()
        if row["col_name"] in desired
    }
    pending = {column: comment for column, comment in desired.items() if current.get(column) != comment}

    for column, comment in pending.items():
        escaped = comment.replace("'", "''")
        spark.sql(f"ALTER TABLE {table} ALTER COLUMN {column} COMMENT '{escaped}'")
    print(f"Table docs: {table} | updated {len(pending)} of {len(desired)} column comments")
    return len(pending)
