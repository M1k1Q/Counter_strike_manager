import unittest
from unittest.mock import MagicMock
from app import models
from app.routes.roster import analyze_roster, select_IGL

class TestRosterAnalysis(unittest.TestCase):
    def test_empty_team(self):
        team = models.Team(id=1, name="Empty Team")
        team.players = []
        
        db = MagicMock()
        result = analyze_roster(team, db)
        
        roles_count = result["roles_count"]
        
        # Manually calculating missing roles as done in the endpoint
        standard_roles = ["entry", "support", "awper", "lurker", "igl"]
        missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
        
        self.assertIn("entry", missing_roles)
        self.assertIn("awper", missing_roles)
        
    def test_team_with_entry_only(self):
        team = models.Team(id=1, name="One Entry")
        p1 = models.Player(id=1, player="Player1", role="entry", is_igl=False)
        team.players = [p1]
        
        db = MagicMock()
        result = analyze_roster(team, db)
        roles_count = result["roles_count"]
        
        standard_roles = ["entry", "support", "awper", "lurker", "igl"]
        missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
        
        self.assertNotIn("entry", missing_roles)
        self.assertIn("awper", missing_roles)
        
    def test_entry_igl_satisfies_entry(self):
        team = models.Team(id=1, name="Entry IGL")
        p1 = models.Player(id=1, player="Player1", role="entry igl", is_igl=True, igl_score=90)
        team.players = [p1]
        
        db = MagicMock()
        result = analyze_roster(team, db)
        roles_count = result["roles_count"]
        
        standard_roles = ["entry", "support", "awper", "lurker", "igl"]
        missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
        
        self.assertNotIn("entry", missing_roles)
        self.assertNotIn("igl", missing_roles)
        
    def test_multiple_supports_and_lurkers(self):
        team = models.Team(id=1, name="Many Supports")
        team.players = [
            models.Player(id=1, player="P1", role="support", is_igl=False),
            models.Player(id=2, player="P2", role="support", is_igl=False),
            models.Player(id=3, player="P3", role="lurker", is_igl=False),
            models.Player(id=4, player="P4", role="lurker", is_igl=False),
        ]
        
        db = MagicMock()
        result = analyze_roster(team, db)
        roles_count = result["roles_count"]
        
        self.assertEqual(roles_count["support"], 2)
        self.assertEqual(roles_count["lurker"], 2)
        
        standard_roles = ["entry", "support", "awper", "lurker", "igl"]
        missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
        
        self.assertNotIn("support", missing_roles)
        self.assertNotIn("lurker", missing_roles)
        self.assertIn("entry", missing_roles)
        self.assertIn("awper", missing_roles)
        
    def test_highest_igl_score_wins(self):
        team = models.Team(id=1, name="Test IGL")
        p1 = models.Player(id=1, player="P1", role="entry", igl_score=50, is_igl=False)
        p2 = models.Player(id=2, player="P2", role="support", igl_score=85, is_igl=False)
        p3 = models.Player(id=3, player="P3", role="awper", igl_score=85, is_igl=False) # Tie
        team.players = [p1, p2, p3]
        
        db = MagicMock()
        best_igl = select_IGL(team, db)
        
        self.assertIsNotNone(best_igl)
        # Should deterministically pick p2 or p3. Our implementation just uses > so it picks the first one it sees (p2).
        self.assertEqual(best_igl.id, 2)
        self.assertTrue(best_igl.is_igl)
        self.assertIn("igl", best_igl.role)
        
    def test_no_role_player(self):
        team = models.Team(id=1, name="No Role Team")
        team.players = [models.Player(id=1, player="P1", role=None, is_igl=False)]
        
        db = MagicMock()
        result = analyze_roster(team, db)
        roles_count = result["roles_count"]
        
        standard_roles = ["entry", "support", "awper", "lurker", "igl"]
        missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
        
        self.assertEqual(roles_count["unknown"], 1)
        self.assertIn("entry", missing_roles)
        self.assertIn("awper", missing_roles)

if __name__ == "__main__":
    unittest.main()
