
"""
dirshot - A flexible, high-performance utility for creating project snapshots 
and searching files with a rich terminal UI.
"""

from .dirshot import (
    generate_snapshot,
    LanguagePreset,
    IgnorePreset,
)

__all__ = [
    # The primary function for all scanning and snapshot operations.
    "generate_snapshot",
    
    # Enums for easy configuration of scanning criteria.
    "LanguagePreset",
    "IgnorePreset",
]

__version__ = "0.2.0"