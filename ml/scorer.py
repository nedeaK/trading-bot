"""ML signal confidence scorer.

Wraps a scikit-learn classifier that predicts win probability (0–100).
Falls back to a neutral score (50) when no trained model exists yet —
the model is only useful after it has been trained on labeled historical signals.

Usage:
    scorer = SignalScorer()
    score = scorer.score(signal, context, ltf_candles, ...)
    # → float 0-100

    # Train after collecting trade outcomes:
    scorer.train(feature_rows, labels)  # labels: 1=win, 0=loss
    scorer.save("models/signal_scorer.pkl")
"""

import logging
import os
import pickle
from typing import List, Optional

from data.models import Candle, MarketContext, Signal
from ml.features import extract_features

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "signal_scorer.pkl"
)


class SignalScorer:
    """Scores a signal 0–100 based on learned historical patterns."""

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path or DEFAULT_MODEL_PATH
        self._model = None
        self._load_if_exists()

    # ── Public API ────────────────────────────────────────────────────────────

    def score(
        self,
        signal: Signal,
        context: MarketContext,
        ltf_candles: List[Candle],
        pool_strength: int = 2,
        sweep_depth_pct: float = 0.1,
        zone_age_bars: int = 5,
    ) -> float:
        """Return a 0–100 confidence score.

        Returns 50.0 (neutral) if no model is trained yet.
        """
        if self._model is None:
            return 50.0
        features = extract_features(
            signal, context, ltf_candles,
            pool_strength, sweep_depth_pct, zone_age_bars,
        )
        try:
            prob = self._model.predict_proba([features])[0][1]
            return round(prob * 100, 1)
        except Exception as exc:
            logger.warning("ML scorer prediction failed: %s", exc)
            return 50.0

    def train(self, feature_rows: List[List[float]], labels: List[int]) -> dict:
        """Train a Random Forest classifier on labeled historical data.

        Args:
            feature_rows: List of feature vectors from extract_features().
            labels: Binary outcomes — 1 = trade won (hit TP), 0 = trade lost (hit SL).

        Returns:
            Dict with training accuracy and cross-val score.
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("scikit-learn not installed: pip install scikit-learn") from exc

        if len(feature_rows) < 30:
            raise ValueError(
                f"Need at least 30 labeled samples to train; got {len(feature_rows)}. "
                "Keep accumulating trades via the trade journal."
            )

        X = np.array(feature_rows)
        y = np.array(labels)

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
        )
        model.fit(X, y)

        cv_scores = cross_val_score(model, X, y, cv=min(5, len(y) // 10), scoring="roc_auc")
        train_acc = model.score(X, y)

        self._model = model
        result = {
            "n_samples": len(y),
            "n_wins": int(y.sum()),
            "win_rate": float(y.mean()),
            "train_accuracy": round(train_acc, 4),
            "cv_roc_auc": round(float(cv_scores.mean()), 4),
            "cv_roc_auc_std": round(float(cv_scores.std()), 4),
        }
        logger.info("ML model trained: %s", result)
        return result

    def save(self, path: Optional[str] = None) -> str:
        """Persist the trained model to disk."""
        save_path = path or self._model_path
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(self._model, f)
        logger.info("ML model saved to %s", save_path)
        return save_path

    def feature_importances(self) -> Optional[List[tuple]]:
        """Return feature name → importance pairs, sorted descending."""
        if self._model is None:
            return None
        try:
            from ml.features import FEATURE_NAMES
            importances = self._model.feature_importances_
            pairs = sorted(
                zip(FEATURE_NAMES, importances),
                key=lambda x: x[1],
                reverse=True,
            )
            return [(name, round(imp, 4)) for name, imp in pairs]
        except Exception:
            return None

    # ── Private ───────────────────────────────────────────────────────────────

    def _load_if_exists(self) -> None:
        if os.path.exists(self._model_path):
            try:
                with open(self._model_path, "rb") as f:
                    self._model = pickle.load(f)
                logger.info("ML model loaded from %s", self._model_path)
            except Exception as exc:
                logger.warning("Failed to load ML model: %s", exc)
