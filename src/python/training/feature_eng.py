import pandas as pd
import numpy as np
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://", 1))

df = pd.read_sql("SELECT * FROM team_match_stats", engine)
arsenal_id = pd.read_sql("SELECT id FROM teams WHERE name = 'Arsenal'", engine).iloc[0, 0] #get arsenal id
engine.dispose()

# print(df.shape)
# print(df.dtypes)
# print(df.head())

df["possession_pct"] = df["possession_pct"].astype(float)
df["match_date"] = pd.to_datetime(df["match_date"])
df = df.sort_values(["team_id", "match_date"]).reset_index(drop=True)

df["shots_rolling"] = (
    df.groupby("team_id")["shots"]
    .transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
)

arsenal = df[df["team_id"] == arsenal_id]
check = arsenal[arsenal["match_date"] >= "2024-03-01"].head(1)
print(check[["match_date", "shots", "shots_against", "shots_rolling"]])