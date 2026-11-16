from django.contrib import admin

from .models import Job, Project


class JobInline(admin.TabularInline):
    model = Job
    extra = 0
    fields = ["status", "progress", "error", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "owner", "created_at"]
    search_fields = ["name", "owner__email"]
    inlines = [JobInline]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "owner", "status", "progress", "created_at"]
    list_filter = ["status"]
