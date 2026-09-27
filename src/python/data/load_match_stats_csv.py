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


def upsert_team_match_stats(cur, match_id, team_id, opponent_id, is_home, match_date, league, goals_for, goals_against, shots, shots_on_target, shots_off_target, possession_pct, corners, yellow_cards):

    cur.execute(
        """
        INSERT INTO team_match_stats (
        match_id, team_id, opponent_id, is_home, match_date, league, goals_for, goals_against, shots, shots_on_target, shots_off_target, possession_pct, corners, yellow_cards
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

        ON CONFLICT (match_id, team_id) DO UPDATE SET
        opponent_id = EXCLUDED.opponent_id,
        is_home = EXCLUDED.is_home,
        goals_for = EXCLUDED.goals_for,
        goals_against = EXCLUDED.goals_against,
        shots = EXCLUDED.shots,
        shots_on_target = EXCLUDED.shots_on_target,
        shots_off_target = EXCLUDED.shots_off_target,
        possession_pct = EXCLUDED.possession_pct,
        corners = EXCLUDED.corners,
        yellow_cards = EXCLUDED.yellow_cards
        """,

        (
            match_id, team_id, opponent_id, is_home, match_date, league,
            int(goals_for), int(goals_against),int(shots), int(shots_on_target), int(shots_off_target),
            float(possession_pct), int(corners), int(yellow_cards)
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
            #home team
            upsert_team_match_stats(cur, match_id, home_id, away_id, True, match_date, row["League"], goals_for=row["FTHG"], goals_against=row["FTAG"],
                                    shots=row["HTSFT"], shots_on_target=row["HSONFT"], shots_off_target=row["HSOFFFT"],
                                    possession_pct=row["HBPFT"], corners=row["HCFT"], yellow_cards=row["HYCFT"])

            #away team
            upsert_team_match_stats(cur, match_id, away_id, home_id, False, match_date, row["League"], goals_for=row["FTAG"], goals_against=row["FTHG"],
                                    shots=row["ATSFT"], shots_on_target=row["ASONFT"], shots_off_target=row["ASOFFFT"],
                                    possession_pct=row["ABPFT"], corners=row["ACFT"], yellow_cards=row["AYCFT"])
            matches_processed += 1

            if (i + 1) % 200 == 0:
                print(f"  ...{i + 1}/{len(merged_df)} rows processed")

        conn.commit()
        print(f"Processed {matches_processed} matches with {matches_processed * 2} team-perspective rows from the CSV files.")

    
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