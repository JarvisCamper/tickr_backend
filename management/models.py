# management/models.py
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
        related_name='created_projects'
    )
    team = models.ForeignKey(
        'Team', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_teams'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'user')

    def __str__(self):
        return f"{self.user.get_username()} in {self.team.name}"


class TimeEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    project = models.ForeignKey(
        Project, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='time_entries'
    )
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    is_running = models.BooleanField(default=False)

class TeamInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('team', 'email')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.team.name}"
    
    def is_valid(self):
        from django.utils import timezone
        return self.status == 'pending' and self.expires_at > timezone.now()
    def save(self, *args, **kwargs):
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_username()}: {self.description[:30]}"