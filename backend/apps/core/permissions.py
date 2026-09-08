"""
Custom permission classes for the mPayhub platform.
"""
from rest_framework import permissions

from apps.users.hierarchy_policy import can_parent_create_child


class IsOwner(permissions.BasePermission):
    """
    Permission to only allow owners of an object to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Check if the object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # Check if the object is the user itself
        return obj == request.user


class IsRole(permissions.BasePermission):
    """
    Permission to check if user has a specific role.
    """
    
    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles if isinstance(allowed_roles, list) else [allowed_roles]
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in self.allowed_roles
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdmin(permissions.BasePermission):
    """
    Platform operator gate (Admin or Super Admin).

    Name kept as IsAdmin so existing view decorators stay valid.
    """

    def has_permission(self, request, view):
        from apps.core.roles import is_platform_operator

        return (
            request.user
            and request.user.is_authenticated
            and is_platform_operator(request.user)
        )


class IsSuperAdmin(permissions.BasePermission):
    """Super Admin only (vendor / developer operator)."""

    def has_permission(self, request, view):
        from apps.core.roles import is_super_admin

        return (
            request.user
            and request.user.is_authenticated
            and is_super_admin(request.user)
        )


class IsMasterDistributorOrAbove(permissions.BasePermission):
    """Permission for Master Distributor and above (includes Super Distributor and operators)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
            'Super Admin',
            'Admin',
            'Super Distributor',
            'Master Distributor',
        ]


class IsDistributorOrAbove(permissions.BasePermission):
    """Permission for Distributor and above."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
            'Super Admin',
            'Admin',
            'Super Distributor',
            'Master Distributor',
            'Distributor',
        ]


class IsHierarchy(permissions.BasePermission):
    """
    Permission to check if user can access resources based on hierarchy onboarding policy.
    Admin: all roles below; each upline role may access direct-report role types per hierarchy_policy.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        from apps.core.roles import is_platform_operator

        # Platform operators can access everything
        if is_platform_operator(request.user):
            return True

        # For other roles, check is done at object level
        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        from apps.core.roles import is_platform_operator

        if is_platform_operator(request.user):
            return True

        # Check if object has a user attribute
        if hasattr(obj, 'user'):
            target_user = obj.user
        elif hasattr(obj, 'created_by'):
            target_user = obj.created_by
        else:
            return False

        return can_parent_create_child(request.user.role, target_user.role)
