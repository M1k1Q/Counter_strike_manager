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
LEADERBOARD_URL = "https://www.hltv.org/stats/players?csVersion=CS2&startDate=2026-01-01&endDate=2026-12-31&matchType=AllMatches&rankingFilter=Top20"

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

def get_soup_via_selenium(driver, url, is_leaderboard=False):
    """Loads a page, checks for Captcha blocks, and returns a BeautifulSoup object."""
    try:
        driver.get(url)
        time.sleep(random.uniform(4.0, 5.5))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # If it's the leaderboard page, check if the main stats table exists
        if is_leaderboard:
            table = soup.find('table', class_='stats-table player-ratings-table')
            if not table:
                print("\n[!] Cloudflare Captcha detected or table hasn't loaded.")
                print("[!] PLEASE GO TO THE OPEN BROWSER WINDOW AND SOLVE THE CAPTCHA MANUALLY.")
                input("[-->] After the leaderboard table appears on screen, come back here and press ENTER to continue...")
                
                # Re-cook the soup after the user clears the gate
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
        return soup
    except Exception as e:
        print(f"Error accessing {url}: {e}")
        return None

def parse_leaderboard(driver):
    """Scrapes the primary table tracking the leaderboard stats."""
    print("Opening HLTV Leaderboard with Selenium...")
    # Pass True to activate the manual Captcha handler if triggered
    soup = get_soup_via_selenium(driver, LEADERBOARD_URL, is_leaderboard=True)
    if not soup:
        return []

    players_data = []
    table = soup.find('table', class_='stats-table player-ratings-table')
    
    if not table:
        print("Process terminated: Still could not locate the table after manual intervention.")
        return []

    tbody = table.find('tbody')
    if not tbody:
        return []

    rows = tbody.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 7:
            continue
            
        player_link_tag = cols[0].find('a')
        if player_link_tag:
            player_name = player_link_tag.text.strip()
            player_href = player_link_tag['href']
            
            players_data.append({
                'Player': player_name,
                'Profile Link': BASE_URL + player_href,
                'Maps': cols[2].text.strip(),
                'Rounds': cols[3].text.strip(),
                'K-D Diff': cols[4].text.strip(),
                'K/D': cols[5].text.strip(),
                'Rating 3.0': cols[6].text.strip()
            })
            
    return players_data

def parse_individual_profile(driver, player_url):
    """Navigates to individual player profile and parses the metric grids."""
    soup = get_soup_via_selenium(driver, player_url, is_leaderboard=False)
    profile_metrics = {}
    if not soup:
        return profile_metrics
    
    ratings = soup.find_all("div",class_="player-summary-stat-box-side-rating-background-wrapper")
    
    if len(ratings) >= 2:
        # On the page T Rating appears first (index 0), CT Rating second (index 1)
        t_raw  = ratings[0].get_text(strip=True)
        ct_raw = ratings[1].get_text(strip=True)
        # Keep only the leading decimal number, e.g. "1.24CT rating" -> "1.24"
        profile_metrics["T Rating"]  = re.match(r"[\d.]+", t_raw).group()  if re.match(r"[\d.]+", t_raw)  else t_raw
        profile_metrics["CT Rating"] = re.match(r"[\d.]+", ct_raw).group() if re.match(r"[\d.]+", ct_raw) else ct_raw
    
    sections = soup.find_all("div", class_="role-stats-section")

    for section in sections:
        title_div = section.find("div", class_="role-stats-section-title")
        score_div = section.find("div", class_="row-stats-section-score")

        if title_div and score_div:
           print("test for title and score div")
           title_texts = [t.strip() for t in title_div.find_all(string=True, recursive=False) if t.strip()]
           title = title_texts[0] if title_texts else ""
           score = score_div.contents[0].get_text(strip=True)
           print(repr(title), score)
           profile_metrics[title] = score

    # Try the specific HLTV impact class first, fall back to any span containing 'strong'
    impact_tag = (
        soup.select_one('div.player-summary-stat-box-rating-data-text--impact') or
        soup.select_one('[class*="impact"]') or
        soup.select_one('span.strong')
    )
    if impact_tag:
        print("Impact found:", impact_tag.get('class'), impact_tag.get_text(strip=True))
        profile_metrics['Impact'] = impact_tag.get_text(strip=True)
    else:
        print("Impact NOT found for this profile")

    print(profile_metrics)
    return profile_metrics

def main():
    print("Starting the scraper...")
    print("Initializing the browser... This may take a moment.")
    driver = init_stealth_driver()
    try:
        # Step 1: Track down player links
        leaderboard_players = parse_leaderboard(driver)
        if not leaderboard_players:
            print("Process terminated: Leaderboard parsing failed.")
            return

        print(f"\nDiscovered {len(leaderboard_players)} players. Compiling deep statistics profiles...")
        complete_dataset = []

        # Step 2: Loop over discovered links to scrape deep content profiles
        for idx, player in enumerate(leaderboard_players):
            print(f"[{idx+1}/{len(leaderboard_players)}] Extracting profiles for: {player['Player']}")
            
            advanced_metrics = parse_individual_profile(driver, player['Profile Link'])
            merged_data = {**player, **advanced_metrics}
            complete_dataset.append(merged_data)
            
            # Gentle delay to prevent secondary verification walls mid-run
            time.sleep(random.uniform(1.5, 3.0))

        # Step 3: Write out final structured CSV file
        if complete_dataset:
            fieldnames = set()
            for item in complete_dataset:
                fieldnames.update(item.keys())
            
            ordered_fields = ['Player', 'Maps', 'Rounds', 'K-D Diff', 'K/D', 'Rating 3.0', 'Profile Link']
            extra_fields = sorted(list(fieldnames - set(ordered_fields)))
            final_fields = ordered_fields + extra_fields

            with open('hltv_player_stats_2026.csv', mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=final_fields)
                writer.writeheader()
                for row in complete_dataset:
                    writer.writerow(row)
                    
            print("\nSuccess! Dataset cleanly saved to 'hltv_player_stats_2026.csv'")

    finally:
        print("Tearing down Selenium Chrome session.")
        driver.quit()

if __name__ == "__main__":
    main()