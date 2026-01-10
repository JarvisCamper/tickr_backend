from .models import ActivityLog


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_admin_action(admin_user, action, target_type, target_id, description, request=None):
    """
    Log an admin action for audit trail
    
    Args:
        admin_user: User object of the admin performing the action
        action: Type of action (from ActivityLog.ACTION_TYPES)
        target_type: Type of target ('user', 'team', 'project', etc.)
        target_id: ID of the target object
        description: Human-readable description of the action
        request: Django request object (optional, for IP and user agent)
    """
    log_data = {
        'admin_user': admin_user,
        'action': action,
        'target_type': target_type,
        'target_id': target_id,
        'description': description,
    }
    
    if request:
        log_data['ip_address'] = get_client_ip(request)
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    return ActivityLog.objects.create(**log_data)
