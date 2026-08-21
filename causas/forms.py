"""
Módulo de formularios de la aplicación Causas.

Contiene el formulario utilizado para subir el archivo Excel del
que se importan las causas.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django import forms


# =====================================================
# FORMULARIO
# =====================================================

class ImportarCausasForm(forms.Form):
    """
    Recibe el archivo Excel (.xlsx) a importar.

    Solo valida lo que le corresponde a un formulario: que se
    haya adjuntado un archivo y que su extensión sea ".xlsx".
    NO abre el archivo, no lee sus filas, no valida sus
    encabezados ni sus datos: eso es responsabilidad exclusiva
    de ServicioImportacionCausas (causas/services.py), que
    también debe volver a comprobar que el contenido sea un
    Excel válido -un archivo podría tener extensión ".xlsx" y
    aun así no ser un Excel real, o estar corrupto-. Mismo
    criterio de reparto que AudienciaForm/ValidadorAgendamiento
    en la app audiencias: el Form valida formato de entrada, el
    servicio valida contenido y reglas de negocio.
    """

    archivo = forms.FileField(
        label="Archivo Excel (.xlsx)",
        error_messages={
            "required": "Debes seleccionar un archivo para importar.",
        },
    )

    def clean_archivo(self):
        """
        Rechaza cualquier archivo cuyo nombre no termine en
        ".xlsx" (sin distinguir mayúsculas/minúsculas). Es una
        validación de formato de entrada, no de contenido: no
        garantiza que el archivo sea realmente un Excel válido,
        solo que "parece" uno por su extensión.
        """

        archivo = self.cleaned_data["archivo"]

        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(
                "El archivo debe tener extensión .xlsx."
            )

        return archivo
