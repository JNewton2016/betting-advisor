"""
Load Premier League and Championship odds from CSV files into the database.

"""

import os
import argparse
from datetime import datetime

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from db_helpers import get_or_create_team, get_or_create_match, parse_match_date

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


#Map columns in the CSV files to the corresponding columns in the database tables (snake_case to camelCase)
COLUMN_MAPPING = {
    "match_date": "matchDate",
    "league": "League",
    "season": "Season",
    "home_team": "homeTeam",
    "away_team": "awayTeam",
}

#Map CSV columns to a market and its given selections
MARKET_COLUMN_MAPPING = {
    "H": ("match_result", "home"),
    "D": ("match_result", "draw"),
    "A": ("match_result", "away"),
    "O05": ("over_under_0.5", "over"),
    "U05": ("over_under_0.5", "under"),
    "O15": ("over_under_1.5", "over"),
    "U15": ("over_under_1.5", "under"),
    "O25": ("over_under_2.5", "over"),
    "U25": ("over_under_2.5", "under"),
    "O35": ("over_under_3.5", "over"),
    "U35": ("over_under_3.5", "under"),
    "O45": ("over_under_4.5", "over"),
    "U45": ("over_under_4.5", "under"),
    "BTTSY": ("btts", "yes"),
    "BTTSN": ("btts", "no"),
}



#FUNCTIONS

def upsert_odds(cur, match_id, bookmaker, market, selection, decimal_odds):
    cur.execute(
        """
        INSERT INTO odds (match_id, bookmaker, market, selection, decimal_odds)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (match_id, bookmaker, market, selection)
        DO UPDATE SET decimal_odds = EXCLUDED.decimal_odds, pulled_at = NOW()
        """,
        (match_id, bookmaker, market, selection, decimal_odds),
    )




#function to load the CSV file and insert/update the data into the database
#opens one database transaction for the file, processing every row and commits at the end
def load_odds_csv(path, bookmaker):

    df = pd.read_csv(path)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    #count
    matches_processed = 0
    odds_processed = 0

    
    try:
        #run through each row in the df, populate teams and match tables, then populate odds table for each market per match
        for i, (_, row) in enumerate(df.iterrows()):
            home_id = get_or_create_team(cur, str(row[COLUMN_MAPPING["home_team"]]).strip())
            away_id = get_or_create_team(cur, str(row[COLUMN_MAPPING["away_team"]]).strip())

            match_date = parse_match_date(row[COLUMN_MAPPING["match_date"]])

            match_id = get_or_create_match(
                cur,
                home_id,
                away_id,
                row[COLUMN_MAPPING["league"]],
                match_date,
                row[COLUMN_MAPPING["season"]],
            )
            matches_processed += 1

            #run through each market column and its selections, and populate odds per selection per match
            for col, (market, selection) in MARKET_COLUMN_MAPPING.items():
                if col in row and pd.notna(row[col]):
                    upsert_odds(
                        cur,
                        match_id,
                        bookmaker,
                        market,
                        selection,
                        float(row[col]),
                    )
                    odds_processed += 1

            #prints status of matches processed
            if (i + 1) % 200 == 0:
                print(f"  ...{i + 1}/{len(df)} rows processed")

        #commit the transaction to DB
        conn.commit()
        print(f"Processed {matches_processed} matches and {odds_processed} odds for bookmaker from {path}")

    except Exception:
        conn.rollback() #rolls back the transaction if any error occurs
        raise

    finally:
        cur.close()
        conn.close()


#run the script from command line with the path to the CSV file and the bookmaker name as arguments
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load Premier League and Championship odds from Footiqo CSV files into the database."
    )
    parser.add_argument("csv_path", help="Path to the CSV file containing the odds data.")
    parser.add_argument(
        "--bookmaker",
        default="Footiqo",
        help="Name of the bookmaker for which to load odds data."
    )
    args = parser.parse_args()

    load_odds_csv(args.csv_path, args.bookmaker)
