"""ML training pipeline.

Reads labeled trade records from the trade journal and trains (or retrains)
the signal scorer. Run this script directly to retrain:

    python -m ml.trainer [--journal path/to/trades.jsonl] [--model output/model.pkl]
"""

import argparse
import json
import logging
import os
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_labeled_trades(journal_path: str) -> Tuple[List[List[float]], List[int]]:
    """Read trade journal and return (feature_rows, labels).

    Only includes trades that have been resolved (outcome recorded).
    """
    if not os.path.exists(journal_path):
        raise FileNotFoundError(f"Trade journal not found: {journal_path}")

    features: List[List[float]] = []
    labels: List[int] = []
    skipped = 0

    with open(journal_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record: Dict = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: JSON parse error — %s", line_no, exc)
                skipped += 1
                continue

            outcome = record.get("outcome")
            if outcome not in ("WIN", "LOSS"):
                skipped += 1
                continue

            feat = record.get("features")
            if not feat or not isinstance(feat, list):
                skipped += 1
                continue

            features.append([float(v) for v in feat])
            labels.append(1 if outcome == "WIN" else 0)

    logger.info(
        "Loaded %d labeled trades (%d wins, %d losses). Skipped %d records.",
        len(labels),
        sum(labels),
        len(labels) - sum(labels),
        skipped,
    )
    return features, labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SMC signal scorer")
    parser.add_argument(
        "--journal",
        default=os.path.join("memory", "trades.jsonl"),
        help="Path to JSONL trade journal",
    )
    parser.add_argument(
        "--model",
        default=os.path.join("models", "signal_scorer.pkl"),
        help="Output path for trained model",
    )
    args = parser.parse_args()

    features, labels = load_labeled_trades(args.journal)

    from ml.scorer import SignalScorer
    scorer = SignalScorer(model_path=args.model)
    results = scorer.train(features, labels)

    print("\n── Training Results ─────────────────────────────────")
    for k, v in results.items():
        print(f"  {k:<25}: {v}")

    scorer.save(args.model)
    print(f"\nModel saved → {args.model}")

    importances = scorer.feature_importances()
    if importances:
        print("\n── Top 10 Feature Importances ───────────────────────")
        for name, imp in importances[:10]:
            bar = "█" * int(imp * 40)
            print(f"  {name:<30} {imp:.4f}  {bar}")


if __name__ == "__main__":
    main()
