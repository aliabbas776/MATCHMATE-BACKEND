"""
Custom permission classes for User and Report management.
"""
from rest_framework import permissions


class IsAdminOrReadOwnProfile(permissions.BasePermission):
    """
    Permission class that allows:
    - Admin users: full access
    - Authenticated users: can only view their own profile
    - Unauthenticated users: no access
    """
    
    def has_permission(self, request, view):
        # Only authenticated users can access
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users have full access
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # For list/create actions, only admins can access
        if view.action in ['list', 'create']:
            return request.user.is_staff or request.user.is_superuser
        
        # For retrieve/update/delete, users can access their own profile
        return True
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access any object
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Users can only access their own profile
        return obj == request.user




class ReportPermission(permissions.BasePermission):
    """
    Permission class for Report management:
    - Only authenticated users can create reports
    - Users can only see their own reports (filtered in queryset)
    - Admin users can see all reports
    - Only report owner or admin can delete a report
    """
    
    def has_permission(self, request, view):
        # Only authenticated users can access
        if not request.user or not request.user.is_authenticated:
            return False
        
        # All authenticated users can create reports
        if request.method == 'POST':
            return True
        
        # All authenticated users can list/retrieve (queryset will be filtered)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Delete requires object-level permission
        if request.method == 'DELETE':
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access any report
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Users can view their own reports
        if request.method in permissions.SAFE_METHODS:
            return obj.reporter == request.user
        
        # Only report owner or admin can delete
        if request.method == 'DELETE':
            return obj.reporter == request.user
        
        return False

