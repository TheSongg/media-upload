import logging
import re

from rest_framework.decorators import action
from rest_framework.response import Response
from media_upload.utils.base_views import BaseViewSet

from django.db import transaction



logger = logging.getLogger("upload")


class RedBookUpdateViewSet(BaseViewSet):
    pass
