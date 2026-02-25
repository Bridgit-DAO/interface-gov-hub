# Copyright The IETF Trust. Serves test/draft pages (e.g. Civic Digital Artifacts).
from django.conf import settings
from django.http import Http404, HttpResponse
import os


def draft_digitalartifacts(request):
    """Serve datatracker/drafts/digitalartifacts.htm as text/html."""
    path = os.path.join(settings.PROJECT_DIR, "drafts", "digitalartifacts.htm")
    if not os.path.isfile(path):
        raise Http404("Draft page not found.")
    with open(path, "rb") as f:
        return HttpResponse(f.read(), content_type="text/html; charset=utf-8")
