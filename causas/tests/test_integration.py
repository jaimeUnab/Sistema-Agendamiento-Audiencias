"""
Pruebas de INTEGRACIÓN de la aplicación Causas.

A diferencia de test_services_unit.py (que llama directamente al
servicio), estas pruebas recorren el flujo HTTP completo con el
cliente de pruebas de Django (self.client): login real, subida de
un archivo .xlsx real tal como lo haría el navegador, permisos por
rol, y verificación de que los datos efectivamente quedan
almacenados en la base de datos -incluida la comprobación de que
"Buscar causa" (audiencias/views.py, sin modificar) encuentra una
causa recién importada-.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import io

import openpyxl
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from competencias.models import Competencia
from usuarios.models import RolUsuario

from causas.models import Causa

Usuario = get_user_model()


# =====================================================
# AUXILIAR: ARCHIVO EXCEL SUBIDO POR HTTP
# =====================================================

def _archivo_excel(
    filas,
    encabezado=("RIT", "RUC", "Carátula", "Competencia"),
    nombre="causas.xlsx",
):
    """
    Arma un archivo .xlsx en memoria y lo envuelve en un
    SimpleUploadedFile, tal como llegaría en request.FILES desde un
    formulario real con enctype="multipart/form-data".
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

    return SimpleUploadedFile(
        nombre,
        buffer.read(),
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
    )


# =====================================================
# IMPORTACIÓN - FLUJO HTTP COMPLETO
# =====================================================

