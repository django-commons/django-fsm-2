from __future__ import annotations

from django import forms


class RejectionForm(forms.Form):
    """Form for rejecting posts with a reason."""

    reason = forms.CharField(
        widget=forms.Textarea,
        help_text="Please provide a reason for rejection.",
        required=True,
    )
