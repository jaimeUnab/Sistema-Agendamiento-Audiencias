"""
Módulo de servicios de la aplicación Usuarios.

Contiene ServicioRegistroAcceso, que registra los eventos de
acceso al sistema (login exitoso, login fallido, logout,
acceso denegado) en el modelo RegistroAcceso.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from .models import RegistroAcceso, TipoEventoAcceso


# =====================================================
# SERVICIO DE REGISTRO DE ACCESO
# =====================================================

class ServicioRegistroAcceso:
    """
    Registra eventos de acceso al sistema, asociándolos al
    usuario (cuando se lo puede identificar) y a la dirección
    IP desde la que ocurrieron.

    Es, para eventos de acceso, el equivalente de
    ServicioTrazabilidad (audiencias/services.py) para
    operaciones de negocio sobre una Audiencia: mismo patrón
    -solo crea registros, no modifica ningún otro modelo-,
    pero cubre un dominio distinto: quién entró o intentó
    entrar al sistema, no qué se hizo dentro de él.

    No calcula el nombre de usuario intentado ni decide si el
    evento fue exitoso: quien invoca cada método
    (usuarios/signals.py, usuarios/middleware.py) ya se los
    entrega resueltos, porque solo esos puntos tienen acceso
    al objeto request/exception original que los origina.
    """

    # -----------------------------------------------------
    # DIRECCIÓN IP
    # -----------------------------------------------------

    @staticmethod
    def _obtenerIp(request):
        """
        Devuelve la IP del cliente a partir de REMOTE_ADDR.

        El proyecto no se ejecuta detrás de un proxy inverso
        (no hay configuración de X-Forwarded-For ni de
        SECURE_PROXY_SSL_HEADER en config/settings.py), así
        que REMOTE_ADDR es la fuente correcta. Devuelve None
        si "request" es None, caso que no debería darse en la
        práctica (las tres señales de autenticación y el
        middleware de acceso denegado siempre lo entregan).
        """
        if request is None:
            return None

        return request.META.get("REMOTE_ADDR")

    # -----------------------------------------------------
    # NOMBRE DE USUARIO INTENTADO
    # -----------------------------------------------------

    @staticmethod
    def _nombreUsuario(usuario):
        """
        Devuelve el valor de USERNAME_FIELD (email, ver
        Usuario.USERNAME_FIELD en usuarios/models.py) de
        "usuario", o "" si no hay usuario resuelto.
        """
        if usuario is None:
            return ""

        return getattr(usuario, usuario.USERNAME_FIELD, "") or ""

    # -----------------------------------------------------
    # EVENTOS
    # -----------------------------------------------------

    @staticmethod
    def registrarLoginExitoso(usuario, request):
        """
        Registra un login exitoso. Se invoca desde el receptor
        de la señal user_logged_in (ver usuarios/signals.py).
        """
        return RegistroAcceso.objects.create(
            usuario=usuario,
            nombreUsuarioIntentado=ServicioRegistroAcceso._nombreUsuario(
                usuario
            ),
            tipoEvento=TipoEventoAcceso.LOGIN_EXITOSO,
            exitoso=True,
            direccionIp=ServicioRegistroAcceso._obtenerIp(request),
        )

    @staticmethod
    def registrarLoginFallido(nombreUsuarioIntentado, request):
        """
        Registra un login fallido. Se invoca desde el receptor
        de la señal user_login_failed (ver
        usuarios/signals.py), que ya entrega
        "nombreUsuarioIntentado" saneado por Django (nunca
        incluye la contraseña).

        "usuario" queda en None: un login fallido no permite
        identificar con certeza a qué Usuario correspondía el
        nombre ingresado (pudo no existir, o existir con una
        contraseña distinta).
        """
        return RegistroAcceso.objects.create(
            usuario=None,
            nombreUsuarioIntentado=nombreUsuarioIntentado or "",
            tipoEvento=TipoEventoAcceso.LOGIN_FALLIDO,
            exitoso=False,
            direccionIp=ServicioRegistroAcceso._obtenerIp(request),
        )

    @staticmethod
    def registrarLogout(usuario, request):
        """
        Registra un cierre de sesión. Se invoca desde el
        receptor de la señal user_logged_out (ver
        usuarios/signals.py).

        "usuario" puede ser None en un caso límite en que
        Django no logre identificar al usuario que cierra
        sesión; se contempla igual para no romper el receptor.
        """
        return RegistroAcceso.objects.create(
            usuario=usuario,
            nombreUsuarioIntentado=ServicioRegistroAcceso._nombreUsuario(
                usuario
            ),
            tipoEvento=TipoEventoAcceso.LOGOUT,
            exitoso=True,
            direccionIp=ServicioRegistroAcceso._obtenerIp(request),
        )

    @staticmethod
    def registrarAccesoDenegado(request):
        """
        Registra un acceso denegado (403): un usuario ya
        autenticado que intentó acceder a una vista sin el rol
        requerido. Se invoca desde
        RegistroAccesoMiddleware.process_exception (ver
        usuarios/middleware.py) al capturar un PermissionDenied.

        No registra los redirect a login por falta de sesión
        (@login_required sin usuario autenticado): esos no son
        "acceso denegado" en el sentido de este registro, y
        además nunca producen un PermissionDenied, así que el
        middleware nunca invoca este método para ese caso.
        """
        usuario = request.user if request.user.is_authenticated else None

        return RegistroAcceso.objects.create(
            usuario=usuario,
            nombreUsuarioIntentado=ServicioRegistroAcceso._nombreUsuario(
                usuario
            ),
            tipoEvento=TipoEventoAcceso.ACCESO_DENEGADO,
            exitoso=False,
            direccionIp=ServicioRegistroAcceso._obtenerIp(request),
            rutaSolicitada=request.path,
        )
