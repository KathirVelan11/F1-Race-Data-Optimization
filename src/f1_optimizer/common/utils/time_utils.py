"""Time conversion and formatting utilities for F1 lap times."""
import re
from typing import Optional


def lap_time_str_to_seconds(lap_time: str) -> Optional[float]:
    """Convert lap time string (e.g. '1:28.176' or '88.176') to float seconds."""
    if not isinstance(lap_time, str) or not lap_time.strip():
        return None
    lap_time = lap_time.strip()
    match = re.match(r"(?:(\d+):)?(\d+(?:\.\d+)?)", lap_time)
    if not match:
        return None
    minutes_str, seconds_str = match.groups()
    minutes = float(minutes_str) if minutes_str else 0.0
    seconds = float(seconds_str)
    return minutes * 60.0 + seconds


def seconds_to_lap_time_str(total_seconds: float) -> str:
    """Convert float seconds to 'M:SS.sss' or 'H:MM:SS.sss' format."""
    if total_seconds < 0:
        return "0:00.000"
    hours = int(total_seconds // 3600)
    remainder = total_seconds % 3600
    minutes = int(remainder // 60)
    seconds = remainder % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:06.3f}"
    return f"{minutes}:{seconds:06.3f}"
