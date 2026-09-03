"""
Módulo de middleware de la aplicación Usuarios.

Contiene RegistroAccesoMiddleware, que intercepta las
excepciones PermissionDenied (403) producidas por el control
de acceso por rol del sistema para registrarlas en
RegistroAcceso mediante ServicioRegistroAcceso.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.core.exceptions import PermissionDenied

from .services import ServicioRegistroAcceso


# =====================================================
# MIDDLEWARE
# =====================================================

class RegistroAccesoMiddleware:
    """
    Registra en RegistroAcceso cada PermissionDenied (403)
    lanzada por una vista, mediante process_exception: hoy es
    el único punto que cubre, sin duplicar lógica, tanto las
    vistas de función decoradas con @solo_administrador como
    las vistas de clase que usan UserPassesTestMixin sin
    raise_exception=True (ver usuarios/decorators.py y
    UsuarioCreateView/UsuarioUpdateView en usuarios/views.py)
    -ambas terminan lanzando PermissionDenied cuando el
    usuario ya está autenticado pero no tiene el rol
    requerido, nunca redirigiendo-.

    No registra los redirect a login que produce
    @login_required cuando no hay sesión iniciada: eso no es
    un "acceso denegado" en el sentido de este registro (un
    usuario autenticado sin permiso), sino la ausencia de
    autenticación, y @login_required nunca lanza
    PermissionDenied para ese caso, así que este middleware
    directamente no lo ve.

    Se implementa solo con process_exception, sin envolver
    get_response: no necesita inspeccionar la respuesta final,
    solo la excepción que la originó.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """
        Registra el acceso denegado y devuelve None de forma
        explícita: Django sigue su manejo estándar de la
        excepción (renderiza la respuesta 403 de siempre, sin
        cambios). Este middleware solo observa/registra, nunca
        reemplaza la respuesta.
        """
        if isinstance(exception, PermissionDenied):
            ServicioRegistroAcceso.registrarAccesoDenegado(request)

        return None
