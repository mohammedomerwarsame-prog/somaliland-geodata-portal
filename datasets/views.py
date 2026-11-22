import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import reviewer_required, specialist_required
from organizations.models import Organization

from .forms import CatalogFilterForm, DatasetForm, ReviewForm
from .models import Category, Dataset, DownloadLog

TECH_FIELDS = ("file_format", "data_type", "file_size", "crs", "feature_count",
               "min_lon", "min_lat", "max_lon", "max_lat")


CATEGORY_ICONS = {
    "boundaries": "bi-bounding-box",
    "roads": "bi-sign-turn-right",
    "water": "bi-droplet-half",
    "elevation": "bi-triangle",
    "land-cover": "bi-tree",
    "imagery": "bi-globe-americas",
    "settlements": "bi-buildings",
    "agriculture": "bi-flower1",
    "services": "bi-hospital",
    "environment": "bi-cloud-sun",
}


# ---------------------------------------------------------------- public pages

def home(request):
    visible = Dataset.objects.visible_to(request.user).select_related("organization", "category")
    featured = list(visible.filter(is_featured=True)[:4])
    if len(featured) < 4:
        featured += list(visible.exclude(pk__in=[d.pk for d in featured])[: 4 - len(featured)])

    published = Dataset.objects.published()
    stats = {
        "datasets": published.count(),
        "institutions": Organization.objects.filter(datasets__status=Dataset.Status.PUBLISHED).distinct().count(),
        "downloads": published.aggregate(total=Sum("download_count"))["total"] or 0,
        "themes": Category.objects.filter(datasets__status=Dataset.Status.PUBLISHED).distinct().count(),
    }
    institutions = (
        Organization.objects.filter(is_active=True)
        .annotate(n=Count("datasets", filter=Q(datasets__status=Dataset.Status.PUBLISHED)))
        .order_by("-n", "name")[:8]
    )
    categories = Category.objects.annotate(
        n=Count("datasets", filter=Q(datasets__status=Dataset.Status.PUBLISHED))
    )
    themes = [(c, CATEGORY_ICONS.get(c.slug, "bi-layers")) for c in categories]
    return render(request, "home.html", {
        "featured": featured,
        "stats": stats,
        "institutions": institutions,
        "categories": categories[:6],
        "themes": themes,
        "recent": visible.order_by("-published_at")[:5],
    })


def catalog(request):
    form = CatalogFilterForm(request.GET or None)
    qs = Dataset.objects.visible_to(request.user).select_related("organization", "category")
    if form.is_valid():
        d = form.cleaned_data
        if d.get("q"):
            q = d["q"]
            qs = qs.filter(
                Q(title__icontains=q) | Q(summary__icontains=q) | Q(keywords__icontains=q)
                | Q(coverage_area__icontains=q) | Q(organization__name__icontains=q)
            )
        if d.get("category"):
            qs = qs.filter(category=d["category"])
        if d.get("data_type"):
            qs = qs.filter(data_type=d["data_type"])
        if d.get("organization"):
            qs = qs.filter(organization__slug=d["organization"])
        qs = {"popular": qs.order_by("-download_count"), "title": qs.order_by("title")}.get(d.get("sort"), qs)

    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "datasets/catalog.html", {
        "form": form,
        "page": page,
        "categories": Category.objects.annotate(
            n=Count("datasets", filter=Q(datasets__status=Dataset.Status.PUBLISHED))
        ),
        "organizations": Organization.objects.filter(datasets__status=Dataset.Status.PUBLISHED).distinct(),
        "querystring": params.urlencode(),
    })


def detail(request, slug):
    ds = get_object_or_404(Dataset.objects.select_related("organization", "category", "uploaded_by"), slug=slug)
    if not ds.can_be_viewed_by(request.user):
        raise Http404
    return render(request, "datasets/detail.html", {
        "ds": ds,
        "can_download": ds.can_be_downloaded_by(request.user),
        "can_edit": ds.can_be_edited_by(request.user),
        "review_form": ReviewForm() if request.user.is_authenticated and request.user.can_review
        and ds.status == Dataset.Status.PENDING else None,
        "related": Dataset.objects.visible_to(request.user).filter(category=ds.category).exclude(pk=ds.pk)[:3],
    })


def download(request, slug):
    ds = get_object_or_404(Dataset, slug=slug)
    if not ds.can_be_viewed_by(request.user):
        raise Http404
    if not ds.can_be_downloaded_by(request.user):
        messages.info(request, "Please log in or register to download this dataset.")
        return redirect_to_login(ds.get_absolute_url())
    try:
        fh = ds.file.open("rb")
    except FileNotFoundError:
        raise Http404("File missing on the server.")
    if ds.status == Dataset.Status.PUBLISHED:
        Dataset.objects.filter(pk=ds.pk).update(download_count=F("download_count") + 1)
        DownloadLog.objects.create(dataset=ds, user=request.user if request.user.is_authenticated else None)
    ext = os.path.splitext(ds.file.name)[1]
    return FileResponse(fh, as_attachment=True, filename=f"{ds.slug}{ext}")


