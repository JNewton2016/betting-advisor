"""
Load Premier League and Championship odds from CSV files into the database.

"""

import os
import argparse
from datetime import datetime

import pandas as pd
import psycopg2
from dotenv import load_dotenv

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
    "O05": ("over_under_05", "over"),
    "U05": ("over_under_05", "under"),
    "O15": ("over_under_15", "over"),
    "U15": ("over_under_15", "under"),
    "O25": ("over_under_25", "over"),
    "U25": ("over_under_25", "under"),
    "O35": ("over_under_35", "over"),
    "U35": ("over_under_35", "under"),
    "O45": ("over_under_45", "over"),
    "U45": ("over_under_45", "under"),
    "BTTSY": ("btts", "yes"),
    "BTTSN": ("btts", "no"),
}

MATCH_DATE_FORMAT = "%d/%m/%Y %H:%M"


#FUNCTIONS

#searches a team by name, inserts if new and then always returns the team id
def get_or_create_team(cur, name):
    cur.execute(
        """
        INSERT INTO teams (name) VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (name,),
    )
    return cur.fetchone()[0]

#same for matches, but also updates league and season if the match already exists
def get_or_create_match(cur, home_id, away_id, league, match_date, season):
    cur.execute(
        """
        INSERT INTO matches (home_team_id, away_team_id, league, match_date, season, status)
        VALUES (%s, %s, %s, %s, %s, 'finished')
        ON CONFLICT (match_date, home_team_id, away_team_id)
        DO UPDATE SET league = EXCLUDED.league, season = EXCLUDED.season
        RETURNING id
        """,
        (home_id, away_id, league, match_date, season),
    )
    return cur.fetchone()[0]


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
def load_csv(path, bookmaker):

    df = pd.read_csv(path)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    #count
    matches_processed = 0
    odds_processed = 0


    try:
        for _, row in df.iterrows():
            home_id = get_or_create_team(cur, row[COLUMN_MAPPING["home_team"]]).strip()
            away_id = get_or_create_team(cur, row[COLUMN_MAPPING["away_team"]]).strip()

            match_date = datetime.strptime(
                row[COLUMN_MAPPING["match_date"]], MATCH_DATE_FORMAT
            )

            match_id = get_or_create_match(
                cur,
                home_id,
                away_id,
                row[COLUMN_MAPPING["league"]],
                match_date,
                row[COLUMN_MAPPING["season"]],
            )
            matches_processed += 1

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

        conn.commit()
        print(f"Processed {matches_processed} matches and {odds_processed} odds for bookmaker from {path}")

    except Exception:
        conn.rollback() #rolls back the transaction if any error occurs
        raise

    finally:
        cur.close()
        conn.close()


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

    load_csv(args.csv_path, args.bookmaker)
