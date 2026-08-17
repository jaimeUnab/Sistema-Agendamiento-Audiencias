"""
Pruebas UNITARIAS del formulario AudienciaForm
(audiencias/forms.py).

Cada prueba de este archivo construye AudienciaForm directamente
con distintos datos de entrada y revisa is_valid()/cleaned_data/
errors: no pasan por ninguna vista HTTP ni por el cliente de
pruebas de Django (esas pruebas están en test_integration.py).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime

from django.test import TestCase

from bloques.models import BloqueHorario
from competencias.models import Competencia
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia

from audiencias.forms import AudienciaForm, DejarSinEfectoAudienciaForm, MotivoBaja


class AudienciaFormTests(TestCase):
    """
    Pruebas de validación de AudienciaForm.
    """

    def setUp(self):
        self.competencia = Competencia.objects.create(
            nombre="Competencia Form Tests", activa=True
        )
        self.tipo_audiencia = TipoAudiencia.objects.create(
            nombre="Tipo Form Tests", activo=True
        )
        self.sala = Sala.objects.create(nombre="Sala Form Tests", activa=True)
        self.bloque = BloqueHorario.objects.create(
            orden=9601, horaInicio=datetime.time(9, 0), horaTermino=datetime.time(9, 30)
        )

    def _datos_validos(self, **overrides):
        """
        Devuelve un dict de datos POST válidos y completos para
        AudienciaForm, permitiendo sobreescribir cualquier campo
        desde cada prueba.
        """
        datos = {
            "competencia": self.competencia.pk,
            "rit": "2222-2027",
            "tipoAudiencia": self.tipo_audiencia.pk,
            "sala": self.sala.pk,
            "cantidadBloques": 1,
            "fecha": "2027-04-01",
            "bloqueInicio": self.bloque.pk,
        }
        datos.update(overrides)
        return datos

    def test_formulario_valido_con_datos_completos(self):
        form = AudienciaForm(data=self._datos_validos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_invalido_sin_rit(self):
        form = AudienciaForm(data=self._datos_validos(rit=""))
        self.assertFalse(form.is_valid())
        self.assertIn("rit", form.errors)

    def test_formulario_invalido_sin_competencia(self):
        form = AudienciaForm(data=self._datos_validos(competencia=""))
        self.assertFalse(form.is_valid())
        self.assertIn("competencia", form.errors)

    def test_formulario_invalido_sin_bloqueInicio(self):
        form = AudienciaForm(data=self._datos_validos(bloqueInicio=""))
        self.assertFalse(form.is_valid())
        self.assertIn("bloqueInicio", form.errors)

    def test_formulario_invalido_sin_fecha(self):
        form = AudienciaForm(data=self._datos_validos(fecha=""))
        self.assertFalse(form.is_valid())
        self.assertIn("fecha", form.errors)

    def test_clean_rit_elimina_espacios_al_inicio_y_al_final(self):
        form = AudienciaForm(data=self._datos_validos(rit="  3333-2027  "))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["rit"], "3333-2027")

    def test_cantidad_bloques_rechaza_un_valor_fuera_de_rango(self):
        form = AudienciaForm(data=self._datos_validos(cantidadBloques=11))
        self.assertFalse(form.is_valid())
        self.assertIn("cantidadBloques", form.errors)

    def test_cantidad_bloques_rechaza_cero(self):
        form = AudienciaForm(data=self._datos_validos(cantidadBloques=0))
        self.assertFalse(form.is_valid())
        self.assertIn("cantidadBloques", form.errors)

    def test_cantidad_bloques_acepta_el_rango_completo_uno_a_diez(self):
        for cantidad in range(1, 11):
            with self.subTest(cantidad=cantidad):
                form = AudienciaForm(data=self._datos_validos(cantidadBloques=cantidad))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["cantidadBloques"], cantidad)

    def test_sala_inactiva_no_aparece_entre_las_opciones_del_formulario(self):
        sala_inactiva = Sala.objects.create(
            nombre="Sala Inactiva Form Tests", activa=False
        )
        form = AudienciaForm()
        self.assertNotIn(sala_inactiva, form.fields["sala"].queryset)
        self.assertIn(self.sala, form.fields["sala"].queryset)

    def test_tipo_audiencia_inactivo_no_aparece_entre_las_opciones(self):
        tipo_inactivo = TipoAudiencia.objects.create(
            nombre="Tipo Inactivo Form Tests", activo=False
        )
        form = AudienciaForm()
        self.assertNotIn(tipo_inactivo, form.fields["tipoAudiencia"].queryset)
        self.assertIn(self.tipo_audiencia, form.fields["tipoAudiencia"].queryset)

    def test_competencia_inactiva_no_aparece_entre_las_opciones(self):
        competencia_inactiva = Competencia.objects.create(
            nombre="Competencia Inactiva Form Tests", activa=False
        )
        form = AudienciaForm()
        self.assertNotIn(competencia_inactiva, form.fields["competencia"].queryset)
        self.assertIn(self.competencia, form.fields["competencia"].queryset)

    def test_anotacion_es_opcional(self):
        form = AudienciaForm(data=self._datos_validos())  # sin "anotacion"
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("anotacion"), "")

    def test_anotacion_se_acepta_cuando_se_ingresa(self):
        form = AudienciaForm(
            data=self._datos_validos(anotacion="Se requiere presencia de perito.")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["anotacion"], "Se requiere presencia de perito."
        )


# =====================================================
# FORMULARIO: DEJAR SIN EFECTO (MOTIVO DE BAJA)
# =====================================================

class DejarSinEfectoAudienciaFormTests(TestCase):
    """
    Pruebas de validación de DejarSinEfectoAudienciaForm: el
    motivo es obligatorio, y "Otro" exige además una explicación.
    """

    def test_motivo_es_obligatorio(self):
        form = DejarSinEfectoAudienciaForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("motivo_seleccionado", form.errors)

    def test_motivo_invalido_es_rechazado(self):
        form = DejarSinEfectoAudienciaForm(
            data={"motivo_seleccionado": "NO_EXISTE"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("motivo_seleccionado", form.errors)

    def test_motivo_otro_sin_explicacion_es_invalido(self):
        form = DejarSinEfectoAudienciaForm(
            data={"motivo_seleccionado": MotivoBaja.OTRO}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("motivo_otro", form.errors)

    def test_motivo_otro_con_solo_espacios_es_invalido(self):
        form = DejarSinEfectoAudienciaForm(
            data={"motivo_seleccionado": MotivoBaja.OTRO, "motivo_otro": "   "}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("motivo_otro", form.errors)

    def test_motivo_otro_con_explicacion_es_valido(self):
        form = DejarSinEfectoAudienciaForm(
            data={
                "motivo_seleccionado": MotivoBaja.OTRO,
                "motivo_otro": "Se cayó el sistema del tribunal.",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.motivo_texto(),
            "Otro: Se cayó el sistema del tribunal.",
        )

    def test_motivo_distinto_de_otro_no_requiere_explicacion(self):
        for valor, etiqueta in MotivoBaja.choices:
            if valor == MotivoBaja.OTRO:
                continue
            with self.subTest(valor=valor):
                form = DejarSinEfectoAudienciaForm(
                    data={"motivo_seleccionado": valor}
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.motivo_texto(), etiqueta)
