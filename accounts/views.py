from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, SignUpForm, SpecialistRequestForm
from .models import SpecialistRequest


def signup(request):
    if request.user.is_authenticated:
        return redirect("datasets:home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome! Your account is ready. You can now browse and download data.")
        return redirect("datasets:home")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    requests_ = request.user.specialist_requests.select_related("organization")
    return render(request, "accounts/profile.html", {"form": form, "specialist_requests": requests_})


@login_required
def request_specialist(request):
    if request.user.can_upload:
        return redirect("datasets:upload")
    pending = request.user.specialist_requests.filter(status=SpecialistRequest.Status.PENDING).first()
    form = SpecialistRequestForm(request.POST or None)
    if request.method == "POST" and not pending and form.is_valid():
        req = form.save(commit=False)
        req.user = request.user
        req.save()
        messages.success(request, "Your request has been sent. An administrator will review it.")
        return redirect("accounts:profile")
    return render(request, "accounts/request_specialist.html", {"form": form, "pending": pending})
