import csv
import os
import time
import random
import re
import tempfile
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth

# Base URL configurations
BASE_URL = "https://www.hltv.org"
PLAYER_STATS_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app",
    "hltv_team_player_stats_2026.csv",
)
# Target the top teams list instead of the player leaderboard
TEAMS_LIST_URL = "https://www.hltv.org/stats/teams?startDate=2026-06-01&endDate=2026-12-31&matchType=Lan&rankingFilter=Top75"

def init_stealth_driver():
    """Initializes a standard Selenium Chrome instance hardened against bot detection."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)

    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver

def get_soup_via_selenium(driver, url, is_verification_page=False, verification_selector=None):
    """Loads a page, checks for structural blocks/Captchas, and returns a BeautifulSoup object."""
    try:
        driver.get(url)
        time.sleep(random.uniform(4.0, 5.5))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Guard rails for automated bot check screens
        if is_verification_page and verification_selector:
            target_element = soup.select_one(verification_selector)
            if not target_element:
                print(f"\n[!] Cloudflare Captcha detected or target page elements haven't loaded.")
                print("[!] PLEASE GO TO THE OPEN BROWSER WINDOW AND SOLVE THE CAPTCHA MANUALLY.")
                input("[-->] After the requested page appears fully on screen, come back here and press ENTER to continue...")
                
                # Re-cook the soup after the user clears the gate
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
        return soup
    except Exception as e:
        print(f"Error accessing {url}: {e}")
        return None

def parse_teams_list(driver):
    """Scrapes the primary top teams table."""
    print("Opening HLTV Top Teams List with Selenium...")
    soup = get_soup_via_selenium(
        driver, 
        TEAMS_LIST_URL, 
        is_verification_page=True, 
        verification_selector='table.stats-table'
    )
    if not soup:
        return []

    teams_data = []
    table = soup.find('table', class_='stats-table')
    
    if not table:
        print("Process terminated: Still could not locate the teams table.")
        return []

    tbody = table.find('tbody')
    if not tbody:
        return []

    rows = tbody.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
            
        team_link_tag = cols[0].find('a')
        if team_link_tag:
            team_name = team_link_tag.text.strip()
            team_href = team_link_tag['href']
            
            teams_data.append({
                'Team': team_name,
                'Team Link': BASE_URL + team_href
            })
            
    return teams_data

def parse_team_lineup(driver, team_url):
    """Navigates to a team's overview page and extracts all players in the active lineup grid."""
    soup = get_soup_via_selenium(driver, team_url, is_verification_page=False)
    if not soup:
        return []

    def extract_players(page_soup):
        players = []
        seen_links = set()
        for link in page_soup.select(
            'div.grid a[href*="/player/"], div.grid a[href*="/stats/players/"]'
        ):
            href = link.get("href", "")
            match = re.match(
                r"^/(?:stats/players|player)/(\d+)/([^/?#]+)",
                href,
            )
            if not match:
                continue

            player_id, player_slug = match.groups()
            if player_id in seen_links:
                continue
            seen_links.add(player_id)

            if href.startswith("/player/"):
                href = href.replace("/player/", "/stats/players/", 1)

            player_name = link.get_text(" ", strip=True)
            if player_name.casefold() in {"bench", "coach", "substitute"}:
                player_name = ""
            if not player_name:
                player_name = player_slug.replace("-", " ")
            players.append({
                "Player": player_name.split("\n")[0].strip(),
                "Profile Link": BASE_URL + href,
            })
            if len(players) == 5:
                break
        return players

    profile_buttons = driver.find_elements(
        By.XPATH,
        "//button[normalize-space(.)='Team profile']"
        " | //a[normalize-space(.)='Team profile']"
        " | //*[@role='button'][normalize-space(.)='Team profile']",
    )
    if profile_buttons:
        profile_buttons[0].click()
        time.sleep(0.5)
        profile_soup = BeautifulSoup(driver.page_source, "html.parser")
        profile_players = extract_players(profile_soup)
        if profile_players:
            return profile_players

    return extract_players(soup)

def _extract_metrics_from_soup(soup):
    metrics = {}
    # 1. Extract Overall Rating 3.0 / Rating
    rating_tag = soup.select_one('div.player-summary-stat-box-rating-data-text')
    if rating_tag:
        metrics['Rating'] = rating_tag.get_text(strip=True)

    # 2. Extract Side Ratings (T Rating & CT Rating)
    ratings = soup.find_all("div", class_="player-summary-stat-box-side-rating-background-wrapper")
    if len(ratings) >= 2:
        t_raw  = ratings[0].get_text(strip=True)
        ct_raw = ratings[1].get_text(strip=True)
        metrics["T Rating"]  = re.match(r"[\d.]+", t_raw).group()  if re.match(r"[\d.]+", t_raw)  else t_raw
        metrics["CT Rating"] = re.match(r"[\d.]+", ct_raw).group() if re.match(r"[\d.]+", ct_raw) else ct_raw
    
    # 3. Extract Role / Attribute Section Scores
    sections = soup.find_all("div", class_="role-stats-section")
    for section in sections:
        title_div = section.find("div", class_="role-stats-section-title")
        score_div = section.find("div", class_="row-stats-section-score")

        if title_div and score_div:
            title_texts = [t.strip() for t in title_div.find_all(string=True, recursive=False) if t.strip()]
            title = title_texts[0] if title_texts else ""
            score = score_div.contents[0].get_text(strip=True)
            metrics[title] = score

    # 4. Extract Impact Metric
    impact_tag = (
        soup.select_one('div.player-summary-stat-box-rating-data-text--impact') or
        soup.select_one('[class*="impact"]') or
        soup.select_one('span.strong')
    )
    if impact_tag:
        metrics['Impact'] = impact_tag.get_text(strip=True)

    # 5. Extract Age
    age_tag = soup.select_one('div.player-summary-stat-box-left-player-age')
    if age_tag:
        age_text = age_tag.get_text(strip=True)
        age_match = re.search(r'\d+', age_text)
        if age_match:
            metrics['Age'] = age_match.group()

    return metrics


