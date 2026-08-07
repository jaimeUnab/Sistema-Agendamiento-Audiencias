"""
Módulo de vistas de la aplicación Bloques.

Contiene las vistas de consulta, alta, edición y cambio del
indicador de agendamiento automático del catálogo de
bloques horarios oficiales del tribunal.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Decorador que restringe el acceso únicamente a usuarios autenticados.
from django.contrib.auth.decorators import login_required

# Decorador que restringe el acceso únicamente a solicitudes POST.
# Se usa en cambiar_agendamiento_automatico porque esa vista
# modifica datos: igual que con el cierre de sesión y con
# cambiar_estado_sala, una acción que cambia el estado del
# sistema no debe poder dispararse con un simple enlace GET.
from django.views.decorators.http import require_POST

# Framework de mensajes para notificar el resultado de una acción.
from django.contrib import messages

# Funciones para renderizar plantillas HTML, redirigir a otra
# URL y obtener un objeto o responder 404 si no existe.
from django.shortcuts import render, redirect, get_object_or_404

# Formulario de alta/edición de bloques horarios.
from .forms import BloqueHorarioForm

# Modelo de bloques horarios del sistema.
from .models import BloqueHorario


# =====================================================
# LISTADO DE BLOQUES HORARIOS
# =====================================================

@login_required
def lista_bloques(request):
    """
    Muestra el listado de bloques horarios oficiales
    registrados en el sistema.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Obtiene todos los bloques horarios ordenados
    # por su campo "orden".
    # -------------------------------------------------

    bloques = BloqueHorario.objects.all().order_by("orden")

    # -------------------------------------------------
    # Envía la información a la plantilla HTML.
    # -------------------------------------------------

    context = {
        "bloques": bloques
    }

    return render(
        request,
        "bloques/lista.html",
        context
    )


# =====================================================
# ALTA DE BLOQUES HORARIOS
# =====================================================

@login_required
def crear_bloque(request):
    """
    Permite registrar un nuevo bloque horario del sistema.

    En GET muestra el formulario vacío. En POST valida los
    datos ingresados y, si son correctos, guarda el bloque,
    notifica el éxito mediante el framework de mensajes y
    redirige al listado de bloques.

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se guarda el nuevo bloque.
        # ---------------------------------------------

        form = BloqueHorarioForm(request.POST)

        if form.is_valid():
            bloque = form.save()

            messages.success(
                request,
                f"«{bloque}» creado correctamente."
            )

            return redirect("lista_bloques")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario vacío.
        # ---------------------------------------------

        form = BloqueHorarioForm()

    context = {
        "form": form
    }

    return render(
        request,
        "bloques/formulario.html",
        context
    )


# =====================================================
# CAMBIAR AGENDAMIENTO AUTOMÁTICO
# =====================================================

@login_required
@require_POST
def cambiar_agendamiento_automatico(request, pk):
    """
    Invierte, directamente desde el listado, si un bloque
    horario puede ser propuesto por el algoritmo de
    agendamiento automático.

    Invierte el valor actual de "permiteAgendamientoAutomatico"
    y guarda únicamente ese campo (update_fields). No modifica
    ningún otro dato del bloque (orden, horaInicio, horaTermino
    permanecen intactos).

    Notifica el resultado mediante el framework de mensajes
    (texto distinto según haya quedado habilitado o no) y
    redirige nuevamente al listado.

    Si el bloque no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados pueden acceder a esta
    vista, y solo mediante una solicitud POST.
    """

    # -------------------------------------------------
    # Carga el bloque a modificar, o responde 404 si no existe.
    # -------------------------------------------------

    bloque = get_object_or_404(BloqueHorario, pk=pk)

    # -------------------------------------------------
    # Invierte el indicador y lo guarda. update_fields
    # limita el UPDATE únicamente a esa columna.
    # -------------------------------------------------

    bloque.permiteAgendamientoAutomatico = not bloque.permiteAgendamientoAutomatico
    bloque.save(update_fields=["permiteAgendamientoAutomatico"])

    horario = (
        f"{bloque.horaInicio.strftime('%H:%M')} - "
        f"{bloque.horaTermino.strftime('%H:%M')}"
    )

    if bloque.permiteAgendamientoAutomatico:
        messages.success(
            request,
            f"El bloque {horario} ahora será considerado por el "
            f"agendamiento automático."
        )
    else:
        messages.success(
            request,
            f"El bloque {horario} ya no será considerado por el "
            f"agendamiento automático."
        )

    return redirect("lista_bloques")


# =====================================================
# EDICIÓN DE BLOQUES HORARIOS
# =====================================================

@login_required
def editar_bloque(request, pk):
    """
    Permite modificar un bloque horario existente del
    sistema.

    En GET muestra el formulario precargado con los datos
    actuales del bloque. En POST valida los datos ingresados
    y, si son correctos, actualiza el bloque, notifica el
    éxito mediante el framework de mensajes y redirige al
    listado de bloques.

    Si el bloque no existe, responde con un error 404
    (get_object_or_404).

    Solo los usuarios autenticados pueden acceder
    a esta vista.
    """

    # -------------------------------------------------
    # Carga el bloque a editar, o responde 404 si no existe.
    # -------------------------------------------------

    bloque = get_object_or_404(BloqueHorario, pk=pk)

    if request.method == "POST":
        # ---------------------------------------------
        # Se completó el formulario: se valida y, si es
        # correcto, se actualiza el bloque existente.
        # instance=bloque indica al ModelForm que debe
        # modificar este registro en vez de crear uno nuevo.
        # ---------------------------------------------

        form = BloqueHorarioForm(request.POST, instance=bloque)

        if form.is_valid():
            bloque = form.save()

            messages.success(
                request,
                f"«{bloque}» actualizado correctamente."
            )

            return redirect("lista_bloques")

    else:
        # ---------------------------------------------
        # Primer ingreso a la pantalla: se muestra el
        # formulario precargado con los datos actuales.
        # ---------------------------------------------

        form = BloqueHorarioForm(instance=bloque)

    context = {
        "form": form,
        # Se envía el bloque para que la plantilla, compartida
        # con la creación, sepa que está en modo edición y
        # ajuste el título y el texto del botón "Guardar".
        "bloque": bloque,
    }

    return render(
        request,
        "bloques/formulario.html",
        context
    )
