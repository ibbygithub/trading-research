import pytest
from trading_research.eval.trials import count_trials, record_trial
import tempfile
from pathlib import Path

def test_trials_registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        record_trial(root, "my_strat", Path("dummy.yaml"), 1.5)
        record_trial(root, "my_strat", Path("dummy.yaml"), 1.6)
        
        count = count_trials(root, "my_strat")
        assert count == 2
