"""Definitions for Strategy Parameters exposed to the GUI."""

STRATEGY_SCHEMAS = {
    "trading_research.strategies.zn_macd_pullback": [
        {"id": "macd_fast", "label": "MACD Fast Period", "default": 12, "type": "number"},
        {"id": "macd_slow", "label": "MACD Slow Period", "default": 26, "type": "number"},
        {"id": "macd_signal_period", "label": "MACD Signal Period", "default": 9, "type": "number"},
        {"id": "atr_stop_mult", "label": "ATR Stop Multiplier", "default": 2.0, "type": "number", "step": 0.1},
        {"id": "streak_bars", "label": "Pullback Streak Bars", "default": 3, "type": "number"}
    ]
}
