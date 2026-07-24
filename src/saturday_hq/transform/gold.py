"""Gold marts: team_week, game_features, matchup_card inputs."""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from saturday_hq.config import POWER4_CANONICAL, G6_CANONICAL, SaturdayHQConfig


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def _american_moneyline_to_prob(ml_col):
    """Convert American moneyline to implied win probability (no vig removal)."""
    return (
        F.when(ml_col.isNull(), F.lit(None).cast("double"))
        .when(ml_col < 0, (-ml_col) / ((-ml_col) + 100.0))
        .otherwise(100.0 / (ml_col + 100.0))
    )


def build_gold_team_week(config: SaturdayHQConfig) -> str:
    """One row per team-season-week using as-of game results + season SP+/PPA.

    SP+/PPA from CFBD team endpoints are typically season aggregates. We attach
    the season values to each week and compute rolling form from completed games.
    """
    spark = _spark()
    games = spark.table(config.silver("games")).filter(F.col("completed") == True)  # noqa: E712
    teams = spark.table(config.silver("teams"))

    home = games.select(
        F.col("season"),
        F.col("week"),
        F.col("game_id"),
        F.col("home_team").alias("team"),
        F.col("away_team").alias("opponent"),
        F.lit(True).alias("is_home"),
        F.col("home_points").alias("points_for"),
        F.col("away_points").alias("points_against"),
        (F.col("home_points") > F.col("away_points")).alias("won"),
    )
    away = games.select(
        F.col("season"),
        F.col("week"),
        F.col("game_id"),
        F.col("away_team").alias("team"),
        F.col("home_team").alias("opponent"),
        F.lit(False).alias("is_home"),
        F.col("away_points").alias("points_for"),
        F.col("home_points").alias("points_against"),
        (F.col("away_points") > F.col("home_points")).alias("won"),
    )
    team_games = home.unionByName(away).join(
        teams.select("team", "conference", "is_notre_dame"), on="team", how="inner"
    )

    w = (
        Window.partitionBy("season", "team")
        .orderBy("week", "game_id")
        .rowsBetween(Window.unboundedPreceding, 0)
    )
    w3 = (
        Window.partitionBy("season", "team")
        .orderBy("week", "game_id")
        .rowsBetween(-2, 0)
    )

    rolling = (
        team_games.withColumn("games_played", F.count("*").over(w))
        .withColumn("wins", F.sum(F.col("won").cast("int")).over(w))
        .withColumn("losses", F.col("games_played") - F.col("wins"))
        .withColumn("point_diff", F.sum(F.col("points_for") - F.col("points_against")).over(w))
        .withColumn("avg_margin_l3", F.avg(F.col("points_for") - F.col("points_against")).over(w3))
        .withColumn("win_pct", F.col("wins") / F.col("games_played"))
    )

    # Keep latest row per team-season-week
    rolling = (
        rolling.withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("season", "team", "week").orderBy(F.col("game_id").desc())
            ),
        )
        .filter(F.col("rn") == 1)
        .drop("rn")
    )

    sp = spark.table(config.silver("sp_plus")).select(
        "season",
        "team",
        "sp_overall",
        "sp_rank",
        "sp_offense",
        "sp_defense",
        "sp_special_teams",
        "sp_sos",
    )
    ppa = spark.table(config.silver("ppa_teams")).select(
        "season",
        "team",
        "ppa_offense",
        "ppa_defense",
        "ppa_offense_passing",
        "ppa_offense_rushing",
        "ppa_defense_passing",
        "ppa_defense_rushing",
    )
    talent = spark.table(config.silver("talent"))
    recruiting = spark.table(config.silver("recruiting_teams"))

    out = (
        rolling.join(sp, ["season", "team"], "left")
        .join(ppa, ["season", "team"], "left")
        .join(talent, ["season", "team"], "left")
        .join(recruiting, ["season", "team"], "left")
        .withColumn(
            "conference_group",
            F.when(F.col("conference").isin(list(POWER4_CANONICAL)), F.lit("Power4"))
            .when(F.col("conference").isin(list(G6_CANONICAL)), F.lit("G6"))
            .when(F.col("is_notre_dame"), F.lit("Independent"))
            .otherwise(F.lit("Other")),
        )
    )

    table = config.gold("team_week")
    out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_gold_game_features(config: SaturdayHQConfig) -> str:
    """One row per FBS game with home/away as-of features + market line + labels.

    Model features intentionally exclude betting lines.
    """
    spark = _spark()
    games = spark.table(config.silver("games"))
    tw = spark.table(config.gold("team_week"))
    lines = spark.table(config.silver("lines")).select(
        "game_id",
        F.col("provider").alias("line_provider"),
        F.col("spread").alias("market_spread"),
        F.col("spread_open").alias("market_spread_open"),
        F.col("over_under").alias("market_ou"),
        F.col("home_moneyline").alias("market_home_ml"),
        F.col("away_moneyline").alias("market_away_ml"),
    )

    # As-of join: use team_week for the same season and week <= game week.
    # Prefer exact week; else latest prior week.
    def asof_team(side: str):
        side_tw = tw.select(
            F.col("season"),
            F.col("week").alias("feature_week"),
            F.col("team").alias(f"{side}_team_key"),
            F.col("conference").alias(f"{side}_conference"),
            F.col("sp_overall").alias(f"{side}_sp_overall"),
            F.col("sp_offense").alias(f"{side}_sp_offense"),
            F.col("sp_defense").alias(f"{side}_sp_defense"),
            F.col("ppa_offense").alias(f"{side}_ppa_offense"),
            F.col("ppa_defense").alias(f"{side}_ppa_defense"),
            F.col("talent").alias(f"{side}_talent"),
            F.col("recruiting_points").alias(f"{side}_recruiting_points"),
            F.col("win_pct").alias(f"{side}_win_pct"),
            F.col("avg_margin_l3").alias(f"{side}_avg_margin_l3"),
            F.col("point_diff").alias(f"{side}_point_diff"),
            F.col("games_played").alias(f"{side}_games_played"),
        )
        team_col = f"{side}_team"
        joined = games.select(
            "game_id",
            "season",
            "week",
            F.col(team_col).alias(f"{side}_team_key"),
        ).join(
            side_tw,
            on=[
                "season",
                f"{side}_team_key",
            ],
            how="left",
        ).filter(
            (F.col("feature_week").isNull()) | (F.col("feature_week") <= F.col("week"))
        )
        w = Window.partitionBy("game_id").orderBy(F.col("feature_week").desc_nulls_last())
        return (
            joined.withColumn("rn", F.row_number().over(w))
            .filter(F.col("rn") == 1)
            .drop("rn", "week")
            .withColumnRenamed(f"{side}_team_key", f"{side}_team")
        )

    home_feats = asof_team("home")
    away_feats = asof_team("away")

    base = games.select(
        "game_id",
        "season",
        "week",
        "season_type",
        "start_date",
        "completed",
        "neutral_site",
        "home_team",
        "away_team",
        "home_conference",
        "away_conference",
        "home_points",
        "away_points",
        "home_won",
        "margin_home",
        "total_points",
    )

    out = (
        base.join(home_feats.drop("season"), on=["game_id", "home_team"], how="left")
        .join(away_feats.drop("season"), on=["game_id", "away_team"], how="left")
        .join(lines, on="game_id", how="left")
        .withColumn("market_home_win_prob_implied", _american_moneyline_to_prob(F.col("market_home_ml")))
        .withColumn(
            "sp_overall_diff",
            F.col("home_sp_overall") - F.col("away_sp_overall"),
        )
        .withColumn(
            "ppa_offense_diff",
            F.col("home_ppa_offense") - F.col("away_ppa_offense"),
        )
        .withColumn(
            "ppa_defense_diff",
            F.col("home_ppa_defense") - F.col("away_ppa_defense"),
        )
        .withColumn(
            "talent_diff",
            F.col("home_talent") - F.col("away_talent"),
        )
    )

    # FBS-FBS focus for modeling
    fbs_teams = spark.table(config.silver("teams")).select(F.col("team").alias("t"))
    out = (
        out.join(fbs_teams.withColumnRenamed("t", "home_team"), on="home_team", how="inner")
        .join(fbs_teams.withColumnRenamed("t", "away_team"), on="away_team", how="inner")
    )

    table = config.gold("game_features")
    out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_gold_matchup_card(config: SaturdayHQConfig) -> str:
    spark = _spark()
    feats = spark.table(config.gold("game_features"))
    preds = spark.table(config.gold("game_predictions"))

    card = (
        feats.alias("f")
        .join(preds.alias("p"), on="game_id", how="left")
        .select(
            "f.*",
            F.col("p.model_home_win_prob"),
            F.col("p.model_version"),
            F.col("p.scored_at"),
            (
                F.col("p.model_home_win_prob")
                - F.coalesce(F.col("f.market_home_win_prob_implied"), F.lit(None))
            ).alias("model_minus_market_home"),
        )
        .withColumn("disclaimer_market", F.lit(
            "For analysis and entertainment only. Not gambling advice."
        ))
    )
    table = config.gold("matchup_card")
    card.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_gold_core(config: SaturdayHQConfig) -> list[dict]:
    spark = _spark()
    results = []
    for name, fn in [
        ("team_week", build_gold_team_week),
        ("game_features", build_gold_game_features),
    ]:
        table = fn(config)
        results.append({"mart": name, "table": table, "rows": spark.table(table).count()})
    return results
