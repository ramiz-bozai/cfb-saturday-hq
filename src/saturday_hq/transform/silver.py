"""Silver transforms: typed, FBS-filtered entities."""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from saturday_hq.config import CONFERENCE_ALIASES, SaturdayHQConfig


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def _alias_map_expr():
    # Build map for conference normalization
    items = []
    for k, v in CONFERENCE_ALIASES.items():
        items.extend([F.lit(k), F.lit(v)])
    return F.create_map(*items)


def normalize_conference(col):
    m = _alias_map_expr()
    return F.coalesce(m[col], col)


def build_silver_teams(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("teams_fbs"))
    # CFBD FBS teams typically include school, conference, id, abbreviations, logos
    df = (
        raw.select(
            F.col("id").cast("int").alias("team_id"),
            F.coalesce(F.col("school"), F.col("team")).alias("team"),
            F.col("mascot").alias("mascot"),
            F.col("abbreviation").alias("abbreviation"),
            normalize_conference(F.col("conference")).alias("conference"),
            F.col("classification").alias("classification"),
            F.col("color").alias("color"),
            F.col("alternateColor").alias("alternate_color"),
            F.col("logos").alias("logos"),
        )
        .withColumn("is_fbs", F.lit(True))
        .withColumn(
            "is_notre_dame",
            F.lower(F.col("team")) == F.lit("notre dame"),
        )
        .dropDuplicates(["team"])
    )
    table = config.silver("teams")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_conferences(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("conferences"))
    df = raw.select(
        F.col("id").cast("int").alias("conference_id"),
        F.col("name").alias("conference_name"),
        F.col("abbreviation").alias("abbreviation"),
        normalize_conference(F.coalesce(F.col("abbreviation"), F.col("name"))).alias(
            "conference"
        ),
    ).dropDuplicates(["conference"])
    table = config.silver("conferences")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_games(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("games"))
    df = (
        raw.select(
            F.col("id").cast("long").alias("game_id"),
            F.col("season").cast("int").alias("season"),
            F.col("week").cast("int").alias("week"),
            F.col("seasonType").alias("season_type"),
            F.col("startDate").alias("start_date"),
            F.col("completed").cast("boolean").alias("completed"),
            F.col("neutralSite").cast("boolean").alias("neutral_site"),
            F.col("conferenceGame").cast("boolean").alias("conference_game"),
            F.col("homeId").cast("int").alias("home_id"),
            F.col("homeTeam").alias("home_team"),
            F.col("homeConference").alias("home_conference_raw"),
            normalize_conference(F.col("homeConference")).alias("home_conference"),
            F.col("homeClassification").alias("home_classification"),
            F.col("homePoints").cast("int").alias("home_points"),
            F.col("awayId").cast("int").alias("away_id"),
            F.col("awayTeam").alias("away_team"),
            F.col("awayConference").alias("away_conference_raw"),
            normalize_conference(F.col("awayConference")).alias("away_conference"),
            F.col("awayClassification").alias("away_classification"),
            F.col("awayPoints").cast("int").alias("away_points"),
            F.col("venueId").cast("int").alias("venue_id"),
            F.col("venue").alias("venue"),
        )
        .withColumn(
            "is_fbs_game",
            (F.lower(F.coalesce(F.col("home_classification"), F.lit(""))) == "fbs")
            | (F.lower(F.coalesce(F.col("away_classification"), F.lit(""))) == "fbs"),
        )
        .withColumn(
            "home_won",
            F.when(
                F.col("completed") & F.col("home_points").isNotNull() & F.col("away_points").isNotNull(),
                F.col("home_points") > F.col("away_points"),
            ),
        )
        .withColumn(
            "margin_home",
            F.when(
                F.col("completed"),
                F.col("home_points") - F.col("away_points"),
            ),
        )
        .withColumn(
            "total_points",
            F.when(
                F.col("completed"),
                F.col("home_points") + F.col("away_points"),
            ),
        )
        .dropDuplicates(["game_id"])
    )
    # Keep games involving at least one FBS team (SOS / schedule completeness)
    df = df.filter(F.col("is_fbs_game"))
    table = config.silver("games")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_sp_plus(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("sp_plus"))
    # TeamSP typically nests offense/defense objects
    df = raw.select(
        F.col("year").cast("int").alias("season"),
        F.col("team").alias("team"),
        normalize_conference(F.col("conference")).alias("conference"),
        F.col("rating").cast("double").alias("sp_overall"),
        F.col("ranking").cast("int").alias("sp_rank"),
        F.col("secondOrderWins").cast("double").alias("sp_second_order_wins"),
        F.col("sos").cast("double").alias("sp_sos"),
        F.col("offense.rating").cast("double").alias("sp_offense"),
        F.col("defense.rating").cast("double").alias("sp_defense"),
        F.col("specialTeams.rating").cast("double").alias("sp_special_teams"),
    ).dropDuplicates(["season", "team"])
    table = config.silver("sp_plus")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_ppa_teams(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("ppa_teams"))
    df = raw.select(
        F.col("season").cast("int").alias("season"),
        F.col("team").alias("team"),
        normalize_conference(F.col("conference")).alias("conference"),
        F.col("conference").alias("conference_raw"),
        F.col("offense.overall").cast("double").alias("ppa_offense"),
        F.col("offense.passing").cast("double").alias("ppa_offense_passing"),
        F.col("offense.rushing").cast("double").alias("ppa_offense_rushing"),
        F.col("defense.overall").cast("double").alias("ppa_defense"),
        F.col("defense.passing").cast("double").alias("ppa_defense_passing"),
        F.col("defense.rushing").cast("double").alias("ppa_defense_rushing"),
    ).dropDuplicates(["season", "team"])
    table = config.silver("ppa_teams")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_ppa_games(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("ppa_games"))
    df = raw.select(
        F.col("gameId").cast("long").alias("game_id"),
        F.col("season").cast("int").alias("season"),
        F.col("week").cast("int").alias("week"),
        F.col("team").alias("team"),
        F.col("conference").alias("conference_raw"),
        normalize_conference(F.col("conference")).alias("conference"),
        F.col("opponent").alias("opponent"),
        F.col("offense.overall").cast("double").alias("ppa_offense"),
        F.col("defense.overall").cast("double").alias("ppa_defense"),
    ).dropDuplicates(["game_id", "team"])
    table = config.silver("ppa_games")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_lines(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("lines"))
    # Lines payload embeds games with nested lines arrays — flatten.
    if "lines" in raw.columns:
        flat = raw.select(
            F.col("id").cast("long").alias("game_id"),
            F.col("season").cast("int").alias("season"),
            F.col("week").cast("int").alias("week"),
            F.col("seasonType").alias("season_type"),
            F.col("homeTeam").alias("home_team"),
            F.col("awayTeam").alias("away_team"),
            F.explode_outer("lines").alias("line"),
        ).select(
            "game_id",
            "season",
            "week",
            "season_type",
            "home_team",
            "away_team",
            F.col("line.provider").alias("provider"),
            F.col("line.spread").cast("double").alias("spread"),
            F.col("line.formattedSpread").alias("formatted_spread"),
            F.col("line.spreadOpen").cast("double").alias("spread_open"),
            F.col("line.overUnder").cast("double").alias("over_under"),
            F.col("line.overUnderOpen").cast("double").alias("over_under_open"),
            F.col("line.homeMoneyline").cast("double").alias("home_moneyline"),
            F.col("line.awayMoneyline").cast("double").alias("away_moneyline"),
        )
    else:
        flat = raw

    # Prefer consensus-like providers when present; keep all rows + a consensus view.
    table_all = config.silver("lines_all")
    flat.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        table_all
    )

    consensus = (
        flat.withColumn(
            "provider_priority",
            F.when(F.lower(F.col("provider")) == "consensus", 0)
            .when(F.lower(F.col("provider")).isin("draftkings", "bovada", "bolton"), 1)
            .otherwise(2),
        )
        .withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("game_id").orderBy(
                    F.col("provider_priority").asc(), F.col("provider").asc()
                )
            ),
        )
        .filter(F.col("rn") == 1)
        .drop("rn", "provider_priority")
    )
    table = config.silver("lines")
    consensus.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        table
    )
    return table


