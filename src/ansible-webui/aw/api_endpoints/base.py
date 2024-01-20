from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework_api_key.permissions import BaseHasAPIKey

from aw.model.api import AwAPIKey


class HasAwAPIKey(BaseHasAPIKey):
    model = AwAPIKey


API_PERMISSION = [IsAuthenticated | HasAwAPIKey]


# see: rest_framework_api_key.permissions.BaseHasAPIKey:get_from_header
def get_api_user(request) -> settings.AUTH_USER_MODEL:
    if isinstance(request.user, AnonymousUser):
        try:
            return AwAPIKey.objects.get_from_key(
                request.META.get(getattr(settings, 'API_KEY_CUSTOM_HEADER'))
            ).user

        except ObjectDoesNotExist:
            # invalid api key
            pass

    return request.user


class BaseResponse(serializers.Serializer):

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass