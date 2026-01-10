from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission to check if user is admin (staff member)
    """
    message = "You must be an admin to access this resource."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_staff
        )


class IsSuperAdmin(permissions.BasePermission):
    """
    Permission to check if user is superadmin
    """
    message = "You must be a superadmin to access this resource."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_superuser
        )


class IsAdminOrSuperAdmin(permissions.BasePermission):
    """
    Permission for admin or superadmin access
    """
    message = "You must be an admin or superadmin to access this resource."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_superuser)
        )
