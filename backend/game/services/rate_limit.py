"""Rate limiting service module.

Handles both daily rate limits (tier-based) and legacy per-minute limits.
Daily limits: Standard=20, Pro=500, Admin=1000, Global=4000
Per-minute limits: 4 user discoveries/min, 50 global API calls/min
"""

from django.conf import settings
from django.utils import timezone
from ..models import RateLimit


def is_admin_user(user):
    """Check if user is the admin testing account."""
    return user.username == "admin" and user.is_superuser


def get_daily_rate_limit(user):
    """Get the daily rate limit for a user based on their pro status."""
    # Admin always get their special limit
    if is_admin_user(user):
        return getattr(settings, "RATE_LIMIT_DAILY_ADMIN", 1000)

    profile = user.profile

    if profile.is_pro:
        return getattr(settings, "RATE_LIMIT_DAILY_PRO", 500)
    else:
        return getattr(settings, "RATE_LIMIT_DAILY_STANDARD", 20)


def check_daily_rate_limit(user):
    """Check if user has exceeded their daily rate limit.

    Returns (allowed: bool, remaining: int)
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count discoveries made today
    profile = user.profile
    rate_limit, created = RateLimit.objects.get_or_create(
        player=profile,
        limit_type="daily_discoveries",
        defaults={"window_start": today_start, "count": 0}
    )

    # Reset if we're in a new day
    if rate_limit.window_start.date() < today_start.date():
        rate_limit.count = 0
        rate_limit.window_start = today_start
        rate_limit.save()

    max_limit = get_daily_rate_limit(user)

    if rate_limit.count >= max_limit:
        return False, max_limit - rate_limit.count

    return True, max_limit - rate_limit.count


def check_global_daily_rate_limit():
    """Check if global daily API call limit has been exceeded.

    Returns (allowed: bool, remaining: int)
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get global rate limit tracker (player=None for global)
    rate_limit, created = RateLimit.objects.get_or_create(
        player=None,
        limit_type="global_daily_discoveries",
        defaults={"window_start": today_start, "count": 0}
    )

    # Reset if we're in a new day
    if rate_limit.window_start.date() < today_start.date():
        rate_limit.count = 0
        rate_limit.window_start = today_start
        rate_limit.save()

    max_limit = getattr(settings, "RATE_LIMIT_DAILY_GLOBAL", 4000)

    if rate_limit.count >= max_limit:
        return False, max_limit - rate_limit.count

    return True, max_limit - rate_limit.count


def increment_global_daily_rate_limit():
    """Increment global daily rate limit counter."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    rate_limit, created = RateLimit.objects.get_or_create(
        player=None,
        limit_type="global_daily_discoveries",
        defaults={"window_start": today_start, "count": 0}
    )

    # Reset if we're in a new day
    if rate_limit.window_start.date() < today_start.date():
        rate_limit.count = 0
        rate_limit.window_start = today_start

    rate_limit.count += 1
    rate_limit.save()


def increment_daily_rate_limit(user):
    """Increment daily rate limit counter."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    profile = user.profile
    rate_limit, created = RateLimit.objects.get_or_create(
        player=profile,
        limit_type="daily_discoveries",
        defaults={"window_start": today_start, "count": 0}
    )

    # Reset if we're in a new day
    if rate_limit.window_start.date() < today_start.date():
        rate_limit.count = 0
        rate_limit.window_start = today_start

    rate_limit.count += 1
    rate_limit.save()


def check_rate_limit(player, limit_type):
    """Check if rate limit is exceeded (legacy per-minute limit).

    Returns (allowed: bool, remaining: int)
    """
    now = timezone.now()

    rate_limit, _ = RateLimit.objects.get_or_create(
        player=player if limit_type == "user_discovery" else None,
        limit_type=limit_type,
        defaults={"window_start": now, "count": 0},
    )

    # Reset if window expired
    window = getattr(settings, "RATE_LIMIT_WINDOW", 60)  # seconds
    if (now - rate_limit.window_start).total_seconds() >= window:
        rate_limit.count = 0
        rate_limit.window_start = now
        rate_limit.save()

    max_limit = (
        getattr(settings, "RATE_LIMIT_USER_DISCOVERIES", 10)
        if limit_type == "user_discovery"
        else getattr(settings, "RATE_LIMIT_GLOBAL_API_CALLS", 100)
    )

    if rate_limit.count >= max_limit:
        return False, max_limit - rate_limit.count

    return True, max_limit - rate_limit.count


def increment_rate_limit(player, limit_type):
    """Increment rate limit counter (legacy per-minute limit)."""
    rate_limit, _ = RateLimit.objects.get_or_create(
        player=player if limit_type == "user_discovery" else None,
        limit_type=limit_type,
        defaults={"window_start": timezone.now(), "count": 0},
    )
    rate_limit.count += 1
    rate_limit.save()
