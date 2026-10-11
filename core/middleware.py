from django.shortcuts import redirect
from django.conf import settings
from django.urls import reverse

class RequireLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Rutas que no requieren login
        public_paths = [
            reverse('login'),
            reverse('signup'),
            '/admin/',  # El admin tiene su propio sistema de auth
        ]

        # Verifica si el usuario NO está autenticado y la ruta NO es pública
        if not request.user.is_authenticated and not any(request.path.startswith(path) for path in public_paths):
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
