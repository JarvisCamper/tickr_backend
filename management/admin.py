# management/admin.py
from django.contrib import admin
from .models import Project, Team, TeamMember, TimeEntry


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'creator', 'team')
    list_filter = ('type',)
    search_fields = ('name', 'creator__username') 


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner')
    search_fields = ('name', 'owner__username')


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'joined_at')
    list_filter = ('team',)


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'description', 'duration', 'is_running')
    list_filter = ('is_running', 'project')
    search_fields = ('description', 'user__username')