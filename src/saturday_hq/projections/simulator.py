"""Preseason ratings and CFP-style playoff projections."""

from __future__ import annotations

from time import perf_counter
from typing import Optional

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from saturday_hq.cfp_rules import TeamSeedInput, select_playoff_field
from saturday_hq.config import DISCLAIMER_CFP, SaturdayHQConfig
from saturday_hq.table_docs import document_table


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def build_preseason_ratings(config: SaturdayHQConfig, season: Optional[int] = None) -> str:
    """Simple transparent preseason composite emphasizing SP+ and PPA."""
    started = perf_counter()
    spark = _spark()
    season = season or config.current_season
    prior = season - 1
    print(f"Preseason ratings: season={season} | prior-rating season={prior}")

    # Season-grained, because the CFP automatic-qualifier logic keys off conference and this
    # function is parameterized by season: silver_teams would hand a 2019 run today's alignment.
    team_seasons = spark.table(config.silver("team_seasons"))
    team_cols = ("team", "conference", "is_notre_dame")
    teams = team_seasons.filter(F.col("season") == season).select(*team_cols)
    if teams.isEmpty():
        # A season's membership is not landed until that season's first ingest, so a preseason
        # run before kickoff falls back to the newest season on hand.
        newest = team_seasons.agg(F.max("season")).collect()[0][0]
        teams = team_seasons.filter(F.col("season") == newest).select(*team_cols)
    sp = spark.table(config.silver("sp_plus")).filter(F.col("season") == prior)
    ppa = spark.table(config.silver("ppa_teams")).filter(F.col("season") == prior)
    talent = spark.table(config.silver("talent")).filter(F.col("season") == season)
    # Fall back talent to prior if current class missing
    talent_prior = spark.table(config.silver("talent")).filter(F.col("season") == prior)

    pdf = (
        teams.join(sp.select("team", "sp_overall", "sp_offense", "sp_defense"), "team", "left")
        .join(ppa.select("team", "ppa_offense", "ppa_defense"), "team", "left")
        .join(talent.select("team", F.col("talent").alias("talent_curr")), "team", "left")
        .join(talent_prior.select("team", F.col("talent").alias("talent_prior")), "team", "left")
        .withColumn("season", F.lit(season))
        .toPandas()
    )
    pdf["talent"] = pdf["talent_curr"].fillna(pdf["talent_prior"])
    for col in ["sp_overall", "sp_offense", "sp_defense", "ppa_offense", "ppa_defense", "talent"]:
        pdf[col] = pdf[col].astype(float)
        pdf[f"z_{col}"] = (pdf[col] - pdf[col].mean()) / (pdf[col].std(ddof=0) + 1e-9)

    # Defense PPA: lower (more negative for opponent PPA allowed) is better depending on CFBD sign.
    # CFBD defense.overall is generally opponent PPA — lower is better. Invert z for defense.
    pdf["rating"] = (
        0.45 * pdf["z_sp_overall"].fillna(0)
        + 0.20 * pdf["z_sp_offense"].fillna(0)
        + 0.15 * (-pdf["z_sp_defense"].fillna(0))
        + 0.10 * pdf["z_ppa_offense"].fillna(0)
        + 0.05 * (-pdf["z_ppa_defense"].fillna(0))
        + 0.05 * pdf["z_talent"].fillna(0)
    )
    pdf["preseason_rank"] = pdf["rating"].rank(ascending=False, method="min").astype(int)
    pdf["disclaimer"] = DISCLAIMER_CFP
    keep = [
        "season",
        "team",
        "conference",
        "is_notre_dame",
        "sp_overall",
        "ppa_offense",
        "ppa_defense",
        "talent",
        "rating",
        "preseason_rank",
        "disclaimer",
    ]
    sdf = spark.createDataFrame(pdf[keep])
    table = config.gold("preseason_team_ratings")
    sdf.write.format("delta").mode("overwrite").saveAsTable(table)
    document_table(spark, table, "preseason_team_ratings")
    print(
        f"Preseason ratings: wrote {len(pdf)} teams to {table} | "
        f"elapsed={perf_counter() - started:.1f}s"
    )
    return table


def _win_prob_from_rating_diff(diff: float) -> float:
    # Logistic transform; 3.0 rating units ~ strong favorite in z-space composite.
    return float(1.0 / (1.0 + np.exp(-1.1 * diff)))


