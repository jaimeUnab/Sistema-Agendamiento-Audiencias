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