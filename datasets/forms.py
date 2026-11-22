from django import forms
from django.conf import settings

from .inspect import accept_attribute, allowed_extensions_text, inspect_upload
from .models import Category, Dataset


class DatasetForm(forms.ModelForm):
    """Used by specialists to upload a new dataset or fix a returned one."""

    class Meta:
        model = Dataset
        fields = (
            "title", "summary", "description", "organization", "category", "keywords", "coverage_area",
            "source", "data_date", "license", "access_level", "disclaimer", "file", "thumbnail",
        )
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "disclaimer": forms.Textarea(attrs={"rows": 2}),
            "data_date": forms.DateInput(attrs={"type": "date"}),
            "file": forms.ClearableFileInput(attrs={"accept": accept_attribute()}),
            "thumbnail": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {
            "file": "Any common GIS format: shapefile, File Geodatabase, GeoPackage, GeoTIFF, ArcGIS/QGIS packages and more. "
                    "Zip folders first (shapefile parts, .gdb folders, ESRI Grids).",
            "thumbnail": "Optional preview image (PNG/JPG) shown in the catalog.",
            "organization": "The institution that produced the data (shown as publisher). "
                            "Add new institutions in Admin → Government institutions.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.detected = {}
        self.fields["organization"].label = "Source institution"
        self.fields["organization"].queryset = self.fields["organization"].queryset.filter(is_active=True)
        if self.instance.pk:
            self.fields["file"].required = False

    def clean_file(self):
        f = self.cleaned_data.get("file")
        # Only a fresh upload has content_type; an unchanged stored file does not.
        if f and hasattr(f, "content_type"):
            if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                raise forms.ValidationError(f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit.")
            self.detected = inspect_upload(f)
        return f

    def clean_thumbnail(self):
        t = self.cleaned_data.get("thumbnail")
        if t and hasattr(t, "content_type") and t.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Thumbnail must be under 5 MB.")
        return t


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approve", "Approve & publish"), ("reject", "Request changes")])
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    feature = forms.BooleanField(required=False, label="Feature on the homepage")

    def clean(self):
        data = super().clean()
        if data.get("decision") == "reject" and not data.get("note"):
            raise forms.ValidationError("Please explain what needs to change.")
        return data


class CatalogFilterForm(forms.Form):
    q = forms.CharField(required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, to_field_name="slug")
    data_type = forms.ChoiceField(choices=[("", "All types")] + list(Dataset.DataType.choices), required=False)
    organization = forms.CharField(required=False)
    sort = forms.ChoiceField(
        choices=[("new", "Newest"), ("popular", "Most downloaded"), ("title", "Title A–Z")], required=False
    )
