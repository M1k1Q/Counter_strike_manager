import csv
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from bs4 import BeautifulSoup

from app.rating import _team_rank_map
from scrapers import team_scraper
from scrapers import team_ranking_scraper


class TeamScraperTests(unittest.TestCase):
    def test_extracts_global_rank_from_world_ranking_stat(self):
        soup = BeautifulSoup(
            """
            <div class="profile-team-stat">
                <b>Valve ranking</b>
                <span class="right"><a href="/ranking/teams/valve">#1</a></span>
            </div>
            <div class="profile-team-stat">
                <b>World ranking</b>
                <span class="right">
                    <a href="/ranking/teams/country/Europe">#1</a>
                    <a href="/ranking/teams/2026/october/12/details/9565">#2</a>
                </span>
            </div>
            """,
            "html.parser",
        )

        self.assertEqual(team_ranking_scraper.parse_world_ranking(soup), 2)

    def test_team_rank_map_uses_scraped_rank_and_keeps_missing_unranked(self):
        df = pd.DataFrame({
            "Team": ["Vitality", "Spirit", "Unranked", "Vitality"],
            "Team_Rank": ["2", "5", "", "2"],
        })

        self.assertEqual(_team_rank_map(df), {"Vitality": 2, "Spirit": 5})

    def test_team_rank_map_falls_back_for_legacy_csv(self):
        df = pd.DataFrame({"Team": ["Vitality", "Spirit", "Vitality"]})

        self.assertEqual(_team_rank_map(df), {"Vitality": 1, "Spirit": 2})

    def test_rank_scraper_opens_profile_panel_to_read_world_rank(self):
        profile_html = """
            <div class="profile-team-stat">
                <b>World ranking</b>
                <span class="right">
                    <a href="/ranking/teams/2026/october/12/details/9565">#2</a>
                </span>
            </div>
            <div class="grid">
                <a href="/stats/players/1/player-one">Player One</a>
            </div>
        """

        class ProfileButton:
            clicked = False

            def click(self):
                self.clicked = True

        class Driver:
            page_source = profile_html

            def __init__(self):
                self.profile_button = ProfileButton()

            def find_elements(self, by, selector):
                return [self.profile_button]

        driver = Driver()
        with (
            patch.object(
                team_ranking_scraper,
                "get_soup_via_selenium",
                return_value=BeautifulSoup("<html></html>", "html.parser"),
            ),
            patch.object(team_ranking_scraper.time, "sleep"),
        ):
            team_rank = team_ranking_scraper.scrape_team_world_ranking(
                driver, "https://example.com/team"
            )

        self.assertTrue(driver.profile_button.clicked)
        self.assertEqual(team_rank, 2)

    def test_lineup_keeps_stats_player_links_for_filtered_stats_page(self):
        soup = BeautifulSoup(
            """
            <div class="grid">
                <a href="/stats/players/11893/apex?startDate=2026-06-01&amp;endDate=2026-12-31">apEX</a>
                <a href="/stats/players/11894/ropz?startDate=2026-06-01&amp;endDate=2026-12-31">ropz</a>
            </div>
            """,
            "html.parser",
        )
        driver = object()

        with patch.object(team_scraper, "get_soup_via_selenium", return_value=soup):
            players = team_scraper.parse_team_lineup(driver, "https://example.com/team")

        self.assertEqual(
            [player["Player"] for player in players],
            ["apEX", "ropz"],
        )
        self.assertTrue(all("/stats/players/" in player["Profile Link"] for player in players))
        self.assertIn("startDate=2026-06-01", players[0]["Profile Link"])

    def test_rank_scraper_updates_team_rank_in_player_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = os.path.join(directory, "players.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["Team", "Player"])
                writer.writeheader()
                writer.writerows([
                    {"Team": "Vitality", "Player": "ZywOo"},
                    {"Team": "Spirit", "Player": "donk"},
                    {"Team": "", "Player": "Free Agent"},
                ])

            matched = team_ranking_scraper.update_player_csv_with_ranks(
                csv_path, {"VITALITY": 2, "Spirit": 5}
            )

            with open(csv_path, newline="", encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(matched, {"vitality", "spirit"})
        self.assertEqual([row["Team_Rank"] for row in rows], ["2", "5", ""])


if __name__ == "__main__":
    unittest.main()
