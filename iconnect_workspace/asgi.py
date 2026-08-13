"""ASGI do iConnect Workspace."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iconnect_workspace.settings.prod")

application = get_asgi_application()
