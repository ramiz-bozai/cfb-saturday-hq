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
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from saturday_hq.config import SaturdayHQConfig

FEATURE_COLS = [
    "sp_overall_diff",
    "home_sp_offense",
    "home_sp_defense",
    "away_sp_offense",
    "away_sp_defense",
    "ppa_offense_diff",
    "ppa_defense_diff",
    "home_ppa_offense",
    "home_ppa_defense",
    "away_ppa_offense",
    "away_ppa_defense",
    "talent_diff",
    "home_win_pct",
    "away_win_pct",
    "home_avg_margin_l3",
    "away_avg_margin_l3",
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
    experiment_name: str = "/Shared/saturday_hq_matchup",
    model_name: str = "saturday_hq_matchup",
    train_end_season: int = 2023,
    valid_season: int = 2024,
    test_season: int = 2025,
) -> dict:
    pdf = load_training_frame(config)
    train, valid, test = time_split(pdf, train_end_season, valid_season, test_season)
    if train.empty:
        raise RuntimeError("Training set is empty. Build gold.game_features first.")

    pipe = build_pipeline()
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=f"matchup_{datetime.now(timezone.utc).strftime('%Y%m%d')}") as run:
        pipe.fit(train[FEATURE_COLS], train["label"])
        metrics = {
            "train": _metrics(train["label"], pipe.predict_proba(train[FEATURE_COLS])[:, 1]),
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

        mlflow.sklearn.log_model(pipe, artifact_path="model", registered_model_name=model_name)
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


def score_games(
    config: SaturdayHQConfig,
    model_uri: Optional[str] = None,
    model_name: str = "saturday_hq_matchup",
    seasons: Optional[List[int]] = None,
) -> str:
    spark = _spark()
    uri = model_uri or f"models:/{model_name}/Production"
    try:
        model = mlflow.sklearn.load_model(uri)
        version_label = uri
    except Exception:
        # Fall back to latest version if Production alias is not set
        uri = f"models:/{model_name}/latest"
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

    sdf = spark.createDataFrame(scored)
    table = config.gold("game_predictions")
    sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return table
