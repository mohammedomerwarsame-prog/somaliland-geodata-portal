from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def specialist_required(view_func):
    """Only portal team members (specialists/reviewers) or superusers."""

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.can_upload:
            messages.info(
                request,
                "Uploading is done by the portal team. Send us your data and we will publish it for you.",
            )
            return redirect("datasets:share")
        return view_func(request, *args, **kwargs)

    return _wrapped


def reviewer_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.can_review:
            messages.error(request, "Only data reviewers can access the review queue.")
            return redirect("datasets:home")
        return view_func(request, *args, **kwargs)

    return _wrapped
