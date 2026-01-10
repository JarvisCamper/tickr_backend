from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Project(models.Model):
    PROJECT_TYPES = [
        ('individual', 'Individual'),
        ('group', 'Group'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=PROJECT_TYPES, default='individual')
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_projects',
        db_index=True
    )
    team = models.ForeignKey(
        'Team', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='projects',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['creator', 'created_at']),
            models.Index(fields=['team', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_teams',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships',
        db_index=True
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'user')
        indexes = [
            models.Index(fields=['user', 'team']),
        ]

    def __str__(self):
        return f"{self.user.get_username()} in {self.team.name}"


class TimeEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries',
        db_index=True
    )
    project = models.ForeignKey(
        Project, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='time_entries',
        db_index=True
    )
    description = models.TextField()
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True, db_index=True)
    duration = models.DurationField(null=True, blank=True)
    is_running = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_running']),
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['user', 'end_time']),
        ]
        ordering = ['-start_time']

    def save(self, *args, **kwargs):
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_username()}: {self.description[:30]}"


class TeamInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='invitations', db_index=True)
    email = models.EmailField(db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        db_index=True
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['token', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.team.name}"
    
    def is_valid(self):
        return self.status == 'pending' and self.expires_at > timezone.now()
