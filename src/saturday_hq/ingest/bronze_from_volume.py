"""Load Volume JSONL files into bronze Delta tables."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from saturday_hq.config import HISTORICAL_DOMAINS, SaturdayHQConfig


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def read_domain_jsonl(
    config: SaturdayHQConfig,
    domain: str,
    mode: str = "historical",
) -> DataFrame:
    """Read JSONL for a domain from historical and/or incremental Volume paths."""
    spark = _spark()
    paths = []
    if mode in {"historical", "both"}:
        paths.append(f"{config.historical_path}/{domain}/")
    if mode in {"incremental", "both"}:
        paths.append(f"{config.incremental_path}/")

    frames = []
    for path in paths:
        try:
            if mode == "incremental" or (mode == "both" and "incremental" in path):
                # incremental layout: dt=.../<domain>/<domain>.jsonl
                df = (
                    spark.read.option("recursiveFileLookup", "true")
                    .json(f"{config.incremental_path}/*/{domain}/")
                    .withColumn("_source_path", F.input_file_name())
                    .withColumn("_ingest_mode", F.lit("incremental"))
                )
            else:
                df = (
                    spark.read.option("recursiveFileLookup", "true")
                    .json(path)
                    .withColumn("_source_path", F.input_file_name())
                    .withColumn("_ingest_mode", F.lit("historical"))
                )
            frames.append(df)
        except Exception:
            # Path may not exist yet.
            continue

    if not frames:
        return spark.createDataFrame([], schema=" _source_path string, _ingest_mode string")

    out = frames[0]
    for frame in frames[1:]:
        out = out.unionByName(frame, allowMissingColumns=True)
    return out.withColumn("_ingested_at", F.current_timestamp())


def write_bronze_domain(
    config: SaturdayHQConfig,
    domain: str,
    mode: str = "both",
) -> str:
    df = read_domain_jsonl(config, domain, mode=mode)
    table = config.bronze(domain)
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table)
    )
    return table


def load_all_bronze(
    config: SaturdayHQConfig,
    domains: Optional[Sequence[str]] = None,
    mode: str = "both",
) -> list[dict]:
    domain_list = list(domains) if domains is not None else list(HISTORICAL_DOMAINS)
    spark = _spark()
    results = []
    for domain in domain_list:
        table = write_bronze_domain(config, domain, mode=mode)
        count = spark.table(table).count()
        results.append({"domain": domain, "table": table, "rows": count})
    # Manifest table for ops visibility
    if results:
        spark.createDataFrame(results).withColumn(
            "loaded_at", F.current_timestamp()
        ).write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(config.bronze("load_manifest"))
    return results
