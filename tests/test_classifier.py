import os
import sys
import pandas as pd

# Allow importing from current directory or app module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.classifier import load_and_classify


def print_separator(title: str, width: int = 120, char: str = "="):
    print("\n" + char * width)
    print(f"  {title.upper()}")
    print(char * width)


def main():
    # Path to dataset
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "..", "app", "hltv_team_player_stats_2026.csv")
    csv_path = os.path.abspath(csv_path)

    print(f"🔍 Loading dataset from: {csv_path}\n")

    try:
        df = load_and_classify(csv_path)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return

    # Pandas display configuration for crisp CLI output
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 25)

    display_cols = [
        "Team", "Player", "role", "confidence", "igl_score", "is_igl",
        "Utility", "Entrying", "Opening", "Firepower", "Sniping"
    ]
    # Filter only available columns
    display_cols = [c for c in display_cols if c in df.columns]

    # ---------------------------------------------------------------------------
    # 1. Team-by-Team Breakdown
    # ---------------------------------------------------------------------------
    print_separator("1. Team Rosters & Classified Roles")

    rostered_df = df[df["Team"].notna() & (df["Team"] != "")].copy()
    no_team_df = df[df["Team"].isna() | (df["Team"] == "")].copy()

    for team, group in rostered_df.groupby("Team", sort=False):
        print(f"\n[ TEAM: {team.upper()} ]")
        print("-" * 120)
        print(group[display_cols].to_string(index=False))
        print("-" * 120)

    # ---------------------------------------------------------------------------
    # 2. Free Agents / Unrostered Players
    # ---------------------------------------------------------------------------
    if not no_team_df.empty:
        print_separator("2. Unrostered / Free Agents")
        print(no_team_df[display_cols].to_string(index=False))

    # ---------------------------------------------------------------------------
    # 3. Selected In-Game Leaders (IGLs) Summary
    # ---------------------------------------------------------------------------
    print_separator("3. Team Captains / In-Game Leaders (is_igl == True)")

    igls = df[df["is_igl"] == True][["Team", "Player", "role", "confidence", "igl_score", "Utility", "Opening", "Entrying"]]
    if not igls.empty:
        print(igls.to_string(index=False))
    else:
        print("No IGLs assigned (check if 'Team' column exists in dataset).")

    # ---------------------------------------------------------------------------
    # 4. Global Role Distribution Summary
    # ---------------------------------------------------------------------------
    print_separator("4. Classifier Summary Statistics")

    role_counts = df["role"].value_counts()
    print("► Role Distribution:")
    for role, count in role_counts.items():
        print(f"   • {role:<15}: {count} players")

    avg_confidence = df["confidence"].mean()
    print(f"\n► Average Classification Confidence: {avg_confidence:.1f}%")

    print("\n[CLASSIFIER TEST COMPLETE]\n")


if __name__ == "__main__":
    main()