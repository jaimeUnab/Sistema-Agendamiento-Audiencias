"""
Módulo de vistas de la aplicación Causas.

Contiene las vistas para importar causas desde un archivo Excel
y para consultar el listado de causas ya cargadas. Coordinan
ImportarCausasForm y ServicioImportacionCausas
(causas/services.py), pero no reimplementan ninguna de sus
reglas: solo interpretan el resultado estructurado que el
servicio devuelve para decidir qué renderizar -mismo criterio ya
usado en audiencias/views.py-.

Solo usuarios con rol Administrador (o superusuarios de Django)
pueden acceder a estas vistas: Causas es un módulo de
Configuración, mismo criterio que Usuarios/Competencias/Tipos de
Audiencia/Salas/Bloques/Reglas de Agendamiento (ver
usuarios/decorators.py:solo_administrador).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from usuarios.decorators import solo_administrador

from .forms import ImportarCausasForm
from .models import Causa
from .services import ServicioImportacionCausas


# =====================================================
# LISTADO DE CAUSAS
# =====================================================

@login_required
@solo_administrador
def lista_causas(request):
    """
    Muestra el listado de causas registradas en el sistema,
    tanto las importadas desde Excel como cualquier otra que ya
    existiera. Es una vista de solo lectura: no crea, edita ni
    elimina ninguna Causa (no hay CRUD completo de causas en
    este alcance, solo importación + consulta).
    """

    causas = Causa.objects.select_related("competencia").all()

    return render(request, "causas/lista.html", {"causas": causas})


# =====================================================
# IMPORTACIÓN DESDE EXCEL
# =====================================================

@login_required
@solo_administrador
def importar_causas(request):
    """
    Permite subir un archivo Excel (.xlsx) y crear las Causa
    correspondientes a sus filas, mediante
    ServicioImportacionCausas.

    En GET muestra el formulario vacío.

    En POST: si ImportarCausasForm no es válido (falta el
    archivo, o no tiene extensión .xlsx), se vuelve a mostrar el
    formulario con sus errores, sin invocar al servicio.

    Si es válido, se invoca ServicioImportacionCausas.procesar():
    - Si el archivo no pudo leerse como un Excel válido, o sus
      encabezados no coinciden con los esperados, se informa
      como error y no se guarda nada.
    - Las filas sin problemas y sin causa previa ya quedan
      creadas en la base de datos en este mismo paso (el
      servicio las guarda internamente, una transacción por
      fila).
    - Si hay filas que corresponden a una causa YA EXISTENTE
      (misma Competencia + RIT), no se actualizan aquí: se
      muestran como "duplicados pendientes", con los datos
      actuales y los del Excel, para que el funcionario decida
      (ver confirmar_actualizacion_causas más abajo). Mientras
      haya duplicados pendientes, el resumen final todavía no
      está completo.
    - Si no hay duplicados pendientes, el resultado de este
      mismo POST ya es el resumen final de la importación.
    """

    if request.method == "POST":
        form = ImportarCausasForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, "causas/importar.html", {"form": form})

        resultado = ServicioImportacionCausas(
            form.cleaned_data["archivo"]
        ).procesar()

        # Formulario vacío para el próximo intento, se muestre lo
        # que se muestre a continuación (error de archivo,
        # duplicados pendientes, o resumen final).
        form_vacio = ImportarCausasForm()

        if not resultado["archivoValido"]:
            messages.error(request, resultado["errorArchivo"])
            return render(request, "causas/importar.html", {"form": form_vacio})

        if resultado["duplicados"]:
            # Todavía falta que el funcionario decida qué hacer
            # con cada duplicado: no se arma el resumen final
            # acá. "total_creadas" y los "errores" de este primer
            # paso viajan como campos ocultos dentro del propio
            # formulario de duplicados (ver
            # templates/causas/importar.html), para que
            # confirmar_actualizacion_causas pueda construir el
            # resumen final combinando ambos pasos.
            return render(
                request,
                "causas/importar.html",
                {
                    "form": form_vacio,
                    "duplicados_pendientes": resultado["duplicados"],
                    "total_creadas": len(resultado["creadas"]),
                    "errores_pendientes": resultado["errores"],
                },
            )

        resumen_final = {
            "creadas": len(resultado["creadas"]),
            "actualizadas": 0,
            "mantenidas": 0,
            "errores": resultado["errores"],
        }

        return render(
            request,
            "causas/importar.html",
            {"form": form_vacio, "resumen_final": resumen_final},
        )

    return render(request, "causas/importar.html", {"form": ImportarCausasForm()})


# =====================================================
# CONFIRMACIÓN DE DUPLICADOS (segundo paso, opcional)
# =====================================================

@login_required
@solo_administrador
@require_POST
def confirmar_actualizacion_causas(request):
    """
    Aplica la decisión del funcionario (actualizar o mantener)
    sobre cada duplicado pendiente que le mostró importar_causas,
    y arma el resumen final combinando ese resultado con lo que
    ya se sabía del primer paso ("total_creadas" y los errores de
    lectura del archivo, recibidos como campos ocultos -ver
    templates/causas/importar.html-, porque no hay ningún otro
    lugar donde ese dato pudiera haber quedado guardado entre una
    solicitud y la siguiente: este proyecto no usa sesiones para
    esto, mismo criterio que "confirmar_advertencias" en
    audiencias/views.py).

    Cada fila de duplicados pendientes viaja con campos ocultos
    indexados (causa_id_0, ruc_excel_0, caratulado_excel_0,
    decision_0, causa_id_1, ...) en vez de con el mismo nombre
    repetido: evita cualquier ambigüedad sobre qué decisión
    corresponde a cuál causa, sin depender del orden en que el
    navegador arme el POST.

    ServicioImportacionCausas.resolverDuplicado() nunca actualiza
    si "decision" no es exactamente "actualizar": un campo
    ausente o manipulado se trata como "mantener", la opción
    segura por defecto.
    """

    total_creadas = int(request.POST.get("total_creadas") or 0)
    total_duplicados = int(request.POST.get("total_duplicados") or 0)
    total_errores = int(request.POST.get("total_errores") or 0)

    errores = [
        {
            "fila": request.POST.get(f"error_fila_{indice}"),
            "motivo": request.POST.get(f"error_motivo_{indice}"),
        }
        for indice in range(total_errores)
    ]

    actualizadas = 0
    mantenidas = 0

    for indice in range(total_duplicados):
        causa_id = request.POST.get(f"causa_id_{indice}")
        decision = request.POST.get(f"decision_{indice}")
        ruc_excel = request.POST.get(f"ruc_excel_{indice}") or ""
        caratulado_excel = request.POST.get(f"caratulado_excel_{indice}") or ""

        causa = Causa.objects.filter(pk=causa_id).first()

        if causa is None:
            # La causa pudo haber sido eliminada entre que se
            # mostró la comparación y que el funcionario confirmó
            # -escenario extremo, pero no debe romper el resto de
            # la confirmación-.
            errores.append(
                {
                    "fila": "—",
                    "motivo": (
                        f"La causa con id {causa_id} ya no existe; no "
                        "se pudo aplicar la decisión."
                    ),
                }
            )
            continue

        resultado = ServicioImportacionCausas.resolverDuplicado(
            causa, decision, ruc_excel, caratulado_excel
        )

        if resultado == "actualizada":
            actualizadas += 1
        else:
            mantenidas += 1

    resumen_final = {
        "creadas": total_creadas,
        "actualizadas": actualizadas,
        "mantenidas": mantenidas,
        "errores": errores,
    }

    return render(
        request,
        "causas/importar.html",
        {"form": ImportarCausasForm(), "resumen_final": resumen_final},
    )
