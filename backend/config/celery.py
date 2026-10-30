import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("securedocs")
# Read every setting that starts with CELERY_ from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")
# Find tasks.py files inside our apps automatically
app.autodiscover_tasks()
