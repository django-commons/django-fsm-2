from __future__ import annotations

from django import forms

from .models import AdminBlogPost


class AdminBlogPostRenameForm(forms.Form):
    """
    This form is used to test the admin form renaming functionality.
    """

    new_title = forms.CharField(
        label="New Title",
        max_length=255,
        required=True,
    )


class AdminBlogPostRenameModelForm(forms.ModelForm[AdminBlogPost]):
    """
    This form is used to test the admin form renaming functionality.
    """

    title = forms.CharField(
        label="New Title",
        max_length=255,
        required=True,
    )

    class Meta:
        model = AdminBlogPost
        fields: list[str] = []