class ImportarCausasIntegrationTests(TestCase):

    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin_causas",
            email="admin_causas@tribunal.cl",
            password="ClaveSegura123",
            nombre="Admin Causas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.usuario_comun = Usuario.objects.create_user(
            username="usuario_causas",
            email="usuario_causas@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Común Causas",
            rol=RolUsuario.USUARIO,
        )
        self.competencia_uno = Competencia.objects.create(nombre="Competencia Causas Uno", activa=True)

    # =================================================
    # PERMISOS
    # =================================================

    def test_usuario_no_autenticado_es_redirigido_al_login(self):
        respuesta = self.client.get(reverse("importar_causas"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_usuario_sin_rol_administrador_no_puede_importar(self):
        self.client.login(
            username=self.usuario_comun.email, password="ClaveSegura123"
        )

        archivo = _archivo_excel(
            [("T-100-2026", "2600010010-5", "Causa Uno", "Competencia Causas Uno")]
        )
        respuesta = self.client.post(
            reverse("importar_causas"), {"archivo": archivo}
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Causa.objects.count(), 0)

    def test_usuario_sin_rol_administrador_no_puede_ver_el_listado(self):
        self.client.login(
            username=self.usuario_comun.email, password="ClaveSegura123"
        )

        respuesta = self.client.get(reverse("lista_causas"))

        self.assertEqual(respuesta.status_code, 403)

    # =================================================
    # IMPORTACIÓN CORRECTA
    # =================================================

    def test_importacion_correcta_crea_las_causas_y_muestra_resumen(self):
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        archivo = _archivo_excel(
            [
                ("T-100-2026", "2600010010-5", "Causa Uno", "Competencia Causas Uno"),
                ("T-200-2026", "2600020020-6", "Causa Dos", "Competencia Causas Uno"),
            ]
        )
        respuesta = self.client.post(
            reverse("importar_causas"), {"archivo": archivo}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Causa.objects.count(), 2)
        self.assertEqual(respuesta.context["resumen_final"]["creadas"], 2)
        self.assertEqual(respuesta.context["resumen_final"]["errores"], [])
        self.assertContains(respuesta, "Resultado de la importación")

    def test_archivo_sin_extension_xlsx_es_rechazado_por_el_formulario(self):
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        archivo = SimpleUploadedFile(
            "causas.csv", b"RIT,RUC,Caratula,Competencia", content_type="text/csv"
        )
        respuesta = self.client.post(
            reverse("importar_causas"), {"archivo": archivo}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El archivo debe tener extensión .xlsx.")
        self.assertEqual(Causa.objects.count(), 0)

    # =================================================
    # DUPLICADOS
    # =================================================

    def test_causa_ya_existente_se_informa_como_duplicado_pendiente(self):
        Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        archivo = _archivo_excel(
            [
                (
                    "T-100-2026",
                    "2600010010-9",
                    "Carátula nueva del Excel",
                    "Competencia Causas Uno",
                )
            ]
        )
        respuesta = self.client.post(
            reverse("importar_causas"), {"archivo": archivo}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Causas duplicadas encontradas")
        self.assertContains(respuesta, "Carátula original")
        self.assertContains(respuesta, "Carátula nueva del Excel")

        duplicados = respuesta.context["duplicados_pendientes"]
        self.assertEqual(len(duplicados), 1)

        # No se aplicó ningún cambio todavía: sigue con los datos
        # originales hasta que se confirme una decisión.
        causa = Causa.objects.get(competencia=self.competencia_uno, rit="T-100-2026")
        self.assertEqual(causa.caratulado, "Carátula original")

    def test_confirmar_mantener_no_actualiza_la_causa(self):
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        respuesta = self.client.post(
            reverse("confirmar_actualizacion_causas"),
            {
                "total_creadas": "0",
                "total_duplicados": "1",
                "total_errores": "0",
                "causa_id_0": str(causa.pk),
                "ruc_excel_0": "2600010010-9",
                "caratulado_excel_0": "Carátula nueva del Excel",
                "decision_0": "mantener",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen_final"]["mantenidas"], 1)
        self.assertEqual(respuesta.context["resumen_final"]["actualizadas"], 0)

        causa.refresh_from_db()
        self.assertEqual(causa.caratulado, "Carátula original")

    def test_confirmar_actualizar_actualiza_la_causa(self):
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        respuesta = self.client.post(
            reverse("confirmar_actualizacion_causas"),
            {
                "total_creadas": "0",
                "total_duplicados": "1",
                "total_errores": "0",
                "causa_id_0": str(causa.pk),
                "ruc_excel_0": "2600010010-9",
                "caratulado_excel_0": "Carátula nueva del Excel",
                "decision_0": "actualizar",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen_final"]["actualizadas"], 1)

        causa.refresh_from_db()
        self.assertEqual(causa.ruc, "2600010010-9")
        self.assertEqual(causa.caratulado, "Carátula nueva del Excel")

    def test_confirmar_incluye_el_total_creadas_del_primer_paso_en_el_resumen(self):
        # "total_creadas" viaja como campo oculto desde el primer
        # paso (importar_causas): el resumen final debe combinarlo
        # con lo que se resuelve en este segundo paso, no perderlo.
        causa = Causa.objects.create(
            competencia=self.competencia_uno,
            rit="T-100-2026",
            ruc="2600010010-5",
            caratulado="Carátula original",
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        respuesta = self.client.post(
            reverse("confirmar_actualizacion_causas"),
            {
                "total_creadas": "3",
                "total_duplicados": "1",
                "total_errores": "0",
                "causa_id_0": str(causa.pk),
                "ruc_excel_0": "2600010010-9",
                "caratulado_excel_0": "Carátula nueva del Excel",
                "decision_0": "mantener",
            },
        )

        self.assertEqual(respuesta.context["resumen_final"]["creadas"], 3)

    # =================================================
    # LISTADO
    # =================================================

    def test_lista_causas_muestra_las_causas_importadas(self):
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        archivo = _archivo_excel(
            [("T-100-2026", "2600010010-5", "Causa Listada", "Competencia Causas Uno")]
        )
        self.client.post(reverse("importar_causas"), {"archivo": archivo})

        respuesta = self.client.get(reverse("lista_causas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "T-100-2026")
        self.assertContains(respuesta, "Causa Listada")

    # =================================================
    # INTEGRACIÓN CON "BUSCAR CAUSA" DE AUDIENCIAS
    # =================================================

    def test_causa_importada_aparece_en_buscar_causa_de_audiencias(self):
        # Cierra el círculo pedido: importar una causa desde Excel y
        # luego encontrarla con el flujo YA EXISTENTE de "Buscar
        # causa" en audiencias/views.py/_resolver_causa(), sin haber
        # modificado ese código.
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

        archivo = _archivo_excel(
            [
                (
                    "T-500-2026",
                    "2600050050-1",
                    "Fiscal de Chile con Juan Pérez",
                    "Competencia Causas Uno",
                )
            ]
        )
        self.client.post(reverse("importar_causas"), {"archivo": archivo})

        respuesta = self.client.post(
            reverse("registrar_audiencia"),
            {
                "buscar_causa": "1",
                "competencia": self.competencia_uno.pk,
                "rit": "T-500-2026",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        causa_encontrada = respuesta.context["causa_encontrada"]
        self.assertIsNotNone(causa_encontrada)
        self.assertEqual(causa_encontrada.rit, "T-500-2026")
        self.assertEqual(
            causa_encontrada.caratulado, "Fiscal de Chile con Juan Pérez"
        )
