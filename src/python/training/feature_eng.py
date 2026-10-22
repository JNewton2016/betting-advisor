import pandas as pd
import numpy as np
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://", 1))

#pull data from the database into a pandas dataframe
df = pd.read_sql("SELECT * FROM team_match_stats", engine)
arsenal_id = pd.read_sql("SELECT id FROM teams WHERE name = 'Arsenal'", engine).iloc[0, 0] #get arsenal id
engine.dispose()

# print(df.shape)
# print(df.dtypes)
# print(df.head())

#typecast columns to appropriate types
df["possession_pct"] = df["possession_pct"].astype(float)
df["possession_pct_against"] = df["possession_pct_against"].astype(float)
df["match_date"] = pd.to_datetime(df["match_date"])
df = df.sort_values(["team_id", "match_date"]).reset_index(drop=True)


#===========================
# Calculate rolling averages
#===========================

#team form
df["points"] = np.select(
    [df["goals_for"] > df["goals_against"], df["goals_for"] == df["goals_against"]],
    [3, 1],
    default=0
)

stat_cols = [
    "points", "goals_for", "goals_against",
    "shots", "shots_against",
    "shots_on_target", "shots_on_target_against",
    "shots_off_target", "shots_off_target_against",
    "possession_pct", "possession_pct_against",
    "corners", "corners_against",
    "yellow_cards", "yellow_cards_against",
]

#group by team_id and calculate rolling averages for each stat column
grouped = df.groupby("team_id")
for col in stat_cols:
    df[f"{col}_rolling"] = grouped[col].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())


df["matches_sampled"] = grouped["goals_for"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).count())

cols = ["match_date", "points_rolling", "goals_for_rolling", "goals_against_rolling",
        "shots_rolling", "corners_rolling", "yellow_cards_rolling", "matches_sampled"]

arsenal = df[df["team_id"] == arsenal_id]
check = arsenal[arsenal["match_date"] >= "2024-08-10"].head(1)
print(check[cols])


#============================
# Home/Away Merge
#============================

rolling_cols = [c for c in df.columns if "_rolling" in c]
side_cols = ["team_id", "goals_for", "goals_against", "matches_sampled"] + rolling_cols 

#split two rows per match into home and away dataframes
home = df[df["is_home"]][["match_id", "match_date", "league"] + side_cols] #match date and league are identical for h & a
away = df[~df["is_home"]][["match_id"] + side_cols]

#prefix every column except the join key
home = home.rename(columns={c: f"home_{c}" for c in side_cols})
away = away.rename(columns={c: f"away_{c}" for c in side_cols})

#merge to one row per match
matches = pd.merge(home, away, on="match_id", how="inner", validate="one_to_one")


#============================
# Feature Engineering
#============================

hg, ag = matches["home_goals_for"], matches["away_goals_for"]

matches["result"] = np.select([hg > ag, hg == ag], ["H", "D"], default="A")
matches["total_goals"] = hg + ag
matches["btts"] = (hg > 0) & (ag > 0)

#columns for model training
feature_cols = [c for c in matches.columns if "_rolling" in c] + ["home_matches_sampled", "away_matches_sampled"]

usable = matches[(matches["home_matches_sampled"] >= 3) & (matches["away_matches_sampled"] >= 3)] #only use matches where both teams have at least 3 matches sampled
print(len(usable))
print(usable[feature_cols].isna().sum().sum())