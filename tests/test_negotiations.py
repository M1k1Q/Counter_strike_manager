import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import models

class NegotiationModelTests(unittest.TestCase):
    def test_top_team_star_is_untouchable_at_base_price(self):
        source_team = models.Team(name="Vitality", ranking=1)
        target_team = models.Team(name="Custom Esports", ranking=99)
        player = models.Player(player="ZywOo", Rating=94, overall_rating=1.38)
        manager = models.Manager(name="Boss", budget=2000000)

        # Price approximation based on property calculation
        base_price = player.price
        
        negotiation = models.Negotiation(
            player=player,
            source_team=source_team,
            target_team=target_team,
            manager=manager,
            offer_amount=base_price, # 1.0x offer
        )

        self.assertTrue(negotiation.is_untouchable)
        chance = negotiation.calculate_success()
        self.assertEqual(chance, 0.0)
        self.assertIn("untouchable", negotiation.status_explanation.lower())

    def test_top_team_star_negotiation_with_high_multiplier(self):
        source_team = models.Team(name="Vitality", ranking=1)
        target_team = models.Team(name="Custom Esports", ranking=99)
        player = models.Player(player="ZywOo", Rating=94, overall_rating=1.38)
        manager = models.Manager(name="Boss", budget=10000000)

        base_price = player.price
        
        negotiation = models.Negotiation(
            player=player,
            source_team=source_team,
            target_team=target_team,
            manager=manager,
            offer_amount=int(base_price * 4.2),
        )

        self.assertFalse(negotiation.is_untouchable)
        chance = negotiation.calculate_success()
        self.assertGreater(chance, 0.0)

    def test_elite_star_is_protected_even_on_a_low_ranked_team(self):
        source_team = models.Team(name="Luminosity", ranking=24)
        target_team = models.Team(name="Custom Esports", ranking=99)
        player = models.Player(player="donk", Rating=94, overall_rating=1.38)
        manager = models.Manager(name="Boss", budget=10000000)
        base_price = player.price

        negotiation = models.Negotiation(
            player=player,
            source_team=source_team,
            target_team=target_team,
            manager=manager,
            offer_amount=int(base_price * 3.9),
        )

        self.assertTrue(negotiation.is_untouchable)
        self.assertEqual(negotiation.calculate_success(), 0.0)

    def test_mid_tier_team_acceptable_offer(self):
        source_team = models.Team(name="3DMAX", ranking=16)
        target_team = models.Team(name="FaZe", ranking=2)
        player = models.Player(player="misutaaa", Rating=83, overall_rating=1.09)
        manager = models.Manager(name="Boss", budget=2000000)

        base_price = player.price
        
        negotiation = models.Negotiation(
            player=player,
            source_team=source_team,
            target_team=target_team,
            manager=manager,
            offer_amount=int(base_price * 1.5),
        )

        self.assertFalse(negotiation.is_untouchable)
        chance = negotiation.calculate_success()
        self.assertGreaterEqual(chance, 50.0)


if __name__ == "__main__":
    unittest.main()