def parse_individual_profile(driver, player_url):
    """Navigates to individual player profile and parses the metric grids.
    If filtered stats are missing, falls back to full-year 2026 stats.
    """
    soup = get_soup_via_selenium(driver, player_url, is_verification_page=False)
    profile_metrics = {}
    if soup:
        profile_metrics = _extract_metrics_from_soup(soup)

    # Fallback: if 'Rating' or role attributes are missing, broaden to full-year 2026 stats
    if not profile_metrics.get('Rating'):
        base_player_url = player_url.split('?')[0]
        fallback_url = f"{base_player_url}?startDate=2026-01-01&endDate=2026-12-31"
        print(f"      [Fallback] No stats under filter, retrying full-year 2026: {fallback_url}")
        time.sleep(random.uniform(1.0, 2.0))
        fallback_soup = get_soup_via_selenium(driver, fallback_url, is_verification_page=False)
        if fallback_soup:
            fallback_metrics = _extract_metrics_from_soup(fallback_soup)
            if fallback_metrics:
                # Keep age if already found, else take fallback
                if 'Age' in profile_metrics and 'Age' not in fallback_metrics:
                    fallback_metrics['Age'] = profile_metrics['Age']
                profile_metrics = fallback_metrics

    return profile_metrics


def load_existing_player_data(csv_path):
    if not os.path.isfile(csv_path):
        return [], [], set()

    with open(csv_path, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "Team" not in reader.fieldnames:
            raise ValueError(f"CSV must contain a Team column: {csv_path}")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    teams = {
        (row.get("Team") or "").strip().casefold()
        for row in rows
        if (row.get("Team") or "").strip()
    }
    return fieldnames, rows, teams


def get_unprocessed_teams(teams, existing_teams):
    return [
        team
        for team in teams
        if team["Team"].strip().casefold() not in existing_teams
    ]


def save_player_data(csv_path, fieldnames, rows):
    ordered_fields = ["Team", "Player", "Profile Link", "Team Link"]
    output_fields = list(fieldnames)
    if not output_fields:
        output_fields = ordered_fields
    else:
        output_fields.extend(
            field for field in ordered_fields if field not in output_fields
        )

    extra_fields = sorted({
        field
        for row in rows
        for field in row
        if field not in output_fields
    })
    output_fields.extend(extra_fields)

    csv_directory = os.path.dirname(os.path.abspath(csv_path))
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=csv_directory,
        delete=False,
    ) as output:
        temp_path = output.name
        writer = csv.DictWriter(output, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)

    try:
        os.replace(temp_path, csv_path)
    except OSError:
        os.unlink(temp_path)
        raise
    
def main():
    print("Starting the team-by-team player scraper...")
    existing_fieldnames, existing_rows, existing_teams = load_existing_player_data(
        PLAYER_STATS_CSV
    )
    print("Initializing the browser... This may take a moment.")
    driver = init_stealth_driver()
    try:
        # Step 1: Track down the Top Teams
        top_teams = parse_teams_list(driver)
        if not top_teams:
            print("Process terminated: Teams list parsing failed.")
            return

        print(f"\nDiscovered {len(top_teams)} teams. Processing rosters layout context...")
        teams_to_scrape = get_unprocessed_teams(top_teams, existing_teams)
        skipped_count = len(top_teams) - len(teams_to_scrape)
        if skipped_count:
            print(f"Skipping {skipped_count} teams already present in the CSV.")
        if not teams_to_scrape:
            print("All listed teams are already present in the CSV.")
            return

        # Step 2: Loop over discovered Teams to extract Lineups
        for t_idx, team in enumerate(teams_to_scrape, 1):
            print(f"\n[{t_idx}/{len(teams_to_scrape)}] Extracting lineup for team: {team['Team']}")
            
            lineup_players = parse_team_lineup(driver, team['Team Link'])
            print(f"-> Found {len(lineup_players)} players in active lineup.")
            
            time.sleep(random.uniform(1.5, 3.0))
            team_rows = []
            
            # Step 3: Loop over each player inside the lineup for individual deep stats
            for p_idx, player in enumerate(lineup_players):
                print(f"   ({p_idx+1}/{len(lineup_players)}) Extracting profile metrics for: {player['Player']}")
                
                advanced_metrics = parse_individual_profile(driver, player['Profile Link'])
                
                # Merge team tracking details, player profile link, and metrics together
                merged_data = {
                    'Team': team['Team'],
                    'Team Link': team['Team Link'],
                    'Player': player['Player'],
                    'Profile Link': player['Profile Link'],
                    **advanced_metrics
                }
                team_rows.append(merged_data)
                
                # Gentle delay to safeguard runtime sessions from rate limits
                time.sleep(random.uniform(1.5, 3.0))

            if team_rows:
                existing_rows.extend(team_rows)
                save_player_data(PLAYER_STATS_CSV, existing_fieldnames, existing_rows)
                existing_teams.add(team["Team"].strip().casefold())
                print(
                    f"Saved {len(team_rows)} players for {team['Team']} to "
                    f"'{PLAYER_STATS_CSV}'."
                )

        print(f"\nUpdated team-focused roster dataset saved to '{PLAYER_STATS_CSV}'.")

    finally:
        print("Tearing down Selenium Chrome session.")
        driver.quit()

if __name__ == "__main__":
    main()