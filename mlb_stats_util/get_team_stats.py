import pybaseball as pyb
import polars as pl
from typing import Dict, Tuple, Any, List
import pandas as pd
import numpy as np
import warnings
from datetime import datetime

# Suppress library-internal noise
warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.simplefilter(action="ignore", category=UserWarning)
pd.options.mode.chained_assignment = None


def get_park_factor(team: str) -> float:
    """
    Returns the park factor for a specific team, normalized to a 1.0 baseline.

    :param str team: The nickname of the MLB team (e.g., 'Astros').
    :return float: The park factor as a decimal (e.g., 0.994).
    """
    mapping: Dict[str, float] = {
        "Angels": 101.23049020767212,
        "Astros": 99.48140382766724,
        "Athletics": 102.86766290664673,
        "Blue Jays": 99.45313930511475,
        "Braves": 100.12708902359009,
        "Brewers": 98.89779090881348,
        "Cardinals": 97.5001335144043,
        "Cubs": 97.8569507598877,
        "Diamondbacks": 100.64197778701782,
        "Dodgers": 99.1439938545227,
        "Giants": 97.25400805473328,
        "Guardians": 98.87371063232422,
        "Mariners": 93.54020357131958,
        "Marlins": 100.99986791610718,
        "Mets": 96.34352326393127,
        "Nationals": 99.63456988334656,
        "Orioles": 98.61453771591187,
        "Padres": 95.90458273887634,
        "Phillies": 101.27016305923462,
        "Pirates": 101.54402256011963,
        "Rangers": 98.6534059047699,
        "Rays": 100.93531608581543,
        "Red Sox": 104.24087047576904,
        "Reds": 104.54981327056885,
        "Rockies": 113.34958076477051,
        "Royals": 103.06445360183716,
        "Tigers": 100.30543804168701,
        "Twins": 100.81133842468262,
        "White Sox": 100.31185150146484,
        "Yankees": 98.9298939704895,
    }

    return mapping.get(team, 100.0) / 100


def get_sc_to_nickname_mapping() -> Dict[str, str]:
    """
    Maps Statcast team abbreviations to team nicknames.
    """
    return {
        "CWS": "White Sox",
        "CHC": "Cubs",
        "NYY": "Yankees",
        "NYM": "Mets",
        "ANA": "Angels",
        "LAA": "Angels",
        "LAD": "Dodgers",
        "HOU": "Astros",
        "DET": "Tigers",
        "PHI": "Phillies",
        "BAL": "Orioles",
        "TOR": "Blue Jays",
        "ATL": "Braves",
        "ARI": "Diamondbacks",
        "AZ": "Diamondbacks",
        "TB": "Rays",
        "PIT": "Pirates",
        "SEA": "Mariners",
        "SF": "Giants",
        "OAK": "Athletics",
        "ATH": "Athletics",
        "CLE": "Guardians",
        "SD": "Padres",
        "BOS": "Red Sox",
        "MIL": "Brewers",
        "MIN": "Twins",
        "KC": "Royals",
        "CIN": "Reds",
        "MIA": "Marlins",
        "COL": "Rockies",
        "TEX": "Rangers",
        "WSH": "Nationals",
        "WSN": "Nationals",
        "STL": "Cardinals",
    }