def build_silver_rankings(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("rankings"))
    # rankings are nested polls -> ranks
    flat = raw.select(
        F.col("season").cast("int").alias("season"),
        F.col("week").cast("int").alias("week"),
        F.col("seasonType").alias("season_type"),
        F.explode_outer("polls").alias("poll"),
    ).select(
        "season",
        "week",
        "season_type",
        F.col("poll.poll").alias("poll"),
        F.explode_outer("poll.ranks").alias("rank"),
    ).select(
        "season",
        "week",
        "season_type",
        "poll",
        F.col("rank.rank").cast("int").alias("rank"),
        F.col("rank.school").alias("team"),
        F.col("rank.conference").alias("conference_raw"),
        normalize_conference(F.col("rank.conference")).alias("conference"),
        F.col("rank.points").cast("double").alias("points"),
        F.col("rank.firstPlaceVotes").cast("int").alias("first_place_votes"),
    )
    table = config.silver("rankings")
    flat.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_talent(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("talent"))
    df = raw.select(
        F.col("year").cast("int").alias("season"),
        F.col("school").alias("team"),
        F.col("talent").cast("double").alias("talent"),
    ).dropDuplicates(["season", "team"])
    table = config.silver("talent")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_silver_recruiting_teams(config: SaturdayHQConfig) -> str:
    spark = _spark()
    raw = spark.table(config.bronze("recruiting_teams"))
    df = raw.select(
        F.col("year").cast("int").alias("season"),
        F.col("team").alias("team"),
        F.col("rank").cast("int").alias("recruiting_rank"),
        F.col("points").cast("double").alias("recruiting_points"),
    ).dropDuplicates(["season", "team"])
    table = config.silver("recruiting_teams")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table


def build_all_silver(config: SaturdayHQConfig) -> list[dict]:
    builders = [
        ("teams", build_silver_teams),
        ("conferences", build_silver_conferences),
        ("games", build_silver_games),
        ("sp_plus", build_silver_sp_plus),
        ("ppa_teams", build_silver_ppa_teams),
        ("ppa_games", build_silver_ppa_games),
        ("lines", build_silver_lines),
        ("rankings", build_silver_rankings),
        ("talent", build_silver_talent),
        ("recruiting_teams", build_silver_recruiting_teams),
    ]
    spark = _spark()
    out = []
    for name, fn in builders:
        table = fn(config)
        out.append({"entity": name, "table": table, "rows": spark.table(table).count()})
    return out
