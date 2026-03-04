def format_seconds(total_seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    total = int(total_seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_hours_minutes(total_seconds: float) -> str:
    """Format seconds into a human-readable 'Xh Ym' string."""
    total = int(total_seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