def map_viewer(request):
    layers = Dataset.objects.visible_to(request.user).select_related("organization")
    focus = request.GET.get("dataset")
    return render(request, "datasets/map.html", {"layers": layers, "focus": focus})


def dataset_geojson(request, slug):
    """Feeds GeoJSON layers to the map viewer (small public datasets only)."""
    ds = get_object_or_404(Dataset, slug=slug)
    if not ds.can_be_viewed_by(request.user) or not ds.can_be_downloaded_by(request.user):
        raise Http404
    if not ds.can_preview_on_map:
        return JsonResponse({"error": "Preview not available for this dataset."}, status=415)
    return FileResponse(ds.file.open("rb"), content_type="application/geo+json")


def about(request):
    return render(request, "pages/about.html")


# ------------------------------------------------------------ specialist pages

@specialist_required
def upload(request):
    form = DatasetForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ds = form.save(commit=False)
        ds.uploaded_by = request.user
        ds.organization = request.user.organization
        ds.status = Dataset.Status.PENDING
        for key, value in form.detected.items():
            setattr(ds, key, value)
        if ds.organization is None:  # superuser without an institution
            messages.error(request, "Your account is not linked to an institution. Set one in the admin.")
            return redirect("datasets:upload")
        ds.save()
        messages.success(request, f"“{ds.title}” was submitted. A reviewer will check it before it is published.")
        return redirect("datasets:my_uploads")
    return render(request, "datasets/upload.html", {"form": form, "max_mb": settings.MAX_UPLOAD_MB})


@specialist_required
def edit(request, slug):
    ds = get_object_or_404(Dataset, slug=slug)
    if not ds.can_be_edited_by(request.user):
        messages.error(request, "Only pending or returned uploads can be edited, by the person who uploaded them.")
        return redirect(ds.get_absolute_url())
    form = DatasetForm(request.POST or None, request.FILES or None, instance=ds)
    if request.method == "POST" and form.is_valid():
        ds = form.save(commit=False)
        for key, value in form.detected.items():
            setattr(ds, key, value)
        ds.status = Dataset.Status.PENDING
        ds.save()
        messages.success(request, "Changes saved and re-submitted for review.")
        return redirect("datasets:my_uploads")
    return render(request, "datasets/upload.html", {"form": form, "ds": ds, "max_mb": settings.MAX_UPLOAD_MB})


@specialist_required
def my_uploads(request):
    uploads = request.user.uploads.select_related("category").order_by("-created_at")
    org_uploads = None
    if request.user.organization_id:
        org_uploads = Dataset.objects.filter(organization=request.user.organization).exclude(
            uploaded_by=request.user
        ).order_by("-created_at")[:20]
    return render(request, "datasets/my_uploads.html", {"uploads": uploads, "org_uploads": org_uploads})


# -------------------------------------------------------------- reviewer pages

@reviewer_required
def review_queue(request):
    pending = Dataset.objects.filter(status=Dataset.Status.PENDING).select_related(
        "organization", "uploaded_by", "category"
    ).order_by("created_at")
    recent = Dataset.objects.filter(reviewed_at__isnull=False).select_related("reviewed_by").order_by("-reviewed_at")[:10]
    return render(request, "datasets/review_queue.html", {"pending": pending, "recent": recent})


@reviewer_required
@require_POST
def review_action(request, slug):
    ds = get_object_or_404(Dataset, slug=slug, status=Dataset.Status.PENDING)
    if ds.uploaded_by_id == request.user.id and not request.user.is_superuser:
        messages.error(request, "You cannot approve your own upload. Another reviewer must check it.")
        return redirect(ds.get_absolute_url())
    form = ReviewForm(request.POST)
    if not form.is_valid():
        for err in form.non_field_errors():
            messages.error(request, err)
        return redirect(ds.get_absolute_url())
    with transaction.atomic():
        ds.review_note = form.cleaned_data["note"]
        ds.reviewed_by = request.user
        ds.reviewed_at = timezone.now()
        if form.cleaned_data["decision"] == "approve":
            ds.status = Dataset.Status.PUBLISHED
            ds.published_at = ds.published_at or timezone.now()
            ds.is_featured = form.cleaned_data["feature"]
            messages.success(request, f"“{ds.title}” is now published.")
        else:
            ds.status = Dataset.Status.REJECTED
            messages.info(request, f"“{ds.title}” was returned to the uploader.")
        ds.save()
    return redirect("datasets:review_queue")


@login_required
def dashboard(request):
    """Send each role to its main working page."""
    if request.user.can_review:
        return redirect("datasets:review_queue")
    if request.user.can_upload:
        return redirect("datasets:my_uploads")
    return redirect("datasets:catalog")
