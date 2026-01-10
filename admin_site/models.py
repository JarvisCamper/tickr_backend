from django.db import models
from django.conf import settings
from django.utils import timezone


class ActivityLog(models.Model):
    """Track all admin actions for audit trail"""
    ACTION_TYPES = [
        ('user_create', 'User Created'),
        ('user_update', 'User Updated'),
        ('user_delete', 'User Deleted'),
        ('user_suspend', 'User Suspended'),
        ('user_activate', 'User Activated'),
        ('team_delete', 'Team Deleted'),
        ('project_delete', 'Project Deleted'),
        ('settings_update', 'Settings Updated'),
        ('login', 'Admin Login'),
        ('logout', 'Admin Logout'),
    ]
    
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions',
        db_index=True
    )
    action = models.CharField(max_length=50, choices=ACTION_TYPES, db_index=True)
    target_type = models.CharField(max_length=50, blank=True)  # 'user', 'team', 'project'
    target_id = models.IntegerField(null=True, blank=True, db_index=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]
    
    def __str__(self):
        return f"{self.admin_user} - {self.action} at {self.created_at}"


class AdminSettings(models.Model):
    """System-wide admin settings"""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_settings'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Admin Setting'
        verbose_name_plural = 'Admin Settings'
        ordering = ['key']
    
    def __str__(self):
        return f"{self.key}: {self.value}"
