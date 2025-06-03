from __future__ import annotations

from django import forms


class AdminBlogPostRenameForm(forms.Form):
    """
    This form is used to test the admin form renaming functionality.
    """

    new_title = forms.CharField(
        label="New Title",
        max_length=255,
        required=True,
    )
