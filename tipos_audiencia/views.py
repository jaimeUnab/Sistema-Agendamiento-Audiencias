"""
Módulo de vistas de la aplicación Tipos de Audiencia.

Contiene las vistas de consulta, alta y edición del catálogo de
tipos de audiencia (HU-13) del sistema. No incluye una vista propia
de "cambiar estado" (a diferencia de Salas): activar/desactivar un
tipo de audiencia se hace desde el propio formulario de edición
(campo "activo"), ver TipoAudienciaForm en tipos_audiencia/forms.py.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso a usuarios con rol
# Administrador: Tipos de Audiencia es un módulo de
# Configuración (ver usuarios/decorators.py).
from usuarios.decorators import solo_administrador

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML, redirigir a otra
# URL y obtener un objeto o responder 404 si no existe.
from django.shortcuts import render, redirect, get_object_or_404

# Formulario de alta/edición de tipos de audiencia.
from .forms import TipoAudienciaForm

# Modelo de tipos de audiencia del sistema.
from .models import TipoAudiencia


# =====================================================
# LISTADO DE TIPOS DE AUDIENCIA
# =====================================================

@login_required
@solo_administrador
def lista_tipos_audiencia(request):
    """
    Muestra el listado de tipos de audiencia registrados
    en el sistema.

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista:
    Tipos de Audiencia es un módulo de Configuración.
    """

    # -------------------------------------------------
    # Obtiene todos los tipos de audiencia ordenados por
    # nombre. Antes también se ordenaba por "competencia",
    # pero TipoAudiencia ya no tiene ese campo: es un
    # catálogo transversal desde que se repurposó (ver
    # tipos_audiencia/models.py), y ese order_by quedó
    # desactualizado, provocando un FieldError al usar esta
    # vista. Coincide con Meta.ordering = ["nombre"] del
    # propio modelo; se deja explícito aquí, mismo criterio
    # que el resto de los listados del proyecto (por ejemplo
    # lista_salas).
    # -------------------------------------------------

    tipos_audiencia = TipoAudiencia.objects.all().order_by("nombre")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "tipos_audiencia": tipos_audiencia
    }

    return render(
        request,
        "tipos_audiencia/lista.html",
        context
    )


# =====================================================
# ALTA DE TIPOS DE AUDIENCIA
# =====================================================

@login_required
@solo_administrador
def crear_tipo_audiencia(request):
    """
    Permite registrar un nuevo tipo de audiencia del sistema.

    En GET muestra el formulario vacío. En POST valida los datos
    ingresados (nombre obligatorio y único, tal como lo exige el
    propio modelo TipoAudiencia) y, si son correctos, guarda el
    tipo de audiencia, notifica el éxito mediante el framework de
    mensajes y redirige al listado. Mismo patrón que crear_sala
    (salas/views.py).

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista.
    """

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se guarda el nuevo tipo de audiencia.
        # ---------------------------------------------

        form = TipoAudienciaForm(request.POST)

        if form.is_valid():
            tipo_audiencia = form.save()

            messages.success(
                request,
                f"Tipo de audiencia «{tipo_audiencia.nombre}» creado correctamente."
            )

            return redirect("lista_tipos_audiencia")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario vacío.
        # ---------------------------------------------

        form = TipoAudienciaForm()

    context = {
        "form": form
    }

    return render(
        request,
        "tipos_audiencia/formulario.html",
        context
    )


# =====================================================
# EDICIÓN DE TIPOS DE AUDIENCIA
# =====================================================

@login_required
@solo_administrador
def editar_tipo_audiencia(request, pk):
    """
    Permite modificar un tipo de audiencia existente del sistema.

    En GET muestra el formulario precargado con los datos actuales
    del tipo de audiencia. En POST valida los datos ingresados y,
    si son correctos, lo actualiza, notifica el éxito mediante el
    framework de mensajes y redirige al listado. Mismo patrón que
    editar_sala (salas/views.py).

    Si el tipo de audiencia no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados con rol Administrador (o
    superusuarios de Django) pueden acceder a esta vista.
    """

    # -------------------------------------------------
    # Carga el tipo de audiencia a editar, o responde 404
    # si no existe.
    # -------------------------------------------------

    tipo_audiencia = get_object_or_404(TipoAudiencia, pk=pk)

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se actualiza el tipo de audiencia
        # existente. instance=tipo_audiencia indica al
        # ModelForm que debe modificar este registro en
        # vez de crear uno nuevo.
        # ---------------------------------------------

        form = TipoAudienciaForm(request.POST, instance=tipo_audiencia)

        if form.is_valid():
            tipo_audiencia = form.save()

            messages.success(
                request,
                f"Tipo de audiencia «{tipo_audiencia.nombre}» actualizado correctamente."
            )

            return redirect("lista_tipos_audiencia")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario precargado con los datos actuales.
        # ---------------------------------------------

        form = TipoAudienciaForm(instance=tipo_audiencia)

    context = {
        "form": form,
        # Se envía el tipo de audiencia para que la plantilla,
        # compartida con la creación, sepa que está en modo
        # edición y ajuste el título y el texto del botón
        # "Guardar" (mismo criterio que "sala" en
        # templates/salas/formulario.html).
        "tipo_audiencia": tipo_audiencia,
    }

    return render(
        request,
        "tipos_audiencia/formulario.html",
        context
    )
