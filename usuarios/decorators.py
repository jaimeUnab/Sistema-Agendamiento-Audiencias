"""
Módulo de decoradores de control de acceso por rol de la
aplicación Usuarios.

Contiene "solo_administrador", usado por los módulos de
Configuración del sistema (Usuarios, Competencias, Tipos de
Audiencia, Salas, Bloques Horarios, Reglas de Agendamiento, Días
No Disponibles) para restringir sus vistas basadas en función a
usuarios con rol Administrador.

No crea ningún sistema de permisos nuevo: reutiliza exactamente
el mismo criterio que UsuarioCreateView.test_func() y
UsuarioUpdateView.test_func() ya aplican (ver usuarios/views.py)
mediante UserPassesTestMixin -usuario con rol=RolUsuario.
ADMINISTRADOR, o is_superuser, para no dejar a un superusuario de
Django bloqueado fuera de un módulo de Configuración si, por
cualquier vía, su campo "rol" no quedó en Administrador-, solo
que expresado como decorador para poder aplicarlo a vistas de
función, que son la mayoría de las vistas de Configuración
(UsuarioCreateView/UsuarioUpdateView son las únicas basadas en
clase; esas ya están protegidas y no se tocan aquí).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from functools import wraps

# Excepción estándar de Django para "usuario autenticado, pero
# sin permiso": produce una respuesta 403 (Prohibido), distinta
# de la redirección al login que ya aplica @login_required para
# un usuario no autenticado.
from django.core.exceptions import PermissionDenied

# Enum de roles y modelo de usuario propios de esta app.
from .models import RolUsuario


# =====================================================
# DECORADOR: SOLO ADMINISTRADOR
# =====================================================

def solo_administrador(view_func):
    """
    Restringe una vista basada en función a usuarios con rol
    Administrador (o superusuarios de Django).

    Se coloca SIEMPRE después de @login_required en la vista
    decorada (más cerca de la función, ver ejemplo abajo), igual
    que LoginRequiredMixin va antes que UserPassesTestMixin en
    las vistas basadas en clase: para cuando este decorador se
    ejecuta, request.user ya fue verificado como autenticado por
    @login_required, así que aquí solo se comprueba el rol, sin
    repetir la comprobación de autenticación.

        @login_required
        @solo_administrador
        def lista_competencias(request):
            ...

    Un usuario autenticado sin el rol requerido recibe un 403
    (PermissionDenied), con la página de error estándar de
    Django -no un simple redirect al login, que confundiría "no
    tienes permiso" con "no iniciaste sesión"-.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (
            request.user.is_superuser
            or request.user.tieneRol(RolUsuario.ADMINISTRADOR)
        ):
            raise PermissionDenied(
                "Esta sección está disponible solo para usuarios "
                "con perfil Administrador."
            )

        return view_func(request, *args, **kwargs)

    return wrapper
