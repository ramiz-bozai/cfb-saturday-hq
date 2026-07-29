"""Leakage audit for the matchup model, run locally against the SQL warehouse.

Refits the exact pipeline from src/saturday_hq/ml/train.py over gold.game_features and prints
holdout metrics beside the sportsbook's own accuracy on the same games. No cluster needed, so
this is cheap enough to run before every training job.

The market column is the point. A logistic regression on season aggregates has no business
beating a sportsbook by a wide margin, so if this script reports a much better AUC than the
market's, assume a feature is carrying the answer rather than celebrating. That signature is
what surfaced the week <= game_week as-of bug: 0.95 AUC against the market's 0.79.

    source .venv/bin/activate
    set -a; source .env; set +a
    python scripts/feature_audit.py [--variant CANDIDATE=col1,col2 ...]

Each --variant refits with the named columns swapped in for their unsuffixed counterparts,
which is how the _fbs form and _prior ratings decisions were measured.
"""

from __future__ import annotations

import argparse
import ast
import os
import pathlib

import numpy as np
from databricks import sql
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TRAIN_FILE = pathlib.Path(__file__).resolve().parent.parent / "src" / "saturday_hq" / "ml" / "train.py"


def load_feature_cols(path: pathlib.Path = TRAIN_FILE) -> list[str]:
    """Read FEATURE_COLS out of train.py without importing it.

    Importing would pull in pyspark, which only exists on the cluster, and the whole point of
    this script is to run locally. Parsing keeps one source of truth for the feature list.
    """
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "FEATURE_COLS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"FEATURE_COLS not found in {path}")


FEATURE_COLS = load_feature_cols()

TRAIN_END_SEASON = 2023
VALID_SEASON = 2024
TEST_SEASON = 2025

# Beyond this much better than the sportsbook, disbelieve the model rather than the market.
SUSPICIOUS_AUC_GAP = 0.05


def fetch(catalog: str, schema: str, extra_cols: list[str]):
    cols = sorted(
        {"game_id", "season", "week", "home_won", "market_home_ml", "market_away_ml"}
        | set(FEATURE_COLS)
        | set(extra_cols)
    )
    query = f"""
        select {', '.join(cols)}
        from {catalog}.{schema}.game_features
        where completed and home_won is not null
    """
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].strip("/"),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DBT_ACCESS_TOKEN"],
    ) as conn:
        pdf = conn.cursor().execute(query).fetchall_arrow().to_pandas()
    pdf["neutral_site"] = pdf["neutral_site"].fillna(False).astype(float)
    pdf["label"] = pdf["home_won"].astype(int)
    return pdf


def build_pipeline(features: list[str]) -> Pipeline:
    """Mirror of train.build_pipeline, parameterized by feature list."""
    pre = ColumnTransformer(
        [(
            "num",
            Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
            features,
        )]
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])


def score(y, p) -> dict:
    return {
        "n": len(y),
        "brier": brier_score_loss(y, p),
        "logloss": log_loss(y, p, labels=[0, 1]),
        "acc": ((p >= 0.5).astype(int) == y).mean(),
        "auc": roc_auc_score(y, p),
    }


def american_to_prob(ml):
    ml = ml.astype(float)
    return np.where(ml < 0, -ml / (-ml + 100.0), 100.0 / (ml + 100.0))


def market_probs(split):
    """De-vigged home probability, matching the no_vig_home_prob dbt macro."""
    m = split.dropna(subset=["market_home_ml", "market_away_ml"])
    home = american_to_prob(m.market_home_ml)
    away = american_to_prob(m.market_away_ml)
    return m["label"].values, np.clip(home / (home + away), 1e-6, 1 - 1e-6)


def row(label: str, split_name: str, s: dict) -> str:
    return (f"{label:38s} {split_name:11s} {s['n']:5d} {s['brier']:8.4f} "
            f"{s['logloss']:9.4f} {s['acc']:7.2%} {s['auc']:7.4f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=os.environ.get("DATABRICKS_CATALOG_DEV", "cfb_saturday_hq_dev"))
    ap.add_argument("--schema", default="cfb_gold")
    ap.add_argument(
        "--variant",
        action="append",
        default=[],
        metavar="NAME=col1,col2",
        help="Refit with these columns replacing their unsuffixed counterparts.",
    )
    args = ap.parse_args()

    variants = {}
    for spec in args.variant:
        name, _, cols = spec.partition("=")
        variants[name] = [c.strip() for c in cols.split(",") if c.strip()]

    pdf = fetch(args.catalog, args.schema, [c for cols in variants.values() for c in cols])
    train = pdf[pdf.season <= TRAIN_END_SEASON]
    holdouts = {
        f"valid {VALID_SEASON}": pdf[pdf.season == VALID_SEASON],
        f"test {TEST_SEASON}": pdf[pdf.season == TEST_SEASON],
    }
    print(f"{len(pdf)} games, seasons {pdf.season.min()}-{pdf.season.max()}, "
          f"train through {TRAIN_END_SEASON}\n")
    print(f"{'configuration':38s} {'split':11s} {'n':>5s} {'brier':>8s} {'logloss':>9s} "
          f"{'acc':>7s} {'auc':>7s}")
    print("-" * 89)

    configs = {"FEATURE_COLS (current)": list(FEATURE_COLS)}
    for name, cols in variants.items():
        swapped = [c for c in FEATURE_COLS if not any(c == v.split("_prior")[0].split("_fbs")[0]
                                                      for v in cols)]
        configs[name] = swapped + cols

    model_aucs = {}
    for label, features in configs.items():
        pipe = build_pipeline(features)
        pipe.fit(train[features], train["label"])
        for split_name, split in holdouts.items():
            if split.empty:
                continue
            s = score(split["label"].values, pipe.predict_proba(split[features])[:, 1])
            print(row(label, split_name, s))
            if label == "FEATURE_COLS (current)":
                model_aucs[split_name] = s["auc"]

    print("-" * 89)
    market_aucs = {}
    for split_name, split in holdouts.items():
        if split.empty:
            continue
        y, p = market_probs(split)
        s = score(y, p)
        print(row("MARKET (de-vigged moneyline)", split_name, s))
        market_aucs[split_name] = s["auc"]

    warned = False
    for split_name, auc in model_aucs.items():
        gap = auc - market_aucs.get(split_name, 0)
        if gap > SUSPICIOUS_AUC_GAP:
            warned = True
            print(f"\nWARNING {split_name}: model AUC exceeds the market's by {gap:.3f}. "
                  f"Suspect leakage before believing it.")
    if not warned:
        print("\nNo model is implausibly ahead of the market.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
