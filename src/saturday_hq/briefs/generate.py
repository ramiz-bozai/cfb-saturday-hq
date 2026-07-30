"""Generate structured weekly briefs for the App."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from saturday_hq.config import DISCLAIMER_CFP, DISCLAIMER_MARKET, SaturdayHQConfig
from saturday_hq.table_docs import document_table


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def _brief_rows(cards):
    """Turn one matchup-card row into one brief per team perspective."""
    home = cards.select(
        "game_id",
        "season",
        "season_type",
        "week",
        "start_date",
        F.col("home_team").alias("team"),
        F.col("away_team").alias("opponent"),
        F.lit(True).alias("is_home"),
        F.col("model_home_win_prob").alias("model_win_prob"),
        F.col("market_home_win_prob_novig").alias("market_win_prob"),
        F.col("market_spread"),
        F.col("home_sp_overall").alias("team_sp"),
        F.col("away_sp_overall").alias("opp_sp"),
        F.col("home_ppa_offense").alias("team_ppa_off"),
        F.col("away_ppa_offense").alias("opp_ppa_off"),
        F.col("model_minus_market_home").alias("model_minus_market"),
    )
    away = cards.select(
        "game_id",
        "season",
        "season_type",
        "week",
        "start_date",
        F.col("away_team").alias("team"),
        F.col("home_team").alias("opponent"),
        F.lit(False).alias("is_home"),
        (1 - F.col("model_home_win_prob")).alias("model_win_prob"),
        # Valid only because the de-vigged pair sums to 1; with the raw price it did not, so the
        # away side's market probability used to come out roughly 2 points light.
        (1 - F.col("market_home_win_prob_novig")).alias("market_win_prob"),
        (-F.col("market_spread")).alias("market_spread"),
        F.col("away_sp_overall").alias("team_sp"),
        F.col("home_sp_overall").alias("opp_sp"),
        F.col("away_ppa_offense").alias("team_ppa_off"),
        F.col("home_ppa_offense").alias("opp_ppa_off"),
        (-F.col("model_minus_market_home")).alias("model_minus_market"),
    )
    base = home.unionByName(away)

    def percent_text(column: str):
        return F.when(F.col(column).isNull(), F.lit("n/a")).otherwise(
            F.concat(F.round(F.col(column) * 100, 1).cast("string"), F.lit("%"))
        )

    return (
        base.withColumn(
            "headline",
            F.concat(
                F.col("team"),
                F.lit(" vs "),
                F.col("opponent"),
                F.lit(" ("),
                F.initcap(F.col("season_type")),
                F.lit(" Week "),
                F.col("week").cast("string"),
                F.lit(")"),
            ),
        )
        .withColumn(
            "summary",
            F.concat(
                F.lit("Model win probability: "),
                percent_text("model_win_prob"),
                F.lit(". "),
                F.lit("Market implied (if available): "),
                percent_text("market_win_prob"),
                F.lit(". "),
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
        )
        .withColumn("disclaimer_market", F.lit(DISCLAIMER_MARKET))
        .withColumn("disclaimer_cfp", F.lit(DISCLAIMER_CFP))
        .withColumn("generated_at", F.lit(datetime.now(timezone.utc).isoformat()))
    )


def generate_weekly_briefs(
    config: SaturdayHQConfig,
    season: Optional[int] = None,
    week: Optional[int] = None,
    season_type: str = "regular",
) -> str:
    """Refresh one season/type of briefs without deleting any other historical scope.

    `week=None` intentionally means every week in the requested season/type. The App has a week
    selector, so persisting only the numerically highest scheduled week made nearly every selection
    return no data. Supplying a week remains useful for a targeted repair.
    """
    started = perf_counter()
    spark = _spark()
    season = season or config.current_season
    season_type = season_type.strip().lower()
    if season_type not in {"regular", "postseason"}:
        raise ValueError("season_type must be 'regular' or 'postseason'")
    table = config.gold("weekly_brief")
    table_exists = spark.catalog.tableExists(table)
    existing_columns = set(spark.table(table).columns) if table_exists else set()
    predicate = f"season = {season} AND season_type = '{season_type}'"
    if week is not None:
        predicate += f" AND week = {int(week)}"

    cards = (
        spark.table(config.gold("matchup_card"))
        .filter(F.col("season") == season)
        .filter(F.lower(F.col("season_type")) == season_type)
    )
    if week is not None:
        cards = cards.filter(F.col("week") == int(week))

    out = _brief_rows(cards).cache()
    card_count = cards.count()
    brief_count = out.count()
    if card_count == 0:
        out.unpersist()
        requested_week = "all weeks" if week is None else f"week {int(week)}"
        if table_exists and "season_type" in existing_columns:
            spark.sql(f"DELETE FROM {table} WHERE {predicate}")
            outcome = "removed any stale rows in that scope"
        else:
            outcome = "no compatible brief table exists yet"
        print(
            f"Weekly briefs: no matchup-card games for season={season}, "
            f"season_type={season_type}, {requested_week}; {outcome}; other history preserved"
        )
        return table
    expected = card_count * 2
    if brief_count != expected:
        out.unpersist()
        raise RuntimeError(f"Expected {expected} brief rows from {card_count} games, got {brief_count}")

    scope = f"season={season}, season_type={season_type}"
    if week is not None:
        scope += f", week={int(week)}"
    print(f"Weekly briefs: {scope} | games={card_count} | team briefs={brief_count}")

    expected_columns = set(out.columns)

    if not table_exists:
        out.write.format("delta").partitionBy("season", "season_type").saveAsTable(table)
        write_mode = "created"
    elif existing_columns != expected_columns:
        # One-time schema migration from the old week-only table. Recompute every available card
        # so adding game_id/season_type cannot erase or strand historical rows.
        print("Weekly briefs: schema changed; rebuilding all seasons and season types once")
        all_out = _brief_rows(spark.table(config.gold("matchup_card")))
        all_out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
            table
        )
        write_mode = "migrated full history"
    else:
        out.write.format("delta").mode("overwrite").option("replaceWhere", predicate).saveAsTable(table)
        write_mode = f"replaced only {predicate}"

    document_table(spark, table, "weekly_brief")
    out.unpersist()
    total_rows = spark.table(table).count()
    total_seasons = spark.table(table).select("season").distinct().count()
    print(
        f"Weekly briefs: {write_mode} | stored rows={total_rows} across "
        f"{total_seasons} season(s) | elapsed={perf_counter() - started:.1f}s"
    )
    return table
