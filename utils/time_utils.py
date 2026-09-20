from datetime import UTC, datetime


def utcnow():
    """Get current UTC time with timezone information"""
    return datetime.now(UTC)


def format_datetime(dt):
    """Format a datetime to ISO 8601 format with timezone"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()
