from rest_framework.permissions import BasePermission


class IsAdminOrHR(BasePermission):

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        if not request.user.role:
            return False

        allowed_roles = ['ADMIN', 'HR']

        return request.user.role.code in allowed_roles