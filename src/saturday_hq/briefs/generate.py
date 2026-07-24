"""Generate structured weekly briefs for the App."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from saturday_hq.config import DISCLAIMER_CFP, DISCLAIMER_MARKET, SaturdayHQConfig


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def generate_weekly_briefs(
    config: SaturdayHQConfig,
    season: Optional[int] = None,
    week: Optional[int] = None,
) -> str:
    spark = _spark()
    season = season or config.current_season
    cards = spark.table(config.gold("matchup_card")).filter(F.col("season") == season)
    if week is None:
        week = cards.agg(F.max("week")).collect()[0][0]
    cards = cards.filter(F.col("week") == week)

    # One brief per team appearing on the slate
    home = cards.select(
        F.lit(season).alias("season"),
        F.lit(int(week)).alias("week"),
        F.col("home_team").alias("team"),
        F.col("away_team").alias("opponent"),
        F.lit(True).alias("is_home"),
        F.col("model_home_win_prob").alias("model_win_prob"),
        F.col("market_home_win_prob_implied").alias("market_win_prob"),
        F.col("market_spread"),
        F.col("home_sp_overall").alias("team_sp"),
        F.col("away_sp_overall").alias("opp_sp"),
        F.col("home_ppa_offense").alias("team_ppa_off"),
        F.col("away_ppa_offense").alias("opp_ppa_off"),
        F.col("model_minus_market_home").alias("model_minus_market"),
    )
    away = cards.select(
        F.lit(season).alias("season"),
        F.lit(int(week)).alias("week"),
        F.col("away_team").alias("team"),
        F.col("home_team").alias("opponent"),
        F.lit(False).alias("is_home"),
        (1 - F.col("model_home_win_prob")).alias("model_win_prob"),
        (1 - F.col("market_home_win_prob_implied")).alias("market_win_prob"),
        (-F.col("market_spread")).alias("market_spread"),
        F.col("away_sp_overall").alias("team_sp"),
        F.col("home_sp_overall").alias("opp_sp"),
        F.col("away_ppa_offense").alias("team_ppa_off"),
        F.col("home_ppa_offense").alias("opp_ppa_off"),
        (-F.col("model_minus_market_home")).alias("model_minus_market"),
    )
    base = home.unionByName(away)

    def brief_sql():
        return base.withColumn(
            "headline",
            F.concat(
                F.col("team"),
                F.lit(" vs "),
                F.col("opponent"),
                F.lit(" (Week "),
                F.col("week").cast("string"),
                F.lit(")"),
            ),
        ).withColumn(
            "summary",
            F.concat(
                F.lit("Model win probability: "),
                F.round(F.col("model_win_prob") * 100, 1).cast("string"),
                F.lit("%. "),
                F.lit("Market implied (if available): "),
                F.coalesce(F.round(F.col("market_win_prob") * 100, 1).cast("string"), F.lit("n/a")),
                F.lit("%. "),
                F.lit("SP+ "),
                F.coalesce(F.round(F.col("team_sp"), 1).cast("string"), F.lit("n/a")),
                F.lit(" vs "),
                F.coalesce(F.round(F.col("opp_sp"), 1).cast("string"), F.lit("n/a")),
                F.lit(". PPA offense "),
                F.coalesce(F.round(F.col("team_ppa_off"), 3).cast("string"), F.lit("n/a")),
                F.lit(" vs "),
                F.coalesce(F.round(F.col("opp_ppa_off"), 3).cast("string"), F.lit("n/a")),
                F.lit("."),
            ),
        ).withColumn("disclaimer_market", F.lit(DISCLAIMER_MARKET)).withColumn(
            "disclaimer_cfp", F.lit(DISCLAIMER_CFP)
        ).withColumn("generated_at", F.lit(datetime.now(timezone.utc).isoformat()))

    out = brief_sql()
    table = config.gold("weekly_brief")
    out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table
