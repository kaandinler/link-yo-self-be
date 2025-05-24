from datetime import datetime, timezone

def utcnow():
    """Get current UTC time with timezone information"""
    return datetime.now(timezone.utc)

def format_datetime(dt):
    """Format a datetime to ISO 8601 format with timezone"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()