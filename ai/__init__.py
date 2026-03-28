"""AI reasoning layer for the SMC Trading Bot.

Two implementations:
- HeuristicAnalyst  : fast rule-based scoring, used in backtesting
- ClaudeAnalyst     : Claude API reasoning, used for live trading
"""
from ai.heuristic_analyst import HeuristicAnalyst
from ai.analyst import ClaudeAnalyst

__all__ = ["HeuristicAnalyst", "ClaudeAnalyst"]
