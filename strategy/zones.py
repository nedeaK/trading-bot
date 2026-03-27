import pandas as pd

def detect_zones(df: pd.DataFrame):
    """
    Detects Supply and Demand Zones based on:
    1. Indecision candle (small body, relatively large wicks).
    2. Impulse move immediately following.
    3. Imbalance (open price gap between indecision and subsequent price action).
    """
    pass