def _is_true(value) -> bool:
    return bool(value) if pd.notna(value) else False


def simulate_season(
    config: SaturdayHQConfig,
    season: Optional[int] = None,
    n_sims: int = 5000,
    use_model_probs: bool = True,
    random_seed: Optional[int] = None,
) -> dict:
    """Monte Carlo remaining/full schedule; apply CFP AQ rules on simulated ranks."""
    if n_sims < 1:
        raise ValueError("n_sims must be at least 1")

    started = perf_counter()
    spark = _spark()
    season = season or config.current_season
    print(f"Season simulation: season={season} | requested simulations={n_sims}")

    read_started = perf_counter()
    games = (
        spark.table(config.silver("games"))
        .filter(F.col("season") == season)
        .filter(F.lower(F.col("season_type")) == "regular")
        .orderBy("game_id")
        .toPandas()
    )
    ratings = (
        spark.table(config.gold("preseason_team_ratings"))
        .filter(F.col("season") == season)
        .toPandas()
        .set_index("team")
    )

    preds = None
    if use_model_probs:
        try:
            preds = (
                spark.table(config.gold("game_predictions"))
                .filter(F.col("season") == season)
                .toPandas()
                .set_index("game_id")
            )
        except Exception:
            preds = None
    read_seconds = perf_counter() - read_started

    teams = sorted(set(games["home_team"]).union(set(games["away_team"])))
    teams = [team for team in teams if team in ratings.index]
    if not teams:
        raise RuntimeError(f"No rated teams available to simulate season {season}")

    team_index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    rating_values = ratings.loc[teams, "rating"].astype(float).to_numpy()
    conferences = ratings.loc[teams, "conference"].fillna("").astype(str).to_numpy()
    notre_dame = ratings.loc[teams, "is_notre_dame"].fillna(False).astype(bool).to_numpy()
    conference_members = {
        conference: np.flatnonzero(conferences == conference)
        for conference in sorted(set(conferences))
        if conference
    }

    completed = games[games["completed"] == True]  # noqa: E712
    remaining = games[games["completed"] != True]  # noqa: E712

    base_wins = np.zeros(n_teams, dtype=np.int16)
    base_conf_wins = np.zeros(n_teams, dtype=np.int16)
    for game in completed.itertuples(index=False):
        if game.home_team not in team_index or game.away_team not in team_index:
            continue
        winner = game.home_team if _is_true(game.home_won) else game.away_team
        winner_index = team_index[winner]
        base_wins[winner_index] += 1
        if _is_true(game.conference_game):
            base_conf_wins[winner_index] += 1

    prediction_map = (
        preds["model_home_win_prob"].to_dict()
        if preds is not None and "model_home_win_prob" in preds
        else {}
    )
    remaining_home = []
    remaining_away = []
    remaining_conference = []
    remaining_home_prob = []
    for g in remaining.to_dict("records"):
        home = g["home_team"]
        away = g["away_team"]
        if home not in team_index or away not in team_index:
            continue
        home_index = team_index[home]
        away_index = team_index[away]
        probability = prediction_map.get(g["game_id"])
        if probability is None or not np.isfinite(float(probability)):
            rating_diff = rating_values[home_index] - rating_values[away_index]
            if not _is_true(g.get("neutral_site", False)):
                # ~0.30 on the z-score composite ≈ 58% home when ratings are equal
                # (historical FBS home win rates ~57–60%). Fallback only — trained model
                # uses its own neutral_site feature when model_home_win_prob exists.
                rating_diff += 0.30
            probability = _win_prob_from_rating_diff(float(rating_diff))
        remaining_home.append(home_index)
        remaining_away.append(away_index)
        remaining_conference.append(_is_true(g.get("conference_game", False)))
        remaining_home_prob.append(float(probability))

    remaining_home = np.asarray(remaining_home, dtype=np.intp)
    remaining_away = np.asarray(remaining_away, dtype=np.intp)
    remaining_conference = np.asarray(remaining_conference, dtype=bool)
    remaining_home_prob = np.asarray(remaining_home_prob, dtype=float)

    effective_n_sims = 1 if remaining_home.size == 0 else n_sims
    print(
        f"Season simulation inputs: teams={n_teams} | regular games={len(games)} | "
        f"completed={len(completed)} | remaining={len(remaining)} | "
        f"simulated remaining={remaining_home.size} | "
        f"model probabilities={len(prediction_map)} | "
        f"effective simulations={effective_n_sims} | read={read_seconds:.1f}s"
    )
    if remaining_home.size == 0:
        print(
            "Season simulation note: no rated remaining regular-season games. Results are "
            f"deterministic; short-circuiting {n_sims} requested simulations to one pass."
        )

    simulation_started = perf_counter()
    win_counts = np.repeat(base_wins[None, :], effective_n_sims, axis=0)
    conf_win_counts = np.repeat(base_conf_wins[None, :], effective_n_sims, axis=0)
    if remaining_home.size:
        rng = np.random.default_rng(random_seed)
        home_wins = rng.random((effective_n_sims, remaining_home.size)) < remaining_home_prob
        winner_indices = np.where(home_wins, remaining_home, remaining_away)
        simulation_indices = np.arange(effective_n_sims)[:, None]
        np.add.at(win_counts, (simulation_indices, winner_indices), 1)
        conference_winners = winner_indices[:, remaining_conference]
        if conference_winners.size:
            np.add.at(conf_win_counts, (simulation_indices, conference_winners), 1)

    playoff_hits = np.zeros(n_teams, dtype=np.int32)
    seed_sum = np.zeros(n_teams, dtype=float)
    seed_n = np.zeros(n_teams, dtype=np.int32)

    progress_every = max(1, effective_n_sims // 10)
    for simulation_index in range(effective_n_sims):
        wins = win_counts[simulation_index]
        conference_wins = conf_win_counts[simulation_index]
        order = np.lexsort((-rating_values, -wins))
        champion_indices = set()
        for members in conference_members.values():
            member_order = np.lexsort((-rating_values[members], -conference_wins[members]))
            champion_indices.add(int(members[member_order[0]]))

        seed_inputs = []
        for rank, index in enumerate(order, start=1):
            seed_inputs.append(
                TeamSeedInput(
                    team=teams[index],
                    rank=rank,
                    conference=conferences[index],
                    is_conference_champion=int(index) in champion_indices,
                    is_notre_dame=bool(notre_dame[index]),
                )
            )
        field = select_playoff_field(seed_inputs)
        for bid in field:
            index = team_index.get(bid.team)
            if index is not None:
                playoff_hits[index] += 1
                seed_sum[index] += bid.seed or 0
                seed_n[index] += 1
        completed_sims = simulation_index + 1
        if completed_sims == effective_n_sims or completed_sims % progress_every == 0:
            print(
                f"Season simulation progress: {completed_sims}/{effective_n_sims} "
                f"({100 * completed_sims / effective_n_sims:.0f}%)"
            )
    simulation_seconds = perf_counter() - simulation_started

    # Aggregate
    rows = []
    for team, index in team_index.items():
        rows.append(
            {
                "season": season,
                "team": team,
                "conference": conferences[index],
                "mean_wins": float(win_counts[:, index].mean()),
                "median_wins": float(np.median(win_counts[:, index])),
                "win_total_p10": float(np.percentile(win_counts[:, index], 10)),
                "win_total_p90": float(np.percentile(win_counts[:, index], 90)),
                "playoff_odds": playoff_hits[index] / effective_n_sims,
                "avg_seed_if_in": (
                    seed_sum[index] / seed_n[index] if seed_n[index] else None
                ),
                "n_sims": effective_n_sims,
                "disclaimer": DISCLAIMER_CFP,
            }
        )
    write_started = perf_counter()
    proj = spark.createDataFrame(pd.DataFrame(rows))
    table = config.gold("season_projections")
    proj.write.format("delta").mode("overwrite").saveAsTable(table)
    document_table(spark, table, "season_projections")

    # Convenience playoff board
    playoff = proj.orderBy(F.col("playoff_odds").desc())
    playoff.write.format("delta").mode("overwrite").saveAsTable(config.gold("playoff_projections"))
    document_table(spark, config.gold("playoff_projections"), "playoff_projections")
    write_seconds = perf_counter() - write_started
    print(
        f"Season simulation complete: simulation={simulation_seconds:.1f}s | "
        f"write+metadata={write_seconds:.1f}s | total={perf_counter() - started:.1f}s"
    )
    return {"season_projections": table, "playoff_projections": config.gold("playoff_projections")}
