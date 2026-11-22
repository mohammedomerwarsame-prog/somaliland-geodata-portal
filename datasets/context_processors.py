from django.conf import settings

from .models import Dataset


def portal(request):
    ctx = {
        "PORTAL_NAME": settings.PORTAL_NAME,
        "PORTAL_TAGLINE": settings.PORTAL_TAGLINE,
        "PORTAL_ORGANIZATION": settings.PORTAL_ORGANIZATION,
        "CONTRIBUTE_TELEGRAM_URL": settings.CONTRIBUTE_TELEGRAM_URL,
        "CONTRIBUTE_TELEGRAM_HANDLE": settings.CONTRIBUTE_TELEGRAM_HANDLE,
        "CONTRIBUTE_EMAIL": settings.CONTRIBUTE_EMAIL,
        "CONTRIBUTE_PHONE": settings.CONTRIBUTE_PHONE,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.can_review:
        ctx["pending_review_count"] = Dataset.objects.filter(status=Dataset.Status.PENDING).count()
    return ctx
