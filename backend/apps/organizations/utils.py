import uuid

from django.utils.text import slugify

from .models import Organization


def unique_slug(name):
    """Make a URL-friendly name that no other organization uses."""
    base = slugify(name)[:60] or "org"
    slug = base
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
    return slug
