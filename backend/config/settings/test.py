from .dev import *  # noqa: F401,F403

# Run tasks inline and never talk to the real broker during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_BROKER_USE_SSL = None
