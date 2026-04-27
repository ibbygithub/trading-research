"""Core typed interfaces: Instrument, FeatureSet, Strategy, and their registries.

Import from here, not from the submodules directly.
"""

from trading_research.core.featuresets import FeatureSet, FeatureSetRegistry, FeatureSpec
from trading_research.core.instruments import Instrument, InstrumentRegistry
from trading_research.core.strategies import (
    ExitDecision,
    PortfolioContext,
    Position,
    Signal,
    Strategy,
)
from trading_research.core.templates import (
    StrategyTemplate,
    TemplateRegistry,
    register_template,
)

__all__ = [
    # Instrument
    "Instrument",
    "InstrumentRegistry",
    # FeatureSet
    "FeatureSet",
    "FeatureSetRegistry",
    "FeatureSpec",
    # Strategy value types
    "ExitDecision",
    "PortfolioContext",
    "Position",
    "Signal",
    # Strategy Protocol
    "Strategy",
    # Template system
    "StrategyTemplate",
    "TemplateRegistry",
    "register_template",
]
