from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class RolUsuario(models.TextChoices):
    """
    Define los roles del sistema.
    """

    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    USUARIO = "USUARIO", "Usuario"


class UsuarioManager(UserManager):
    """
    Manager personalizado de Usuario.

    Extiende el UserManager por defecto únicamente para
    asegurar que todo superusuario creado por consola
    (createsuperuser) quede con rol Administrador, y no
    con el rol Usuario por defecto del modelo.
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("rol", RolUsuario.ADMINISTRADOR)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Modelo de usuario del sistema.

    Hereda de AbstractUser para reutilizar el sistema
    de autenticación de Django.
    """

    # =====================================================
    # CAMPOS DEL SISTEMA
    # =====================================================

    # Nombre completo del funcionario
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )

    # Correo institucional
    email = models.EmailField(
        unique=True,
        verbose_name="Correo"
    )

    # Rol del usuario
    rol = models.CharField(
        max_length=20,
        choices=RolUsuario.choices,
        default=RolUsuario.USUARIO,
        verbose_name="Rol"
    )

    # =====================================================
    # CONFIGURACIÓN DE AUTENTICACIÓN
    # =====================================================

    # El correo será utilizado para iniciar sesión
    USERNAME_FIELD = "email"

    # Campos obligatorios al crear un superusuario
    REQUIRED_FIELDS = [
        "username",
        "nombre",
    ]

    # Manager que garantiza rol=Administrador para superusuarios.
    objects = UsuarioManager()

    # =====================================================
    # MÉTODOS
    # =====================================================

    def tieneRol(self, rol):
        """
        Verifica si el usuario posee el rol indicado.
        """
        return self.rol == rol

    def __str__(self):
        """
        Devuelve el nombre del usuario.
        """
        return self.nombre

    def save(self, *args, **kwargs):
        """
        Sobrescribe el guardado del modelo para mantener
        compatibilidad interna con Django.

        El sistema de autenticación se basa en "email"
        (USERNAME_FIELD), pero el campo "username" heredado
        de AbstractUser sigue existiendo y es único a nivel
        de base de datos. El usuario nunca lo ingresa, por lo
        que aquí se autocompleta con el correo únicamente
        cuando aún no tiene un valor asignado, evitando así
        el error de unicidad al crear nuevos usuarios sin
        pisar un "username" ya definido en ediciones futuras.
        """

        if not self.username:
            self.username = self.email

        super().save(*args, **kwargs)


# =====================================================
# REGISTRO DE ACCESO
# =====================================================

class TipoEventoAcceso(models.TextChoices):
    """
    Define los tipos de evento que RegistroAcceso puede
    registrar.
    """

    LOGIN_EXITOSO = "LOGIN_EXITOSO", "Login exitoso"
    LOGIN_FALLIDO = "LOGIN_FALLIDO", "Login fallido"
    LOGOUT = "LOGOUT", "Logout"
    ACCESO_DENEGADO = "ACCESO_DENEGADO", "Acceso denegado"


class RegistroAcceso(models.Model):
    """
    Audita un evento de acceso al sistema: login (exitoso o
    fallido), logout, o acceso denegado a una sección
    restringida por rol.

    Es independiente de RegistroTrazabilidad
    (audiencias/models.py): ese modelo audita operaciones de
    negocio sobre una Audiencia; este audita quién entró,
    quién intentó entrar sin éxito y quién intentó acceder a
    una sección sin el permiso requerido. Ninguno de los dos
    reemplaza ni modifica al otro.

    Solo define la estructura de datos: el servicio que
    efectivamente crea estos registros (ServicioRegistroAcceso)
    vive en usuarios/services.py.
    """

    # Usuario del sistema asociado al evento. Nulo en un login
    # fallido cuyo nombre de usuario no corresponde a ningún
    # Usuario existente -no siempre es posible identificar a
    # quién intentó acceder-. on_delete=SET_NULL: si el
    # Usuario se elimina más adelante, el registro histórico
    # de acceso no debe perderse.
    usuario = models.ForeignKey(
        Usuario,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registrosAcceso",
        verbose_name="Usuario",
    )

    # Nombre de usuario (correo, ver USERNAME_FIELD más arriba)
    # asociado al intento, tal como se ingresó o se resolvió.
    # Se completa en TODOS los eventos, no solo cuando
    # "usuario" es None: permite reconstruir con qué credencial
    # se accedió incluso cuando sí existe un Usuario asociado.
    nombreUsuarioIntentado = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Nombre de usuario intentado",
    )

    # Tipo de evento registrado.
    tipoEvento = models.CharField(
        max_length=20,
        choices=TipoEventoAcceso.choices,
        verbose_name="Tipo de evento",
    )

    # Indica si el evento representa un acceso concedido
    # (LOGIN_EXITOSO, LOGOUT) o denegado (LOGIN_FALLIDO,
    # ACCESO_DENEGADO). Se guarda como campo propio -en vez de
    # derivarlo de "tipoEvento" al leer- para que quede
    # filtrable directamente desde el panel de administración
    # (ver usuarios/admin.py).
    exitoso = models.BooleanField(
        verbose_name="Exitoso",
    )

    # Fecha y hora del evento. auto_now_add la asigna una única
    # vez, al crear el registro (mismo criterio que
    # RegistroTrazabilidad.fechaHora en audiencias/models.py).
    fechaHora = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora",
    )

    # Dirección IP desde la que ocurrió el evento (ver
    # ServicioRegistroAcceso._obtenerIp). Nula solo si no hay
    # objeto request disponible, caso que no debería darse en
    # la práctica.
    direccionIp = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP",
    )

    # Ruta solicitada que produjo un ACCESO_DENEGADO. Queda en
    # blanco para el resto de los eventos: login/logout no
    # tienen una "ruta denegada" asociada.
    rutaSolicitada = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Ruta solicitada",
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena del evento más reciente al más antiguo, el
        # orden natural para revisar un historial de accesos.
        ordering = ["-fechaHora"]

        verbose_name = "Registro de acceso"
        verbose_name_plural = "Registros de acceso"

    def __str__(self):
        """
        Devuelve "TipoEvento - nombreUsuarioIntentado -
        FechaHora", por ejemplo:
        "Login fallido - jasalas1@pjud.cl - 2026-09-03 10:15".
        """
        return (
            f"{self.get_tipoEvento_display()} - "
            f"{self.nombreUsuarioIntentado} - {self.fechaHora}"
        )