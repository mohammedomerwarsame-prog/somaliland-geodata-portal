from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def specialist_required(view_func):
    """Only specialists/reviewers attached to an institution (or superusers)."""

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.can_upload:
            messages.warning(
                request,
                "Uploading is limited to approved GIS specialists of government institutions. "
                "You can request specialist access below.",
            )
            return redirect("accounts:request_specialist")
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
