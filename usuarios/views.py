from django.contrib.auth.views import LoginView


class UsuarioLoginView(LoginView):
    template_name = "usuarios/login.html"