import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from scrapers import scraping_neityu


class ScrapingNeityParserTests(unittest.TestCase):
    def test_missing_overall_rating_does_not_crash(self):
        soup = BeautifulSoup(
            """
            <html><body>
                <div class="role-stats-section">
                    <div class="role-stats-section-title">Entry</div>
                    <div class="row-stats-section-score">9.9</div>
                </div>
            </body></html>
            """,
            "html.parser",
        )

        with patch("scrapers.scraping_neityu.get_soup_via_selenium", return_value=soup):
            metrics = scraping_neityu.parse_individual_profile(object(), "https://example.com")

        self.assertEqual(metrics["Entry"], "9.9")



if __name__ == "__main__":
    unittest.main()
