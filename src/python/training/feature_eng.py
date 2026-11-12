import pandas as pd
import numpy as np
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine


#define columns for function
stat_cols = [
        "points", "goals_for", "goals_against",
        "shots", "shots_against",
        "shots_on_target", "shots_on_target_against",
        "shots_off_target", "shots_off_target_against",
        "possession_pct", "possession_pct_against",
        "corners", "corners_against",
        "yellow_cards", "yellow_cards_against",
]

WINDOW = 5
MIN_HISTORY = 3


def build_dataset():

    load_dotenv()
    engine = create_engine(os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://", 1))

    #pull data from the database into a pandas dataframe
    match_stats_df = pd.read_sql("SELECT * FROM team_match_stats", engine)
    odds_df = pd.read_sql(
        """
        SELECT match_id,
            MAX(CASE WHEN selection = 'home' THEN decimal_odds END) AS odds_h,
            MAX(CASE WHEN selection = 'draw' THEN decimal_odds END) AS odds_d,
            MAX(CASE WHEN selection = 'away' THEN decimal_odds END) AS odds_a
        FROM odds
        WHERE market = 'match_result'
        GROUP BY match_id
        """, engine)

#   cast odds columns' decimal values to float
    odds_df[["odds_h", "odds_d", "odds_a"]] = odds_df[["odds_h", "odds_d", "odds_a"]].astype(float)

    engine.dispose()

    # print(df.shape)
    # print(df.dtypes)
    # print(df.head())

    #typecast columns to appropriate types
    match_stats_df["possession_pct"] = match_stats_df["possession_pct"].astype(float)
    match_stats_df["possession_pct_against"] = match_stats_df["possession_pct_against"].astype(float)
    match_stats_df["match_date"] = pd.to_datetime(match_stats_df["match_date"])
    match_stats_df = match_stats_df.sort_values(["team_id", "match_date"]).reset_index(drop=True)


    #===========================
    # Calculate rolling averages
    #===========================

    #team form
    match_stats_df["points"] = np.select(
        [match_stats_df["goals_for"] > match_stats_df["goals_against"], match_stats_df["goals_for"] == match_stats_df["goals_against"]],
        [3, 1],
        default=0
    )


    #group by team_id and calculate rolling averages for each stat column
    grouped = match_stats_df.groupby("team_id")
    for col in stat_cols:
        match_stats_df[f"{col}_rolling"] = grouped[col].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).mean())


    match_stats_df["matches_sampled"] = grouped["goals_for"].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).count())


    #============================
    # Home/Away Merge
    #============================

    rolling_cols = [c for c in match_stats_df.columns if "_rolling" in c]
    side_cols = ["team_id", "goals_for", "goals_against", "matches_sampled"] + rolling_cols 

    #split two rows per match into home and away dataframes
    home = match_stats_df[match_stats_df["is_home"]][["match_id", "match_date", "league"] + side_cols] #match date and league are identical for h & a
    away = match_stats_df[~match_stats_df["is_home"]][["match_id"] + side_cols]

    #prefix every column except the join key
    home = home.rename(columns={c: f"home_{c}" for c in side_cols})
    away = away.rename(columns={c: f"away_{c}" for c in side_cols})

    #merge to one row per match
    matches = pd.merge(home, away, on="match_id", how="inner", validate="one_to_one")

    #merge odds to matches on left join, as some matches may not have odds data
    matches = matches.merge(odds_df, on="match_id", how="left", validate="one_to_one")


    #============================
    # Feature Engineering
    #============================

    hg, ag = matches["home_goals_for"], matches["away_goals_for"]

    matches["result"] = np.select([hg > ag, hg == ag], ["H", "D"], default="A")
    matches["total_goals"] = hg + ag
    matches["btts"] = (hg > 0) & (ag > 0)

    #columns for model training
    feature_cols = [c for c in matches.columns if "_rolling" in c] + ["home_matches_sampled", "away_matches_sampled"]

    usable = matches[(matches["home_matches_sampled"] >= MIN_HISTORY) & (matches["away_matches_sampled"] >= MIN_HISTORY)].copy() #only use matches where both teams have at least MIN_HISTORY matches sampled
    usable = usable.sort_values("match_date").reset_index(drop=True)

    return usable, feature_cols

if __name__ == "__main__":
    usable, feature_cols = build_dataset()
    print(len(usable), len(feature_cols)) 