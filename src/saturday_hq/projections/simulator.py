"""Preseason ratings and CFP-style playoff projections."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from saturday_hq.cfp_rules import TeamSeedInput, select_playoff_field
from saturday_hq.config import DISCLAIMER_CFP, SaturdayHQConfig


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def build_preseason_ratings(config: SaturdayHQConfig, season: Optional[int] = None) -> str:
    """Simple transparent preseason composite emphasizing SP+ and PPA."""
    spark = _spark()
    season = season or config.current_season
    prior = season - 1

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
    sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def _win_prob_from_rating_diff(diff: float) -> float:
    # Logistic transform; 3.0 rating units ~ strong favorite in z-space composite.
    return float(1.0 / (1.0 + np.exp(-1.1 * diff)))


def simulate_season(
    config: SaturdayHQConfig,
    season: Optional[int] = None,
    n_sims: int = 5000,
    use_model_probs: bool = True,
) -> dict:
    """Monte Carlo remaining/full schedule; apply CFP AQ rules on simulated ranks."""
    spark = _spark()
    season = season or config.current_season

    games = (
        spark.table(config.silver("games"))
        .filter(F.col("season") == season)
        .filter(F.lower(F.col("season_type")) == "regular")
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

    teams = sorted(set(games["home_team"]).union(set(games["away_team"])))
    teams = [t for t in teams if t in ratings.index]
    team_index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    win_counts = np.zeros((n_sims, n_teams), dtype=np.int16)
    # Conference champion proxy: most wins within conference among conference games.
    # Simplified: track conference wins.
    conf_map = ratings["conference"].to_dict()

    completed = games[games["completed"] == True]  # noqa: E712
    remaining = games[games["completed"] != True]  # noqa: E712

    base_wins = np.zeros(n_teams, dtype=np.int16)
    for _, g in completed.iterrows():
        if g["home_team"] not in team_index or g["away_team"] not in team_index:
            continue
        if bool(g["home_won"]):
            base_wins[team_index[g["home_team"]]] += 1
        else:
            base_wins[team_index[g["away_team"]]] += 1

    rem_records = remaining.to_dict("records")
    playoff_hits = {t: 0 for t in teams}
    seed_sum = {t: 0.0 for t in teams}
    seed_n = {t: 0 for t in teams}

    for s in range(n_sims):
        wins = base_wins.copy()
        conf_wins = {t: 0 for t in teams}
        # replay completed conference wins
        for _, g in completed.iterrows():
            if g["home_team"] not in team_index or g["away_team"] not in team_index:
                continue
            if not g.get("conference_game"):
                continue
            winner = g["home_team"] if g["home_won"] else g["away_team"]
            if winner in conf_wins:
                conf_wins[winner] += 1

        for g in rem_records:
            ht, at = g["home_team"], g["away_team"]
            if ht not in team_index or at not in team_index:
                continue
            if preds is not None and g["game_id"] in preds.index:
                p_home = float(preds.loc[g["game_id"], "model_home_win_prob"])
            else:
                diff = float(ratings.loc[ht, "rating"] - ratings.loc[at, "rating"])
                if not g.get("neutral_site"):
                    diff += 0.15  # small home edge in rating space
                p_home = _win_prob_from_rating_diff(diff)
            home_win = np.random.random() < p_home
            if home_win:
                wins[team_index[ht]] += 1
                if g.get("conference_game"):
                    conf_wins[ht] += 1
            else:
                wins[team_index[at]] += 1
                if g.get("conference_game"):
                    conf_wins[at] += 1
        win_counts[s, :] = wins

        # Build ranking for this sim from wins then preseason rating tiebreak
        order = sorted(
            teams,
            key=lambda t: (wins[team_index[t]], ratings.loc[t, "rating"]),
            reverse=True,
        )
        # Conference champions by conf wins then rating
        champs = set()
        by_conf = {}
        for t in teams:
            by_conf.setdefault(conf_map.get(t), []).append(t)
        for conf, members in by_conf.items():
            if not conf:
                continue
            champ = sorted(
                members,
                key=lambda t: (conf_wins.get(t, 0), ratings.loc[t, "rating"]),
                reverse=True,
            )[0]
            champs.add(champ)

        seed_inputs = []
        for rank, t in enumerate(order, start=1):
            seed_inputs.append(
                TeamSeedInput(
                    team=t,
                    rank=rank,
                    conference=str(conf_map.get(t) or ""),
                    is_conference_champion=t in champs,
                    is_notre_dame=bool(ratings.loc[t, "is_notre_dame"]),
                )
            )
        field = select_playoff_field(seed_inputs)
        for bid in field:
            if bid.team in playoff_hits:
                playoff_hits[bid.team] += 1
                seed_sum[bid.team] += bid.seed or 0
                seed_n[bid.team] += 1

    # Aggregate
    rows = []
    for t in teams:
        i = team_index[t]
        rows.append(
            {
                "season": season,
                "team": t,
                "conference": conf_map.get(t),
                "mean_wins": float(win_counts[:, i].mean()),
                "median_wins": float(np.median(win_counts[:, i])),
                "win_total_p10": float(np.percentile(win_counts[:, i], 10)),
                "win_total_p90": float(np.percentile(win_counts[:, i], 90)),
                "playoff_odds": playoff_hits[t] / n_sims,
                "avg_seed_if_in": (seed_sum[t] / seed_n[t]) if seed_n[t] else None,
                "n_sims": n_sims,
                "disclaimer": DISCLAIMER_CFP,
            }
        )
    proj = spark.createDataFrame(pd.DataFrame(rows))
    table = config.gold("season_projections")
    proj.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)

    # Convenience playoff board
    playoff = proj.orderBy(F.col("playoff_odds").desc())
    playoff.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        config.gold("playoff_projections")
    )
    return {"season_projections": table, "playoff_projections": config.gold("playoff_projections")}
