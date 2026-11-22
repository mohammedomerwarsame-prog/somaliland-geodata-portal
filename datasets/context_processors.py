from django.conf import settings

from .models import Dataset


def portal(request):
    ctx = {"PORTAL_NAME": settings.PORTAL_NAME, "PORTAL_TAGLINE": settings.PORTAL_TAGLINE}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.can_review:
        ctx["pending_review_count"] = Dataset.objects.filter(status=Dataset.Status.PENDING).count()
    return ctx
