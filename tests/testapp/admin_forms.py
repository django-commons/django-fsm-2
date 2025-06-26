from __future__ import annotations

from django import forms

from .models import AdminBlogPost


class AdminBlogPostRenameForm(forms.ModelForm):
    """
    This form is used to test the admin form renaming functionality.
    It should not be used in production.
    """

    class Meta:
        model = AdminBlogPost
        fields = ["title"]  # Do not try to update the state field, especially if it's "protected" in the model.
