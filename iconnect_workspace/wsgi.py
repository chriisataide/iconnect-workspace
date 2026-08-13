"""WSGI do iConnect Workspace."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iconnect_workspace.settings.prod")

application = get_wsgi_application()
