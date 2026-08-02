"""
Módulo de vistas de la aplicación Usuarios.

Contiene las vistas relacionadas con la autenticación
y administración de usuarios del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Vistas genéricas de Django para el inicio y cierre de sesión.
from django.contrib.auth.views import LoginView, LogoutView

# Función para renderizar plantillas HTML.
from django.shortcuts import render

# Modelo de usuario personalizado del sistema.
from .models import Usuario


# =====================================================
# VISTA DE INICIO DE SESIÓN
# =====================================================

class UsuarioLoginView(LoginView):
    """
    Vista encargada del inicio de sesión.

    Utiliza la plantilla login.html para autenticar
    a los usuarios del sistema.
    """

    template_name = "usuarios/login.html"


# =====================================================
# VISTA DE CIERRE DE SESIÓN
# =====================================================

class UsuarioLogoutView(LogoutView):
    """
    Vista encargada de cerrar la sesión del usuario.

    Una vez cerrada la sesión, redirige nuevamente
    a la pantalla de inicio de sesión.
    """

    next_page = "login"


# =====================================================
# LISTADO DE USUARIOS
# =====================================================

@login_required
def lista_usuarios(request):
    """
    Muestra el listado de usuarios registrados
    en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los usuarios registrados
    # ordenados alfabéticamente por nombre.
    # -------------------------------------------------

    usuarios = Usuario.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "usuarios": usuarios
    }

    return render(
        request,
        "usuarios/lista.html",
        context
    )
