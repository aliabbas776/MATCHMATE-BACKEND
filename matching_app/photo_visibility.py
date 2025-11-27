from __future__ import annotations

from typing import Any, Dict, Optional, Set

from django.db.models import Q

from .models import UserConnection, UserProfile


class ProfilePhotoVisibilityHelper:
    """
    Computes whether a viewer is allowed to see another user's profile photo.
    """

    def __init__(self, viewer=None):
        self.viewer = viewer
        self._connected_user_ids: Optional[Set[int]] = None

    @property
    def _viewer_id(self) -> Optional[int]:
        if not self.viewer or getattr(self.viewer, 'is_anonymous', False):
            return None
        return getattr(self.viewer, 'id', None)

    def can_view(self, profile: UserProfile) -> bool:
        if not profile.profile_picture:
            return False
        if profile.is_public:
            return True
        viewer_id = self._viewer_id
        if viewer_id is None:
            return False
        if profile.user_id == viewer_id:
            return True
        return profile.user_id in self._approved_connection_ids

    @property
    def _approved_connection_ids(self) -> Set[int]:
        if self._connected_user_ids is None:
            self._connected_user_ids = self._fetch_connection_ids()
        return self._connected_user_ids

    def _fetch_connection_ids(self) -> Set[int]:
        viewer_id = self._viewer_id
        if viewer_id is None:
            return set()
        connections = UserConnection.objects.filter(
            status=UserConnection.Status.APPROVED,
        ).filter(
            Q(from_user_id=viewer_id) | Q(to_user_id=viewer_id)
        )
        connected: Set[int] = set()
        for from_id, to_id in connections.values_list('from_user_id', 'to_user_id'):
            if from_id != viewer_id:
                connected.add(from_id)
            if to_id != viewer_id:
                connected.add(to_id)
        return connected


def get_photo_visibility_helper(
    context: Optional[Dict[str, Any]] = None,
    viewer_override=None,
) -> ProfilePhotoVisibilityHelper:
    """
    Return a cached helper for the serializer/view context.
    """
    if context is None:
        return ProfilePhotoVisibilityHelper(viewer_override)

    cache_key = '_photo_visibility_helper'
    cached = context.get(cache_key)
    if cached:
        return cached

    request = context.get('request') if context else None
    viewer = viewer_override
    if viewer is None and request is not None:
        viewer = getattr(request, 'user', None)

    helper = ProfilePhotoVisibilityHelper(viewer)
    context[cache_key] = helper
    return helper


def resolve_profile_picture_url(
    profile: UserProfile,
    request,
    helper: ProfilePhotoVisibilityHelper,
) -> Optional[str]:
    """
    Return an absolute/relative URL for the profile photo if allowed.
    """
    if not profile.profile_picture:
        return None
    if not helper.can_view(profile):
        return None
    url = profile.profile_picture.url
    if request is not None:
        return request.build_absolute_uri(url)
    return url

