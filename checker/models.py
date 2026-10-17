from django.db import models
from django.conf import settings

class Assignment(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    filename = models.CharField(max_length=255,blank=True)
    pages = models.JSONField(default=list)
    checks = models.JSONField(default=list)
    approved = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Run(models.Model):
    assignment = models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name='runs')
    results = models.JSONField(default=list)
    checks_snapshot = models.JSONField(default=list)
    suggestions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def passed(self):
        return sum(r['status']=='passed' for r in self.results)

    @property
    def failed(self):
        return sum(r['status']=='failed' for r in self.results)

    @property
    def skipped(self):
        return sum(r['status']=='unverified' for r in self.results)
