import os
import unittest

from app import seed_db


class SeedDatabaseCompatibilityTests(unittest.TestCase):
    def test_classifier_and_rating_helpers_exist(self):
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "hltv_team_player_stats_2026.csv")
        df = seed_db.load_and_classify(csv_path)

        self.assertIn("role", df.columns)
        self.assertIn("confidence", df.columns)
        self.assertIn("igl_score", df.columns)
        self.assertIn("is_igl", df.columns)

        row = df.iloc[0]
        rating = seed_db.calculate_rating(row, 1)
        self.assertIsInstance(rating, (int, float))


if __name__ == "__main__":
    unittest.main()
