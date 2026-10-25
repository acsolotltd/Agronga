import time

from django import forms

from .countries import COUNTRIES
from django.core import signing

from .models import Product

FIELD = "input"
MIN_SECONDS, MAX_SECONDS = 3, 60 * 60 * 6


class SpamTrapForm(forms.Form):
    """Styling + signed time trap. The honeypot field and rate limit live in the view helper."""

    ts = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.HiddenInput):
                f.widget.attrs["class"] = FIELD
        if "email" in self.fields:
            self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email")
        if "name" in self.fields:
            self.fields["name"].widget.attrs.update(autocomplete="name")
        if not self.is_bound:
            self.fields["ts"].initial = signing.dumps(time.time(), salt="quote")

    def clean(self):
        data = super().clean()
        try:
            age = time.time() - signing.loads(data.get("ts", ""), salt="quote", max_age=MAX_SECONDS)
        except signing.BadSignature:
            raise forms.ValidationError("This form has expired. Reload the page and try again.")
        if age < MIN_SECONDS:
            raise forms.ValidationError("That was quick. Please check your details and send again.")
        return data


class QuoteForm(SpamTrapForm):
    name = forms.CharField(max_length=80, error_messages={"required": "Enter your name."})
    email = forms.EmailField(error_messages={"required": "Enter your email.", "invalid": "Enter a valid email address."})
    country = forms.ChoiceField(choices=[("NG", "Nigeria"), ("US", "United States"), ("OT", "Another country")])
    product = forms.ChoiceField(choices=[])
    quantity = forms.CharField(max_length=60, required=False)
    message = forms.CharField(max_length=1500, required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].choices = (
            [(p.slug, p.name) for p in Product.objects.filter(is_active=True)] + [("other", "Something else")]
        )


TOPICS = [("general", "A general question"), ("quote", "A bulk or export quote"), ("order", "Help with an order")]


class ContactForm(SpamTrapForm):
    name = forms.CharField(max_length=80, error_messages={"required": "Enter your name."})
    email = forms.EmailField(error_messages={"required": "Enter your email.", "invalid": "Enter a valid email address."})
    topic = forms.ChoiceField(choices=TOPICS)
    message = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 6}),
                              error_messages={"required": "Tell us how we can help."})


class OrderForm(SpamTrapForm):
    """Order request. The cart arrives as JSON in `cart`; prices are NEVER taken from it."""

    name = forms.CharField(max_length=80, error_messages={"required": "Enter your name."})
    email = forms.EmailField(error_messages={"required": "Enter your email.", "invalid": "Enter a valid email address."})
    phone = forms.CharField(max_length=30, error_messages={"required": "Enter a phone number we can call."})
    country = forms.ChoiceField(choices=COUNTRIES)
    address = forms.CharField(max_length=300, error_messages={"required": "Enter the delivery address."},
                              widget=forms.Textarea(attrs={"rows": 3}))
    notes = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    cart = forms.CharField(widget=forms.HiddenInput)
    expected_total = forms.CharField(required=False, widget=forms.HiddenInput)   # total the buyer saw; server refuses if it moved
