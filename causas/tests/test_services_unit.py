"""
Pruebas UNITARIAS de ServicioImportacionCausas
(causas/services.py).

Cada prueba llama DIRECTAMENTE al servicio, sin pasar por ningún
formulario ni vista HTTP: construye el archivo Excel en memoria con
openpyxl y lo entrega tal cual a ServicioImportacionCausas.procesar()
(o a resolverDuplicado()), aislando la lógica de procesamiento de
filas de cualquier consideración de permisos/formulario/template
-esas están en test_integration.py, mismo criterio que
audiencias/tests/test_services_unit.py y test_integration.py-.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import io

import openpyxl
from django.test import TestCase

from competencias.models import Competencia

from causas.models import Causa
from causas.services import ServicioImportacionCausas


# =====================================================
# AUXILIAR: ARMAR UN EXCEL EN MEMORIA
# =====================================================

def _crear_excel(filas, encabezado=("RIT", "RUC", "Carátula", "Competencia")):
    """
    Arma un archivo .xlsx en memoria (BytesIO) con el encabezado
    indicado y una fila por cada elemento de "filas".
    encabezado=None arma un archivo sin ninguna fila -para el caso
    "archivo completamente vacío"-.
    """
    libro = openpyxl.Workbook()
    hoja = libro.active
    if encabezado is not None:
        hoja.append(list(encabezado))
    for fila in filas:
        hoja.append(list(fila))
    buffer = io.BytesIO()
    libro.save(buffer)
    buffer.seek(0)
    return buffer


class ServicioImportacionCausasTests(TestCase):

    def setUp(self):
        self.competencia_uno = Competencia.objects.create(nombre="Competencia Causas Uno", activa=True)
        self.competencia_dos = Competencia.objects.create(nombre="Competencia Causas Dos", activa=True)
        self.competencia_inactiva = Competencia.objects.create(
            nombre="Competencia Causas Inactiva", activa=False
        )

    # =================================================
    # ARCHIVO
    # =================================================

    def test_excel_valido_crea_la_causa(self):
        archivo = _crear_excel(
            [("T-100-2026", "2600010010-5", "Fiscal con Pérez", "Competencia Causas Uno")]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertTrue(resultado["archivoValido"])
        self.assertEqual(len(resultado["creadas"]), 1)
        self.assertEqual(resultado["errores"], [])
        self.assertEqual(resultado["duplicados"], [])
        self.assertTrue(
            Causa.objects.filter(
                competencia=self.competencia_uno, rit="T-100-2026"
            ).exists()
        )

    def test_archivo_sin_filas_de_datos_es_invalido(self):
        archivo = _crear_excel([])  # solo encabezado, sin filas
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertFalse(resultado["archivoValido"])
        self.assertEqual(
            resultado["errorArchivo"], ServicioImportacionCausas.MENSAJE_ARCHIVO_VACIO
        )
        self.assertEqual(Causa.objects.count(), 0)

    def test_archivo_completamente_vacio_es_invalido(self):
        archivo = _crear_excel([], encabezado=None)
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertFalse(resultado["archivoValido"])
        self.assertEqual(
            resultado["errorArchivo"], ServicioImportacionCausas.MENSAJE_ARCHIVO_VACIO
        )

    def test_encabezados_incorrectos_es_invalido(self):
        archivo = _crear_excel(
            [("T-100-2026", "2600010010-5", "Fiscal con Pérez", "Competencia Causas Uno")],
            encabezado=("Rol", "RUC", "Carátula", "Competencia"),
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertFalse(resultado["archivoValido"])
        self.assertEqual(
            resultado["errorArchivo"],
            ServicioImportacionCausas.MENSAJE_ENCABEZADOS_INCORRECTOS,
        )
        self.assertEqual(Causa.objects.count(), 0)

    def test_archivo_no_legible_como_excel_es_invalido(self):
        archivo = io.BytesIO(b"esto no es un archivo Excel real")
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertFalse(resultado["archivoValido"])
        self.assertEqual(
            resultado["errorArchivo"],
            ServicioImportacionCausas.MENSAJE_ARCHIVO_NO_LEGIBLE,
        )

    # =================================================
    # DATOS OBLIGATORIOS FALTANTES
    # =================================================

    def test_rit_vacio_es_un_error_de_fila(self):
        archivo = _crear_excel(
            [("", "2600010010-5", "Fiscal con Pérez", "Competencia Causas Uno")]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["errores"]), 1)
        self.assertEqual(resultado["errores"][0]["fila"], 2)
        self.assertEqual(resultado["errores"][0]["motivo"], "Falta el RIT.")
        self.assertEqual(resultado["creadas"], [])

    def test_ruc_vacio_es_un_error_de_fila(self):
        archivo = _crear_excel(
            [("T-100-2026", "", "Fiscal con Pérez", "Competencia Causas Uno")]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(resultado["errores"][0]["motivo"], "Falta el RUC.")

    def test_caratula_vacia_es_un_error_de_fila(self):
        archivo = _crear_excel([("T-100-2026", "2600010010-5", "", "Competencia Causas Uno")])
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(resultado["errores"][0]["motivo"], "Falta la carátula.")

    def test_competencia_vacia_es_un_error_de_fila(self):
        archivo = _crear_excel(
            [("T-100-2026", "2600010010-5", "Fiscal con Pérez", "")]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(resultado["errores"][0]["motivo"], "Falta la competencia.")

    # =================================================
    # COMPETENCIA
    # =================================================

    def test_competencia_inexistente_es_un_error_de_fila(self):
        archivo = _crear_excel(
            [
                (
                    "T-100-2026",
                    "2600010010-5",
                    "Fiscal con Pérez",
                    "Competencia Inexistente",
                )
            ]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["errores"]), 1)
        self.assertIn(
            "No existe una competencia", resultado["errores"][0]["motivo"]
        )
        self.assertEqual(Causa.objects.count(), 0)

    def test_competencia_inactiva_es_un_error_de_fila(self):
        archivo = _crear_excel(
            [("T-100-2026", "2600010010-5", "Fiscal con Pérez", "Competencia Causas Inactiva")]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["errores"]), 1)
        self.assertIn("está inactiva", resultado["errores"][0]["motivo"])
        self.assertEqual(Causa.objects.count(), 0)

    # =================================================
    # VARIAS FILAS / DUPLICADOS
    # =================================================

    def test_varias_causas_validas_se_crean_todas(self):
        archivo = _crear_excel(
            [
                ("T-100-2026", "2600010010-5", "Causa Uno", "Competencia Causas Uno"),
                ("T-200-2026", "2600020020-6", "Causa Dos", "Competencia Causas Dos"),
                ("T-300-2026", "2600030030-7", "Causa Tres", "Competencia Causas Uno"),
            ]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["creadas"]), 3)
        self.assertEqual(resultado["errores"], [])
        self.assertEqual(Causa.objects.count(), 3)

    def test_duplicado_dentro_del_excel_solo_crea_la_primera_ocurrencia(self):
        archivo = _crear_excel(
            [
                ("T-100-2026", "2600010010-5", "Primera vez", "Competencia Causas Uno"),
                (
                    "T-100-2026",
                    "2600010010-5",
                    "Segunda vez (repetida)",
                    "Competencia Causas Uno",
                ),
            ]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["creadas"]), 1)
        self.assertEqual(len(resultado["errores"]), 1)
        self.assertIn(
            "duplicado dentro del mismo archivo",
            resultado["errores"][0]["motivo"],
        )
        self.assertEqual(Causa.objects.count(), 1)
        self.assertEqual(
            Causa.objects.get(
                competencia=self.competencia_uno, rit="T-100-2026"
            ).caratulado,
            "Primera vez",
        )

    def test_causa_ya_existente_no_se_crea_de_nuevo_y_queda_pendiente(self):
        Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )
        archivo = _crear_excel(
            [
                (
                    "T-100-2026",
                    "2600010010-9",
                    "Carátula nueva del Excel",
                    "Competencia Causas Uno",
                )
            ]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(resultado["creadas"], [])
        self.assertEqual(len(resultado["duplicados"]), 1)

        duplicado = resultado["duplicados"][0]
        self.assertEqual(duplicado["actual"]["caratulado"], "Carátula original")
        self.assertEqual(
            duplicado["excel"]["caratulado"], "Carátula nueva del Excel"
        )

        # No se modificó nada todavía: la causa sigue con sus datos
        # originales hasta que se resuelva explícitamente.
        self.assertEqual(Causa.objects.count(), 1)
        causa = Causa.objects.get(pk=duplicado["causaId"])
        self.assertEqual(causa.caratulado, "Carátula original")

    def test_mezcla_de_filas_validas_e_invalidas_no_detiene_la_importacion(self):
        archivo = _crear_excel(
            [
                ("T-100-2026", "2600010010-5", "Causa válida", "Competencia Causas Uno"),
                ("", "2600020020-6", "Sin RIT", "Competencia Causas Uno"),
                (
                    "T-300-2026",
                    "2600030030-7",
                    "Competencia inexistente",
                    "No Existe",
                ),
            ]
        )
        resultado = ServicioImportacionCausas(archivo).procesar()

        self.assertEqual(len(resultado["creadas"]), 1)
        self.assertEqual(len(resultado["errores"]), 2)
        self.assertEqual(Causa.objects.count(), 1)

    # =================================================
    # RESOLUCIÓN DE UN DUPLICADO
    # =================================================

    def test_resolver_duplicado_mantener_no_modifica_la_causa(self):
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )

        resultado = ServicioImportacionCausas.resolverDuplicado(
            causa, "mantener", "2600010010-9", "Carátula nueva del Excel"
        )

        self.assertEqual(resultado, "mantenida")
        causa.refresh_from_db()
        self.assertEqual(causa.ruc, "2600010010-5")
        self.assertEqual(causa.caratulado, "Carátula original")

    def test_resolver_duplicado_actualizar_modifica_ruc_y_caratulado(self):
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )

        resultado = ServicioImportacionCausas.resolverDuplicado(
            causa, "actualizar", "2600010010-9", "Carátula nueva del Excel"
        )

        self.assertEqual(resultado, "actualizada")
        causa.refresh_from_db()
        self.assertEqual(causa.ruc, "2600010010-9")
        self.assertEqual(causa.caratulado, "Carátula nueva del Excel")

    def test_resolver_duplicado_con_decision_desconocida_mantiene_por_defecto(self):
        # Ninguna decisión distinta de "actualizar" (incluido un
        # valor manipulado/ausente) debe actualizar la causa: es la
        # opción segura por defecto, exigida explícitamente por el
        # diseño ("nunca actualizar silenciosamente").
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )

        resultado = ServicioImportacionCausas.resolverDuplicado(
            causa, "valor-inesperado", "2600010010-9", "Otra carátula"
        )

        self.assertEqual(resultado, "mantenida")
        causa.refresh_from_db()
        self.assertEqual(causa.caratulado, "Carátula original")