def get_team_stats(year: int) -> pl.DataFrame:
    """
    Calculates detailed team statistics using Statcast data.
    Avoids Baseball-Reference to prevent rate limiting and library-internal errors.

    :param int year: The year for which to compute data.
    :return pl.DataFrame: DataFrame with detailed team stats.
    """
    print(f"Fetching Statcast data for {year}...")
    start_date = f"{year}-03-01"
    end_date = f"{year}-11-15"

    # Fetching Statcast data - this is generally one large request
    sc_df = pyb.statcast(start_dt=start_date, end_dt=end_date)
    pl_sc = pl.from_pandas(sc_df)

    if pl_sc.is_empty():
        raise ValueError(f"No Statcast data found for {year}.")

    sc_to_nickname = get_sc_to_nickname_mapping()

    # 1. Team Runs For and Against (Game-by-Game)
    print("Processing game results...")
    game_results = pl_sc.group_by("game_pk").agg(
        [
            pl.col("game_date").first(),
            pl.col("home_team").first(),
            pl.col("away_team").first(),
            pl.col("post_home_score").max().alias("home_score"),
            pl.col("post_away_score").max().alias("away_score"),
        ]
    )

    # Reshape to get one row per team per game
    home_games = game_results.select(
        [
            pl.col("game_date"),
            pl.col("home_team").alias("Team_Abbr"),
            pl.col("away_team").alias("Opp_Abbr"),
            pl.col("home_score").alias("R"),
            pl.col("away_score").alias("RA"),
            pl.lit("Home").alias("Loc"),
        ]
    )

    away_games = game_results.select(
        [
            pl.col("game_date"),
            pl.col("away_team").alias("Team_Abbr"),
            pl.col("home_team").alias("Opp_Abbr"),
            pl.col("away_score").alias("R"),
            pl.col("home_score").alias("RA"),
            pl.lit("Away").alias("Loc"),
        ]
    )

    all_games = pl.concat([home_games, away_games])

    # 2. Team Offense vs LHP and vs RHP
    print("Calculating offense splits...")

    # Create batting_team column
    pl_sc = pl_sc.with_columns(
        pl.when(pl.col("inning_topbot") == "Top")
        .then(pl.col("away_team"))
        .otherwise(pl.col("home_team"))
        .alias("batting_team")
    )

    # Calculate wOBA components per team vs handedness
    splits = (
        pl_sc.filter(pl.col("events").is_not_null())
        .group_by(["batting_team", "p_throws"])
        .agg(
            [
                pl.col("events")
                .filter(pl.col("events") == "single")
                .count()
                .alias("1B"),
                pl.col("events")
                .filter(pl.col("events") == "double")
                .count()
                .alias("2B"),
                pl.col("events")
                .filter(pl.col("events") == "triple")
                .count()
                .alias("3B"),
                pl.col("events")
                .filter(pl.col("events") == "home_run")
                .count()
                .alias("HR"),
                pl.col("events").filter(pl.col("events") == "walk").count().alias("BB"),
                pl.col("events")
                .filter(pl.col("events") == "hit_by_pitch")
                .count()
                .alias("HBP"),
                pl.col("at_bat_number").count().alias("PA"),
            ]
        )
    )

    splits = splits.with_columns(
        (
            (
                pl.col("BB") * 0.703
                + pl.col("HBP") * 0.734
                + pl.col("1B") * 0.900
                + pl.col("2B") * 1.281
                + pl.col("3B") * 1.625
                + pl.col("HR") * 2.097
            )
            / pl.col("PA")
        ).alias("wOBA")
    )

    splits_pivot = splits.pivot(
        on="p_throws", index="batting_team", values="wOBA"
    ).rename({"batting_team": "Team_Abbr", "L": "wOBA_vs_LHP", "R": "wOBA_vs_RHP"})

    # 3. Calculate Runs in Last 10 Games
    print("Calculating Last 10 games trend...")
    last_10_stats = (
        all_games.sort("game_date", descending=True)
        .group_by("Team_Abbr")
        .head(10)
        .group_by("Team_Abbr")
        .agg(
            [
                pl.col("R").sum().alias("Runs_L10"),
            ]
        )
    )

    # 4. Final Averages and Park Factors
    print("Finalizing summary...")
    team_summary = all_games.group_by("Team_Abbr").agg(
        [
            pl.col("R").mean().alias("Avg_Runs_For"),
            pl.col("RA").mean().alias("Avg_Runs_Against"),
        ]
    )

    final_df = team_summary.join(splits_pivot, on="Team_Abbr", how="left")
    final_df = final_df.join(last_10_stats, on="Team_Abbr", how="left")

    # Map nicknames for Park Factor lookup
    final_df = final_df.with_columns(
        pl.col("Team_Abbr").replace(sc_to_nickname).alias("Team")
    )

    # Add Park Factors
    final_df = final_df.with_columns(
        pl.col("Team")
        .map_elements(get_park_factor, return_dtype=pl.Float64)
        .alias("Park_Factor")
    )

    # Round results
    final_df = final_df.with_columns(
        [
            pl.col("Avg_Runs_For").round(2),
            pl.col("Avg_Runs_Against").round(2),
            pl.col("wOBA_vs_LHP").round(3),
            pl.col("wOBA_vs_RHP").round(3),
        ]
    )

    return final_df.select(
        [
            "Team",
            "Team_Abbr",
            "Avg_Runs_For",
            "Avg_Runs_Against",
            "Runs_L10",
            "wOBA_vs_LHP",
            "wOBA_vs_RHP",
            "Park_Factor",
        ]
    )


def get_default_year() -> int:
    """
    Returns the current year if the date is after March 25th, otherwise the previous year.
    """
    today = datetime.now()
    if today.month > 3 or (today.month == 3 and today.day >= 25):
        return today.year
    return today.year - 1


if __name__ == "__main__":
    default_year = get_default_year()
    try:
        results = get_team_stats(default_year)
        with pl.Config(tbl_cols=20, tbl_rows=50):
            print(f"Team Stats for {default_year}:")
            print(results.sort("Avg_Runs_For", descending=True))
    except Exception as e:
        print(f"Error: {e}")
