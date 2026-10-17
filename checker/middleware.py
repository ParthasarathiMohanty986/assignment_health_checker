from uuid import uuid4
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect


class GuestWorkspaceMiddleware:
    """Keep owner isolation while allowing a browser to enter without sign-in."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ('/login/', '/local-login/', '/logout/'):
            return redirect('/')
        if request.path == '/' and not request.user.is_authenticated:
            user = get_user_model().objects.create_user(
                username='guest-' + uuid4().hex, password=None
            )
            login(request, user)
        return self.get_response(request)
