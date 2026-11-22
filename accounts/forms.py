from django import forms
from django.contrib.auth.forms import UserCreationForm

from organizations.models import Organization

from .models import SpecialistRequest, User


class SignUpForm(UserCreationForm):
    """Public registration. Always creates a PUBLIC account."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PUBLIC
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "job_title", "phone")


class SpecialistRequestForm(forms.ModelForm):
    organization = forms.ModelChoiceField(queryset=Organization.objects.filter(is_active=True))

    class Meta:
        model = SpecialistRequest
        fields = ("organization", "job_title", "work_email", "justification")
        widgets = {"justification": forms.Textarea(attrs={"rows": 4})}
