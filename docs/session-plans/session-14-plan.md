# Session 14: The Dynamic Strategy Builder

**Status:** Planning Phase
**Objective:** Transition the Dash GUI from a static script runner into an interactive parameter sandbox without introducing look-ahead bias or overfitting vectors.

---

## Architectural Debate: How Do We Build This?

### 🗣️ The Quant Mentor (Market Structure & Risk)
*"Look, Ibby, keep it simple. If you build a drag-and-drop 'Rule Engine' where you can plug RSI into MACD into Bollinger Bands on the fly, you aren't building a trading desk—you're building a curve-fitting video game. You'll spend hours combining random indicators until you find a magic combination that made 400% last year, and then you'll take it live and get slaughtered because it was pure noise.*

*My vote: **Parameterization only**. We stick to the robust templates we've already written in Python (like `zn_macd_pullback`). The GUI's only job should be to expose the specific math parameters—MACD lengths, ATR multipliers, required streak bars. You use the GUI to tweak the dials and stress-test the robustness of a known strategy, not to hunt for magic formulas."*

### 🔬 The Data Scientist (Statistical Integrity)
*"I agree with the Mentor, but for different reasons. My primary concern is leakage and state management.* 

*If we allow dynamic rule creation in the UI, we bypass the strict DataFrame vectorization and validation we built into `src/trading_research/strategies/`. If we stick to 'Parameterization' (Option A), the UI simply passes a `signal_params` dictionary down to our isolated, tested Python modules. This guarantees that look-ahead prevention (like the `shift(1)` on the 60m HTF bias) remains completely intact regardless of what the user clicks.*

*We must also ensure that the default values populated in the GUI are strictly the ones we validated in previous sessions. If you change a parameter in the GUI, it is a new hypothesis and must be tested across out-of-sample folds."*

---

## The Consensus Plan (Option A)

Based on the need for both market robustness (Mentor) and pipeline integrity (Data Scientist), we will proceed with **Option A: Parameter Optimization UI**. 

### 1. The Schema Registry (`schemas.py`)
We will create a strict dictionary mapping our Python modules to their allowed parameters. The Data Scientist approves this because it strictly bounds what can be manipulated.
```python
STRATEGY_SCHEMAS = {
    "trading_research.strategies.zn_macd_pullback": [
        {"id": "macd_fast", "label": "MACD Fast", "default": 12, "type": "number"},
        {"id": "macd_slow", "label": "MACD Slow", "default": 26, "type": "number"},
        # ...
    ]
}
```

### 2. The UI Renderer (`app.py` & `callbacks.py`)
We will add a dynamic Panel to Dash. When you select a strategy, it reads `schemas.py` and renders the exact input boxes required. No code generation, just pure parameter injection.

### 3. Execution Wiring
We will use Dash's `ALL` pattern-matching to scrape the values from the UI and pass them into the `run_walkforward` engine via the `signal_params` dict.

## Next Steps for Tomorrow
When you boot up the IDE tomorrow, you can point me to this exact file (`docs/session-plans/session-14-plan.md`). 
Tell me to *"Execute Session 14"*, and I will build this exact architecture.
