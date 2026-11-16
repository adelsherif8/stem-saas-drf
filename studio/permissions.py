from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level check: only the owner may see or change an object.

    The viewsets also filter their querysets by owner, so another user's ids
    return 404 (not 403) and cannot be probed, the same rule the FastAPI app
    applies to jobs. This class is the second line of defence in case a
    queryset is ever widened.
    """

    message = "You do not own this object."

    def has_object_permission(self, request, view, obj) -> bool:
        return getattr(obj, "owner_id", None) == request.user.id
