import csv
import re
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# --- Target Data Settings ---
CSV_FILENAME = 'hltv_team_player_stats_2026.csv'
TARGET_PLAYER_NAME = "Neityu"
TARGET_TEAM_NAME = "FaZe"
TARGET_TEAM_LINK = "https://www.hltv.org/stats/teams/6665/faze"
TARGET_PLAYER_LINK = "https://www.hltv.org/stats/players/21972/neityu?startDate=2026-01-01&endDate=2026-12-31&rankingFilter=Top20"

def init_stealth_driver():
    """Initializes a standard Selenium Chrome instance hardened against bot detection."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    
    # Modern Chrome User-Agent string to prevent Cloudflare detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
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

def handle_cloudflare_or_wait(driver, timeout=20):
    """
    Waits for the target HLTV page elements to render while allowing 
    extra time if Cloudflare triggers a interstitial challenge.
    """
    print("-> Waiting for page to load completely...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        title = driver.title.lower()
        # Detect standard Cloudflare challenge page titles
        if "just a moment" in title or "attention required" in title:
            print("   Cloudflare challenge detected. Waiting for auto-solve / user action...")
            time.sleep(2)
            continue
        
        # Check if actual target content has rendered
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "player-summary-stat-box-rating-data-text"))
            )
            print("-> Core metrics rendered successfully.")
            return True
        except Exception:
            # Short fallback sleep before re-checking
            time.sleep(1)

    print("[!] Timed out waiting for target elements or Cloudflare challenge.")
    return False

def get_soup_via_selenium(driver, url):
    """Loads a page with explicit waits and returns a BeautifulSoup object."""
    try:
        driver.get(url)
        
        # Wait until target elements load or Cloudflare clears
        loaded = handle_cloudflare_or_wait(driver, timeout=25)
        if not loaded:
            return None

        # Short human-like micro pause for dynamic JS bindings to settle
        time.sleep(random.uniform(1.0, 2.0))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        return soup
    except Exception as e:
        print(f"[!] Error accessing {url}: {e}")
        return None

def parse_individual_profile(driver, player_url):
    """Navigates to individual player profile and parses the metric grids."""
    soup = get_soup_via_selenium(driver, player_url)
    profile_metrics = {}
    if not soup:
        return profile_metrics

    ovr_rating = soup.find("div", class_="player-summary-stat-box-rating-data-text")
    if ovr_rating:
        profile_metrics["Overall Rating"] = ovr_rating.get_text(strip=True)

    ratings = soup.find_all("div", class_="player-summary-stat-box-side-rating-background-wrapper")

    if len(ratings) >= 2:
        t_raw = ratings[0].get_text(strip=True)
        ct_raw = ratings[1].get_text(strip=True)
        profile_metrics["T Rating"] = re.match(r"[\d.]+", t_raw).group() if re.match(r"[\d.]+", t_raw) else t_raw
        profile_metrics["CT Rating"] = re.match(r"[\d.]+", ct_raw).group() if re.match(r"[\d.]+", ct_raw) else ct_raw

    sections = soup.find_all("div", class_="role-stats-section")

    for section in sections:
        title_div = section.find("div", class_="role-stats-section-title")
        score_div = section.find("div", class_="row-stats-section-score")

        if title_div and score_div:
            title_texts = [t.strip() for t in title_div.find_all(string=True, recursive=False) if t.strip()]
            title = title_texts[0] if title_texts else ""
            score = score_div.get_text(strip=True)
            if title:
                profile_metrics[title] = score

    impact_tag = (
        soup.select_one('div.player-summary-stat-box-rating-data-text--impact')
        or soup.select_one('[class*="impact"]')
        or soup.select_one('span.strong')
    )
    if impact_tag:
        profile_metrics['Impact'] = impact_tag.get_text(strip=True)

    return profile_metrics

def main():
    print(f"Initializing browser to pull metrics for {TARGET_PLAYER_NAME}...")
    driver = init_stealth_driver()
    
    try:
        # Step 1: Scrape player profile using explicit waiting
        advanced_metrics = parse_individual_profile(driver, TARGET_PLAYER_LINK)
        
        if not advanced_metrics:
            print("[!] Could not parse metrics. Page failed to load or timed out.")
            return

        # Step 2: Assemble row data
        new_row = {
            'Team': TARGET_TEAM_NAME,
            'Player': TARGET_PLAYER_NAME,
            'Profile Link': TARGET_PLAYER_LINK,
            'Team Link': TARGET_TEAM_LINK,
            **advanced_metrics
        }
        
        # Step 3: Read current header layout from file
        try:
            with open(CSV_FILENAME, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
        except FileNotFoundError:
            print(f"[!] Target file '{CSV_FILENAME}' not found. Initializing new structure.")
            headers = list(new_row.keys())

        # Ensure any newly scraped headers map properly
        for key in new_row.keys():
            if key not in headers:
                headers.append(key)

        # Step 4: Append to CSV securely
        with open(CSV_FILENAME, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writerow(new_row)
            
        print(f"\n[+] Success! Custom entry for {TARGET_PLAYER_NAME} added under team {TARGET_TEAM_NAME}.")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()