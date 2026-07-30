"""Train and score Saturday HQ matchup model.

Important: betting lines are NOT used as training features.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from saturday_hq.config import SaturdayHQConfig
from saturday_hq.table_docs import document_table

# Alias to score with, when one has been assigned in the UC model UI. Scoring falls back to
# the newest version, so a fresh environment works before anyone promotes anything.
MODEL_ALIAS = "production"

FEATURE_COLS = [
    # Prior-season SP+/PPA. The unsuffixed columns are this season's ratings, which CFBD
    # computes from the whole season — for any finished game they already know its result, so
    # training on them buys holdout accuracy that does not exist at kickoff. Last season's
    # ratings are the strongest view of a team that is genuinely available in advance.
    # Once the weekly job has accumulated in-season rating snapshots, these can be replaced by
    # a true as-of rating; see DECISIONS.md.
    "sp_overall_diff_prior",
    "home_sp_offense_prior",
    "home_sp_defense_prior",
    "away_sp_offense_prior",
    "away_sp_defense_prior",
    "ppa_offense_diff_prior",
    "ppa_defense_diff_prior",
    "home_ppa_offense_prior",
    "home_ppa_defense_prior",
    "away_ppa_offense_prior",
    "away_ppa_defense_prior",
    # Signing day precedes the season, so the current season's talent composite is fair game.
    "talent_diff",
    # FBS-only form. The unsuffixed win_pct / avg_margin_l3 include games against non-FBS
    # opponents, where margins average roughly double, which makes the two teams in a matchup
    # incomparable when only one of them has played an FCS opponent. Both live in
    # gold_game_features; only these belong in the model.
    "home_win_pct_fbs",
    "away_win_pct_fbs",
    "home_avg_margin_l3_fbs",
    "away_avg_margin_l3_fbs",
    "neutral_site",
]


def _spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def load_training_frame(config: SaturdayHQConfig) -> pd.DataFrame:
    spark = _spark()
    cols = ["game_id", "season", "week", "home_won", *FEATURE_COLS]
    df = (
        spark.table(config.gold("game_features"))
        .filter(F.col("completed") == True)  # noqa: E712
        .filter(F.col("home_won").isNotNull())
        .select(*cols)
    )
    pdf = df.toPandas()
    pdf["neutral_site"] = pdf["neutral_site"].fillna(False).astype(float)
    pdf["label"] = pdf["home_won"].astype(int)
    return pdf


def time_split(
    pdf: pd.DataFrame,
    train_end_season: int = 2023,
    valid_season: int = 2024,
    test_season: int = 2025,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = pdf[pdf["season"] <= train_end_season].copy()
    valid = pdf[pdf["season"] == valid_season].copy()
    test = pdf[pdf["season"] == test_season].copy()
    return train, valid, test


def build_pipeline() -> Pipeline:
    numeric = FEATURE_COLS
    pre = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            )
        ]
    )
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    return Pipeline(steps=[("pre", pre), ("clf", clf)])


def _metrics(y_true, y_prob) -> dict:
    y_pred = (y_prob >= 0.5).astype(int)
    out = {
        "n": int(len(y_true)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])),
        "accuracy": float((y_pred == y_true).mean()) if len(y_true) else None,
    }
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        out["roc_auc"] = None
    return out


def train_and_register(
    config: SaturdayHQConfig,
    experiment_name: Optional[str] = None,
    model_name: Optional[str] = None,
    train_end_season: int = 2023,
    valid_season: int = 2024,
    test_season: int = 2025,
) -> dict:
    model_name = model_name or config.model_name
    experiment_name = experiment_name or f"/Shared/saturday_hq_{config.env}_matchup"
    mlflow.set_registry_uri("databricks-uc")
    pdf = load_training_frame(config)
    train, valid, test = time_split(pdf, train_end_season, valid_season, test_season)
    if train.empty:
        raise RuntimeError("Training set is empty. Build gold.game_features first.")

    pipe = build_pipeline()
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=f"matchup_{datetime.now(timezone.utc).strftime('%Y%m%d')}") as run:
        pipe.fit(train[FEATURE_COLS], train["label"])
        train_prob = pipe.predict_proba(train[FEATURE_COLS])[:, 1]
        metrics = {
            "train": _metrics(train["label"], train_prob),
            "valid": _metrics(valid["label"], pipe.predict_proba(valid[FEATURE_COLS])[:, 1])
            if not valid.empty
            else {},
            "test": _metrics(test["label"], pipe.predict_proba(test[FEATURE_COLS])[:, 1])
            if not test.empty
            else {},
        }
        mlflow.log_params(
            {
                "train_end_season": train_end_season,
                "valid_season": valid_season,
                "test_season": test_season,
                "features": ",".join(FEATURE_COLS),
                "uses_betting_lines": False,
            }
        )
        for split, vals in metrics.items():
            for k, v in vals.items():
                if v is not None:
                    mlflow.log_metric(f"{split}_{k}", v)

        # Unity Catalog refuses to register a model without a signature. The output is the
        # positive-class probability rather than a label, because that is what score_games
        # consumes and what the app and briefs display.
        signature = infer_signature(train[FEATURE_COLS], train_prob)
        mlflow.sklearn.log_model(
            pipe,
            artifact_path="model",
            signature=signature,
            # Pinned rather than left to the default, which MLflow 3 changed to skops. skops
            # rejects the numpy.dtype references inside a fitted ColumnTransformer unless every
            # type is declared trusted, so a runtime upgrade would otherwise break this call.
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
            registered_model_name=model_name,
        )
        run_id = run.info.run_id

    spark = _spark()
    summary = {
        "run_id": run_id,
        "model_name": model_name,
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    spark.createDataFrame([{"payload": str(summary)}]).write.format("delta").mode(
        "overwrite"
    ).saveAsTable(config.ml("train_summary"))
    return summary


def _newest_version_uri(model_name: str) -> str:
    """Unity Catalog has no `latest` pseudo-version, so resolve the highest version number."""
    versions = MlflowClient().search_model_versions(f"name='{model_name}'")
    if not versions:
        raise RuntimeError(f"No versions registered for {model_name}")
    newest = max(versions, key=lambda v: int(v.version))
    return f"models:/{model_name}/{newest.version}"


def score_games(
    config: SaturdayHQConfig,
    model_uri: Optional[str] = None,
    model_name: Optional[str] = None,
    seasons: Optional[List[int]] = None,
) -> str:
    # UC registered models are referenced by alias, not by the old workspace stages.
    mlflow.set_registry_uri("databricks-uc")
    model_name = model_name or config.model_name
    spark = _spark()
    uri = model_uri or f"models:/{model_name}@{MODEL_ALIAS}"
    try:
        model = mlflow.sklearn.load_model(uri)
        version_label = uri
    except Exception:
        # No @production alias assigned yet; fall back to the newest version.
        uri = _newest_version_uri(model_name)
        model = mlflow.sklearn.load_model(uri)
        version_label = uri

    feats = spark.table(config.gold("game_features"))
    if seasons:
        feats = feats.filter(F.col("season").isin(seasons))
    pdf = feats.select("game_id", "season", "week", *FEATURE_COLS).toPandas()
    pdf["neutral_site"] = pdf["neutral_site"].astype(float)
    probs = model.predict_proba(pdf[FEATURE_COLS])[:, 1]
    scored = pdf[["game_id", "season", "week"]].copy()
    scored["model_home_win_prob"] = probs
    scored["model_version"] = version_label
    scored["scored_at"] = datetime.now(timezone.utc).isoformat()

    # Match the stable table contract explicitly so data can be overwritten without
    # overwriteSchema, which would discard Unity Catalog column comments on every score run.
    sdf = spark.createDataFrame(scored).select(
        F.col("game_id").cast("bigint").alias("game_id"),
        F.col("season").cast("int").alias("season"),
        F.col("week").cast("int").alias("week"),
        F.col("model_home_win_prob").cast("double").alias("model_home_win_prob"),
        F.col("model_version").cast("string").alias("model_version"),
        F.col("scored_at").cast("string").alias("scored_at"),
    )
    table = config.gold("game_predictions")
    if seasons and spark.catalog.tableExists(table):
        requested_seasons = sorted({int(value) for value in seasons})
        predicate = f"season IN ({', '.join(str(value) for value in requested_seasons)})"
        sdf.write.format("delta").mode("overwrite").option("replaceWhere", predicate).saveAsTable(
            table
        )
    else:
        sdf.write.format("delta").mode("overwrite").saveAsTable(table)
    document_table(spark, table, "game_predictions")
    return table
