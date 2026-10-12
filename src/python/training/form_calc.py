#calculate form using previous 5 matches from any given date
#useful feature for training model

#team form
def get_team_form(cur, team_id, as_of_date, window=5, venue="all"):

    venue_filter = ""

    if venue == "home":
        venue_filter = "AND is_home = TRUE"
    elif venue == "away":
        venue_filter = "AND is_home = FALSE"

    #pulls a DB sample of a teams last 5 games as of a given date with goals for/against
    cur.execute(
        f"""

        SELECT goals_for, goals_against
        FROM team_match_stats tms
        WHERE tms.team_id = %(team_id)s
            AND tms.match_date < %(as_of_date)s
            {venue_filter}
        ORDER BY tms.match_date DESC
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
    for goals_for, goals_against in rows:

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
def get_stat_form(cur, team_id, as_of_date, stat_col, window=5, venue="all"):

    venue_filter = ""

    if venue == "home":
        venue_filter = "AND is_home = TRUE"
    elif venue == "away":
        venue_filter = "AND is_home = FALSE"

    against_col = f"{stat_col}_against"

    cur.execute(
        f"""

        SELECT {stat_col}, {against_col}
        FROM team_match_stats tms
        WHERE tms.team_id = %(team_id)s
            AND tms.match_date < %(as_of_date)s
            {venue_filter}
        ORDER BY tms.match_date DESC
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
    test_team_id = 14148  # arsenal
    test_date = date(2024, 3, 1)
 
    print(f"Overall form: {get_team_form(cur, test_team_id, test_date)}")
    print(f"Home form: {get_team_form(cur, test_team_id, test_date, venue='home')}")
    print(f"Shots: {get_stat_form(cur, test_team_id, test_date, 'shots')}")
    print(f"Corners: {get_stat_form(cur, test_team_id, test_date, 'corners')}")
    print(f"Cards: {get_stat_form(cur, test_team_id, test_date, 'yellow_cards')}")

    cur.close()
    conn.close()

