"""
helper functions used for database operations, such as inserting and updating data from CSV files
for historical data or live API data for frontend display

"""
from datetime import datetime

MATCH_DATE_FORMATS = ["%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%y %H:%M", "%d-%m-%y %H:%M"]

#look up a team by name, insert it if it doesn't exist, and return the team id always
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

#look up a match by the natural key (home team, away team, match date), insert if it doesnt exist and return the match id always
def get_or_create_match(cur, home_id, away_id, league, match_date, season, status="finished"):
    cur.execute(
        """
        INSERT INTO matches (home_team_id, away_team_id, league, match_date, season, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (home_team_id, away_team_id, match_date)
        DO UPDATE SET league = EXCLUDED.league, season = EXCLUDED.season
        RETURNING id
        """,
        (home_id, away_id, league, match_date, season, status),
    )
    return cur.fetchone()[0]


#handle date formats
def parse_match_date(date_str):
    for f in MATCH_DATE_FORMATS:
        try:
            return datetime.strptime(date_str, f)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")