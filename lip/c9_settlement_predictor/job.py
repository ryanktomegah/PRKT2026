"""
job.py — Small C9 smoke/evaluation job for staging.
"""
from __future__ import annotations

import json
import os

from lip.c9_settlement_predictor.model import SettlementTimePredictor
from lip.c9_settlement_predictor.synthetic_data import generate_settlement_data


def main() -> None:
    n_samples = int(os.environ.get("LIP_C9_JOB_SAMPLES", "256"))
    predictor = SettlementTimePredictor()
    X, durations, events = generate_settlement_data(n_samples=n_samples, seed=42)
    predictor.fit(X, durations, events)
    prediction = predictor.predict(
        corridor="USD-EUR",
        rejection_class="CLASS_B",
        amount_usd=1_250_000.0,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "model_type": predictor.model_type,
                "using_dynamic": prediction.using_dynamic,
                "predicted_hours": prediction.predicted_hours,
                "dynamic_maturity_hours": prediction.dynamic_maturity_hours,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
