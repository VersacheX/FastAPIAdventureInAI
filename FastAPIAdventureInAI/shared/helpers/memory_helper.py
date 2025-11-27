"""
Lightweight helpers related to memory handling.
"""
from typing import List, Optional


def get_recent_memories(memory_log, limit: Optional[int] = None):
    """Get the most recent items from a memory log.

    Kept intentionally minimal and free of other service imports to avoid
    circular import issues between the ai package and services modules.
    """
    if limit is None:
        return memory_log
    return memory_log[-limit:]
