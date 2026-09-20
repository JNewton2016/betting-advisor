import pandas as pd


from form_calc import get_stat_form, get_team_form

#derive features from match_stats table and engineer data columns for training
def engineer_features (df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    #match totals
    df['total_yellows'] = df['home_yellow_cards'] + df['away_yellow_cards']
    df['total_corners'] = df['home_corners'] + df['away_corners']
    df['total_shots'] = df['home_shots'] + df['away_shots']
    
    

    #attacking indicators
    df['home_shot_accuracy'] = df['home_shots_on_target'] / df["home_shots"].replace(0, pd.NA)
    df['away_shot_accuracy'] = df['away_shots_on_target'] / df['away_shots'].replace(0, pd.NA)


    return df


#find rolling average of stats for given team at given date
def add_rolling_team_features(df: pd.DataFrame, team_col: str, stat_cols: list[str], window: int=5) -> pd.DataFrame:
    df = df.sort_values('match_date')

    for col in stat_cols:
        df[f'{col}_rolling'] = (
            df.groupby(team_col)[col]
            .transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
        )

    return df

#columns used as features in training
feature_cols = [
    """
    home_possession_pct,
    away_possession_pct,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    home_shots_off_target,
    away_shots_off_target,
    home_corners,
    away_corners,
    home_yellow_cards,
    away_yellow_cards,
    total_yellows,
    total_corners,

    """
]


def get_training_features_set(df: pd.DataFrame) -> pd.DataFrame:
    df = engineer_features(df)
    return df[feature_cols]
