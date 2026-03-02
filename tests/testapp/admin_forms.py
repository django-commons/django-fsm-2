from __future__ import annotations

from django import forms

from .models import AdminBlogPost
from .models import AdminBlogPostState


class FSMLogDescription(forms.Form):
    # fsm log field
    description = forms.CharField(
        label="Comment",
        widget=forms.Textarea,
        required=True,
        help_text="Why are you updating the title",
    )


class ForceStateForm(FSMLogDescription):
    state = forms.ChoiceField(
        choices=AdminBlogPostState.choices,
        required=True,
    )


class AdminBlogPostRenameForm(forms.Form):
    """
    This form is used to test the admin form renaming functionality.
    """

    title = forms.CharField(
        label="New Title",
        max_length=255,
        required=True,
    )

    comment = forms.CharField(
        label="Comment",
        widget=forms.Textarea,
        required=True,
        help_text="Why are you updating the title",
    )

    # fsm log field
    description = forms.CharField(
        label="Comment",
        widget=forms.Textarea,
        required=True,
        help_text="Why are you updating the title",
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

    # fsm log field
    description = forms.CharField(
        label="Comment",
        widget=forms.Textarea,
        required=True,
        help_text="Why are you updating the title",
    )

    class Meta:
        model = AdminBlogPost
        fields: list[str] = ["title"]
