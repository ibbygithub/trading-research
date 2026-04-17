import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib
from typing import Optional

def get_trials_file(runs_root: Path) -> Path:
    return runs_root / ".trials.json"

def record_trial(runs_root: Path, strategy_id: str, config_path: Path, sharpe: float, trial_group: Optional[str] = None) -> None:
    tf = get_trials_file(runs_root)
    trials = []
    if tf.exists():
        with open(tf, "r") as f:
            try: trials = json.load(f)
            except Exception: pass
            
    config_hash = ""
    if config_path.exists():
        config_hash = hashlib.md5(config_path.read_bytes()).hexdigest()
        
    trials.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "config_hash": config_hash,
        "sharpe": float(sharpe) if sharpe is not None else float("nan"),
        "trial_group": trial_group or strategy_id
    })
    
    tf.parent.mkdir(parents=True, exist_ok=True)
    with open(tf, "w") as f:
        json.dump(trials, f, indent=2)

def count_trials(runs_root: Path, strategy_id: str) -> int:
    tf = get_trials_file(runs_root)
    if not tf.exists(): return 1
    try:
        with open(tf, "r") as f: trials = json.load(f)
        cnt = sum(1 for t in trials if t.get("strategy_id") == strategy_id or t.get("trial_group") == strategy_id)
        return cnt if cnt > 0 else 1
    except Exception: return 1
