"""
Módulo de formularios de la aplicación Usuarios.

Contiene los formularios utilizados para la administración
de usuarios del sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Formularios base de Django.
from django import forms

# Excepción utilizada para reportar errores de validación.
from django.core.exceptions import ValidationError

# Modelo de usuario personalizado del sistema.
from .models import Usuario


# =====================================================
# FORMULARIO
# =====================================================

class UsuarioForm(forms.ModelForm):
    """
    Formulario para el registro de nuevos usuarios.

    Incluye los campos propios del modelo Usuario
    más dos campos adicionales para el ingreso
    y confirmación de la contraseña.
    """

    # Contraseña ingresada por el usuario.
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput
    )

    # Confirmación de la contraseña.
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput
    )

    class Meta:
        model = Usuario

        # Campos del modelo que incluirá el formulario.
        fields = [
            "nombre",
            "email",
            "rol",
            "is_active",
        ]

    # Orden explícito de los campos en el formulario.
    #
    # Se usa field_order (en vez de confiar en el orden
    # implícito que resulta de combinar Meta.fields con los
    # campos declarados en la clase) para que la secuencia
    # quede garantizada y documentada, sin depender de cómo
    # Django decida mezclar ambos internamente.
    #
    # Criterio del orden: agrupa los campos por etapa lógica
    # del alta de un usuario -> primero su información
    # (nombre, email, rol), luego sus credenciales
    # (password1, password2) y por último su estado
    # operativo (is_active), que no es parte del flujo de
    # identidad/credenciales sino un dato administrativo.
    field_order = [
        "nombre",
        "email",
        "rol",
        "password1",
        "password2",
        "is_active",
    ]

    def __init__(self, *args, **kwargs):
        """
        Al editar un usuario existente (self.instance.pk ya
        asignado), la contraseña pasa a ser opcional: si el
        administrador deja ambos campos en blanco, la
        contraseña actual no se modifica. Al crear un usuario
        nuevo (instance.pk aún None) siguen siendo
        obligatorios, sin cambios respecto al comportamiento
        original.

        También agrega la clase Bootstrap correspondiente a cada
        campo (form-control / form-select / form-check-input)
        según el tipo de widget -incluye "nombre"/"email" (texto),
        "rol" (select), "is_active" (checkbox) y "password1"/
        "password2" (declarados arriba con PasswordInput)-.
        Exclusivamente presentación: no cambia validación ni
        comportamiento.
        """

        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

        if self.instance.pk:
            self.fields["password1"].required = False
            self.fields["password2"].required = False

    # =================================================
    # VALIDACIONES
    # =================================================

    def clean_email(self):
        """
        Valida que el correo electrónico ingresado
        no esté registrado previamente en el sistema.

        Al editar, se excluye la propia instancia de la
        búsqueda: de lo contrario, guardar un usuario sin
        cambiar su correo lo rechazaría por "duplicado"
        contra sí mismo.
        """

        email = self.cleaned_data.get("email")

        usuarios_con_ese_email = Usuario.objects.filter(email=email)

        if self.instance.pk:
            usuarios_con_ese_email = usuarios_con_ese_email.exclude(
                pk=self.instance.pk
            )

        if usuarios_con_ese_email.exists():
            raise ValidationError(
                "Ya existe un usuario registrado con este correo electrónico."
            )

        return email

    def clean(self):
        """
        Valida las contraseñas ingresadas.

        - Si ambas están vacías: válido, no se modifica
          la contraseña actual (solo relevante al editar).
        - Si solo una de las dos fue completada: inválido,
          se exige ingresar y confirmar la nueva contraseña
          junta, nunca por separado.
        - Si ambas fueron completadas pero no coinciden:
          inválido.
        """

        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and not password2:
            raise ValidationError(
                "Debes confirmar la nueva contraseña."
            )

        if password2 and not password1:
            raise ValidationError(
                "Debes ingresar la nueva contraseña antes de confirmarla."
            )

        if password1 and password2 and password1 != password2:
            raise ValidationError(
                "Las contraseñas ingresadas no coinciden."
            )

        return cleaned_data

    # =================================================
    # MÉTODO SAVE
    # =================================================

    def save(self, commit=True):
        """
        Guarda el usuario cifrando la contraseña mediante
        set_password(), evitando almacenarla en texto plano.

        Si no se ingresó una contraseña nueva (caso de
        edición con campos en blanco), la contraseña actual
        del usuario se mantiene sin cambios.
        """

        # Crea la instancia del usuario sin guardarla aún.
        usuario = super().save(commit=False)

        password1 = self.cleaned_data.get("password1")

        # Solo cifra y asigna la contraseña si se ingresó una nueva.
        if password1:
            usuario.set_password(password1)

        if commit:
            usuario.save()

        return usuario
