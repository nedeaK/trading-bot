"""Position sizing using fixed percentage risk model.

Risk a fixed percentage of account equity per trade.
Position size = (equity * risk_percent) / risk_per_share.
"""


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_loss: float,
    risk_percent: float = 0.02,
    max_position_pct: float = 0.2,
) -> int:
    """Calculate position size (number of shares).

    Args:
        equity: Current account equity.
        entry_price: Entry price per share.
        stop_loss: Stop loss price per share.
        risk_percent: Fraction of equity to risk (0.02 = 2%).
        max_position_pct: Maximum fraction of equity in one position.

    Returns:
        Number of shares to trade (integer, minimum 0).
    """
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share == 0:
        return 0

    risk_amount = equity * risk_percent
    shares_from_risk = risk_amount / risk_per_share

    # Cap by max position size
    max_shares = (equity * max_position_pct) / entry_price if entry_price > 0 else 0

    return max(0, int(min(shares_from_risk, max_shares)))
