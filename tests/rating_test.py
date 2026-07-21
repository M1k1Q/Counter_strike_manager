import os
import sys
import unittest
import pandas as pd

# Allow running from repo root or from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.rating import (
    ROLE_WEIGHTS,
    FALLBACK_WEIGHTS,
    W_ROLE,
    W_HLTV,
    W_RANKING,
    HLTV_MIN,
    HLTV_MAX,
    _normalise_impact,
    _normalise_hltv,
    _ranking_adjustment,
    _post_scale,
    _role_score,
    calculate_rating,
    main,
)

class RatingCalculationTests(unittest.TestCase):
    def test_calculate_rating_return_type(self):
        sample_row = pd.Series({
            "role": "awper",
            "is_igl": False,
            "Overall Rating": 1.15,
            "Sniping": 90.0,
            "Clutching": 70.0,
            "Opening": 60.0,
            "Firepower": 75.0,
            "Impact": 1.20,
        })
        rating = calculate_rating(sample_row, team_rank=1, max_rank=20)
        self.assertIsInstance(rating, int)
        self.assertGreaterEqual(rating, 65)
        self.assertLessEqual(rating, 96)

    def test_normalise_impact(self):
        self.assertEqual(_normalise_impact(pd.NA), 50.0)
        self.assertEqual(_normalise_impact(0.50), 0.0)
        self.assertEqual(_normalise_impact(1.70), 100.0)

    def test_post_scale_bounds(self):
        self.assertEqual(_post_scale(0.0), 65)
        self.assertEqual(_post_scale(100.0), 96)


if __name__ == "__main__":
    main()