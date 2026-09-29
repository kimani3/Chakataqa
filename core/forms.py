from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "organisation", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "organisation": forms.TextInput(
                attrs={"placeholder": "Company, school or estate (optional)"}
            ),
            "message": forms.Textarea(
                attrs={"rows": 4, "placeholder": "How can we help?"}
            ),
        }
