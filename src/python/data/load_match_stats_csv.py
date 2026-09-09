import argparse
import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from db_helpers import get_or_create_team, get_or_create_match, parse_match_date

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

NATURAL_KEY = ["homeTeam", "awayTeam", "matchDate"]


#functions

#set the number of home goals and away goals for an item in the matches table given the match_id
def set_match_goals(cur, match_id, home_goals, away_goals):
    cur.execute(
        """
        UPDATE matches
        SET home_goals = %s, away_goals = %s
        WHERE id = %s
        """,
        (int(home_goals), int(away_goals), match_id),
    )


def upsert_match_stats(cur, match_id, row):
    cur.execute(
        """
        INSERT INTO match_stats (match_id, home_possession_pct, away_possession_pct,
            home_shots, away_shots, home_shots_on_target, away_shots_on_target,
            home_shots_off_target, away_shots_off_target,
            home_corners, away_corners, home_yellow_cards, away_yellow_cards
            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO UPDATE SET
            home_possession_pct = EXCLUDED.home_possession_pct,
            away_possession_pct = EXCLUDED.away_possession_pct,
            home_shots = EXCLUDED.home_shots,
            away_shots = EXCLUDED.away_shots,
            home_shots_on_target = EXCLUDED.home_shots_on_target,
            away_shots_on_target = EXCLUDED.away_shots_on_target,
            home_shots_off_target = EXCLUDED.home_shots_off_target,
            away_shots_off_target = EXCLUDED.away_shots_off_target,
            home_corners = EXCLUDED.home_corners,
            away_corners = EXCLUDED.away_corners,
            home_yellow_cards = EXCLUDED.home_yellow_cards,
            away_yellow_cards = EXCLUDED.away_yellow_cards
        """,
        (
            match_id,
            float(row["HBPFT"]),
            float(row["ABPFT"]),
            int(row["HTSFT"]),
            int(row["ATSFT"]),
            int(row["HSONFT"]),
            int(row["ASONFT"]),
            int(row["HSOFFFT"]),
            int(row["ASOFFFT"]),
            int(row["HCFT"]),
            int(row["ACFT"]),
            int(row["HYCFT"]),
            int(row["AYCFT"]),
        ),
    )

def load_match_stats_csv(scores_path, corners_cards_path, shots_poss_path):

    scores_df = pd.read_csv(scores_path)
    corners_cards_df = pd.read_csv(corners_cards_path)
    shots_poss_df = pd.read_csv(shots_poss_path)

    #merge dataframes on natural key on inner join, so only matches in all 3 files are processed
    merged_df = scores_df.merge(
        corners_cards_df, on=NATURAL_KEY, how="inner", suffixes=("", "_cc")
    ).merge(
        shots_poss_df, on=NATURAL_KEY, how="inner", suffixes=("", "_sp")
    )

    print(f"{len(merged_df)} matches found after merging all 3 files.")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    #count
    matches_processed = 0

    try:
        for i, (_, row) in enumerate(merged_df.iterrows()):
            home_id = get_or_create_team(cur, str(row["homeTeam"]).strip())
            away_id = get_or_create_team(cur, str(row["awayTeam"]).strip())

            match_date = parse_match_date(row["matchDate"])
    
            match_id = get_or_create_match(
                cur, home_id, away_id, row["League"], match_date, row["Season"]
            )

            set_match_goals(cur, match_id, row["FTHG"], row["FTAG"])
            upsert_match_stats(cur, match_id, row)
            matches_processed += 1

            if (i + 1) % 200 == 0:
                print(f"  ...{i + 1}/{len(merged_df)} rows processed")

        conn.commit()
        print(f"Processed {matches_processed} matches with stats from the CSV files.")

    
    except Exception:
        conn.rollback() #rolls back the transaction if any error occurs
        raise

    finally:
        cur.close()
        conn.close()

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load Footiqo goals, corners, cards, shots and possesion stats from 3 CSV files into the database."
    )

    parser.add_argument("--scores", required=True, help="Path to the CSV file containing match scores.")
    parser.add_argument("--corners_cards", required=True, help="Path to the CSV file containing match corners and cards stats.")
    parser.add_argument("--shots_poss", required=True, help="Path to the CSV file containing match shots and possession stats.")
    args = parser.parse_args()

    load_match_stats_csv(args.scores, args.corners_cards, args.shots_poss)