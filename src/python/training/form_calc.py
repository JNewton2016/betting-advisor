#calculate form using previous 5 matches from any given date
#useful feature for training model

#team form
def get_team_form(cur, team_id, as_of_date, window=5, venue="all"):

    if venue == "home":
        venue_filter = "m.home_team_id = %(team_id)s"
    elif venue == "away":
        venue_filter = "m.away_team_id = %(team_id)s"
    else:
        venue_filter = "(m.home_team_id = %(team_id)s OR m.away_team_id = %(team_id)s)"

    #pulls a DB sample of a teams last 5 games as of a given date with goals for/against
    cur.execute(
        f"""

        SELECT
            m.home_team_id,
                CASE WHEN m.home_team_id = %(team_id)s THEN m.home_goals ELSE m.away_goals END AS goals_for,
                CASE WHEN m.home_team_id = %(team_id)s THEN m.away_goals ELSE m.home_goals END AS goals_against
            FROM matches m
            WHERE {venue_filter}
                AND m.match_date < %(as_of_date)s
                AND m.status = 'finished'
            ORDER BY m.match_date DESC
            LIMIT %(window)s
        """,
        {
            "team_id": team_id,
            "as_of_date": as_of_date,
            "window": window
        },
    )
    rows = cur.fetchall()

    matches_played = len(rows)

    #catches a period with no matches
    if matches_played == 0:
        return {
            "matches_played": 0,
            "points": None,
            "wins": None, "draws": None, "losses": None,
            "goals_for": None, "goals_against": None,
            "goals_for_avg": None, "goals_against_avg": None,
        }


    wins = draws = losses = 0
    goals_for_total = goals_against_total = 0

    #
    for _, goals_for, goals_against in rows:

        goals_for_total += goals_for
        goals_against_total += goals_against

        #tallies W/D/L based on goals for/against
        if goals_for > goals_against:
            wins += 1
        elif goals_for == goals_against:
            draws += 1
        else:
            losses += 1

    points = (wins * 3) + draws #3pts for win, 1pt for draw, 0pts for loss

    #return JSON payload of teams form information
    return{
        "matches_played": matches_played,
        "points": points,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for_total,
        "goals_against": goals_against_total,
        "goals_for_avg": round(goals_for_total / matches_played, 2),
        "goals_against_avg": round(goals_against_total / matches_played, 2)
    }

#get numbers for any stat in previous 5 games
def get_stat_form(cur, team_id, as_of_date, home_col, away_col, window=5, venue="all", join_on_stats=True):

    if venue == "home":
        venue_filter = "m.home_team_id = %(team_id)s"
    elif venue == "away":
        venue_filter = "m.away_team_id = %(team_id)s"
    else:
        venue_filter = "(m.home_team_id = %(team_id)s OR m.away_team_id = %(team_id)s)"

    join_clause = f"JOIN match_stats ms ON ms.match_id = m.id" if join_on_stats else ""
    table_prefix = "ms." if join_on_stats else "m."

    cur.execute(
        f"""
        SELECT
            CASE WHEN m.home_team_id = %(team_id)s THEN {table_prefix}{home_col} ELSE {table_prefix}{away_col} END AS value_for,
            CASE WHEN m.home_team_id = %(team_id)s THEN {table_prefix}{away_col} ELSE {table_prefix}{home_col} END AS value_against
        FROM matches m
        {join_clause}
        WHERE {venue_filter}
            AND m.match_date < %(as_of_date)s
            AND m.status = 'finished'
        ORDER BY m.match_date DESC
        LIMIT %(window)s
        """,

        {
            "team_id": team_id,
            "as_of_date": as_of_date,
            "window": window
        }
    )
    rows = cur.fetchall()

    matches_played = len(rows)

    if matches_played == 0:
        return {"matches_played": 0, "avg_for": None, "avg_against": None}

    total_for = sum(r[0] for r in rows)
    total_against = sum(r[1] for r in rows)

    return {
        "matches_played": matches_played,
        "avg_for": round(total_for / matches_played, 2),
        "avg_against": round(total_against / matches_played, 2),
    }


if __name__ == "__main__":
    
    import os
    import psycopg2
    from datetime import date
    from dotenv import load_dotenv

    load_dotenv()
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    #hardcoded DB test
    test_team_id = 2664 #arsenal
    test_date = date(2024, 3, 1)

    result = get_team_form(cur, test_team_id, as_of_date=date(2024, 3, 1), window=5)
    print(f"Overall form: {result}")

    home_result = get_team_form(cur, test_team_id, as_of_date=date(2024, 3, 1), window=5, venue="home")
    print(f"Home form: {home_result}")

    shots = get_stat_form(cur, test_team_id, test_date, "home_shots", "away_shots")
    print(f"Shots: {shots}")

    corners = get_stat_form(cur, test_team_id, test_date, "home_corners", "away_corners")
    print(f"Corners: {corners}")

    cur.close()
    conn.close()

