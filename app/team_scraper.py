import csv
import time
import random
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

# Base URL configurations
BASE_URL = "https://www.hltv.org"
# Target the top teams list instead of the player leaderboard
TEAMS_LIST_URL = "https://www.hltv.org/stats/teams?csVersion=CS2&startDate=2026-01-01&endDate=2026-12-31&rankingFilter=Top20"

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
    players = []
    if not soup:
        return players

    # HLTV profiles lineup cards usually reside inside elements with player links
    # We find links pointing to player stats inside the lineup display structure
    player_links = soup.select('div.grid a[href*="/stats/players/"]') or soup.select('a[href*="/stats/players/"]')
    
    seen_links = set()
    for link in player_links:
        href = link.get('href')
        # Skip duplicates (e.g. image link + text link) and clean up the URL path
        if href and href not in seen_links:
            seen_links.add(href)
            
            # Extract player name text safely from container child nodes if present
            player_name = link.text.strip()
            if not player_name:
                # Fallback to finding text inside or reading the name via URL tokens
                name_div = link.find_next('div')
                player_name = name_div.text.strip() if name_div else "Unknown"
            
            # Clean text if it grabbed messy layout strings
            player_name = player_name.split('\n')[0].strip()
            
            players.append({
                'Player': player_name,
                'Profile Link': BASE_URL + href
            })
            
            # We explicitly want the active 5 core members showing on the grid dashboard
            if len(players) == 5:
                break
                
    return players

def parse_individual_profile(driver, player_url):
    """Navigates to individual player profile and parses the metric grids."""
    soup = get_soup_via_selenium(driver, player_url, is_verification_page=False)
    profile_metrics = {}
    if not soup:
        return profile_metrics
    
    # 1. Extract Overall Rating 3.0 / Rating
    rating_tag = soup.select_one('div.player-summary-stat-box-rating-data-text')
    if rating_tag:
        profile_metrics['Rating'] = rating_tag.get_text(strip=True)

    # 2. Extract Side Ratings (T Rating & CT Rating)
    ratings = soup.find_all("div", class_="player-summary-stat-box-side-rating-background-wrapper")
    if len(ratings) >= 2:
        t_raw  = ratings[0].get_text(strip=True)
        ct_raw = ratings[1].get_text(strip=True)
        profile_metrics["T Rating"]  = re.match(r"[\d.]+", t_raw).group()  if re.match(r"[\d.]+", t_raw)  else t_raw
        profile_metrics["CT Rating"] = re.match(r"[\d.]+", ct_raw).group() if re.match(r"[\d.]+", ct_raw) else ct_raw
    
    # 3. Extract Role / Attribute Section Scores
    sections = soup.find_all("div", class_="role-stats-section")
    for section in sections:
        title_div = section.find("div", class_="role-stats-section-title")
        score_div = section.find("div", class_="row-stats-section-score")

        if title_div and score_div:
            title_texts = [t.strip() for t in title_div.find_all(string=True, recursive=False) if t.strip()]
            title = title_texts[0] if title_texts else ""
            score = score_div.contents[0].get_text(strip=True)
            profile_metrics[title] = score

    # 4. Extract Impact Metric
    impact_tag = (
        soup.select_one('div.player-summary-stat-box-rating-data-text--impact') or
        soup.select_one('[class*="impact"]') or
        soup.select_one('span.strong')
    )
    if impact_tag:
        profile_metrics['Impact'] = impact_tag.get_text(strip=True)

    return profile_metrics
    
def main():
    print("Starting the team-by-team player scraper...")
    print("Initializing the browser... This may take a moment.")
    driver = init_stealth_driver()
    try:
        # Step 1: Track down the Top Teams
        top_teams = parse_teams_list(driver)
        if not top_teams:
            print("Process terminated: Teams list parsing failed.")
            return

        print(f"\nDiscovered {len(top_teams)} teams. Processing rosters layout context...")
        complete_dataset = []

        # Step 2: Loop over discovered Teams to extract Lineups
        for t_idx, team in enumerate(top_teams):
            print(f"\n[{t_idx+1}/{len(top_teams)}] Extracting lineup for team: {team['Team']}")
            
            lineup_players = parse_team_lineup(driver, team['Team Link'])
            print(f"-> Found {len(lineup_players)} players in active lineup.")
            
            time.sleep(random.uniform(1.5, 3.0))
            
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
                complete_dataset.append(merged_data)
                
                # Gentle delay to safeguard runtime sessions from rate limits
                time.sleep(random.uniform(1.5, 3.0))

        # Step 4: Output structure generation
        if complete_dataset:
            fieldnames = set()
            for item in complete_dataset:
                fieldnames.update(item.keys())
            
            ordered_fields = ['Team', 'Player', 'Profile Link', 'Team Link']
            extra_fields = sorted(list(fieldnames - set(ordered_fields)))
            final_fields = ordered_fields + extra_fields

            with open('hltv_team_player_stats_2026.csv', mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=final_fields)
                writer.writeheader()
                for row in complete_dataset:
                    writer.writerow(row)
                    
            print("\nSuccess! Final team-focused roster dataset cleanly saved to 'hltv_team_player_stats_2026.csv'")

    finally:
        print("Tearing down Selenium Chrome session.")
        driver.quit()

if __name__ == "__main__":
    main()