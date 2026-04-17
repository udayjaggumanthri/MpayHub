"""
Custom permission classes for the mPayhub platform.
"""
from rest_framework import permissions


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
    """Permission to check if user is Admin."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Admin'


class IsMasterDistributorOrAbove(permissions.BasePermission):
    """Permission for Master Distributor and above (includes Super Distributor and Admin)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
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
            'Admin',
            'Super Distributor',
            'Master Distributor',
            'Distributor',
        ]


class IsHierarchy(permissions.BasePermission):
    """
    Permission to check if user can access resources based on hierarchy.
    Admin: all roles below; Super Distributor: D/R (skips MD tier for onboarding); Master Distributor: D/R; Distributor: R.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can access everything
        if request.user.role == 'Admin':
            return True
        
        # For other roles, check is done at object level
        return True
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can access everything
        if request.user.role == 'Admin':
            return True
        
        # Check if object has a user attribute
        if hasattr(obj, 'user'):
            target_user = obj.user
        elif hasattr(obj, 'created_by'):
            target_user = obj.created_by
        else:
            return False
        
        # Check hierarchy
        current_role = request.user.role
        target_role = target_user.role
        
        hierarchy = {
            'Admin': [
                'Super Distributor',
                'Master Distributor',
                'Distributor',
                'Retailer',
            ],
            'Super Distributor': ['Distributor', 'Retailer'],
            'Master Distributor': ['Distributor', 'Retailer'],
            'Distributor': ['Retailer'],
            'Retailer': [],
        }
        
        return target_role in hierarchy.get(current_role, [])
