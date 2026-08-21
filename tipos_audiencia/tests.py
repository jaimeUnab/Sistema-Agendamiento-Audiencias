"""
Módulo de pruebas de la aplicación Tipos de Audiencia.

Contiene las pruebas automatizadas (Django Test Framework) del
modelo TipoAudiencia, de la vista de solo lectura
lista_tipos_audiencia, y de los permisos que la protegen (módulo de
Configuración, exclusivo de rol Administrador).

No se prueba aquí ningún CRUD (crear/editar): el template ya
contiene los botones "Nuevo"/"Editar", pero apuntan a "#" y están
marcados explícitamente como "Todavía no implementado (HU-13 solo
cubre el listado)" -no existen vistas ni urls para eso todavía-.

Tampoco hay pruebas de "carga inicial de datos": a diferencia de
competencias (que sí tiene una migración de datos,
0002_cargar_competencias_iniciales), tipos_audiencia no siembra
ningún registro: el catálogo nace vacío.

Y tampoco se repite aquí la prueba de que un TipoAudiencia inactivo
queda fuera del <select> de AudienciaForm: ya está cubierta en
audiencias/tests/test_forms_unit.py
(test_tipo_audiencia_inactivo_no_aparece_entre_las_opciones).

Cada clase de prueba usa django.test.TestCase, que envuelve cada
método de prueba en su propia transacción y la revierte al
finalizar: no es necesario limpiar manualmente los datos creados en
cada prueba, y ninguna prueba depende del estado que haya dejado
otra.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

# Permite crear usuarios de prueba sin acoplarse directamente a la
# clase Usuario (buena práctica recomendada por Django cuando el
# proyecto usa un modelo de usuario personalizado).
from django.contrib.auth import get_user_model

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

# Tipos de Audiencia es un módulo de Configuración: su vista exige
# rol Administrador (ver usuarios/decorators.py:solo_administrador).
from usuarios.models import RolUsuario

from .models import TipoAudiencia

Usuario = get_user_model()


# =====================================================
# 1. MODELO
# =====================================================

class TipoAudienciaModelTests(TestCase):
    """
    Pruebas unitarias del modelo TipoAudiencia.
    """

    def test_str_devuelve_el_nombre(self):
        """
        __str__ debe devolver exactamente el nombre: es lo que
        usan ReglaAgendamiento.__str__, el admin y el <select> de
        AudienciaForm.
        """
        tipo = TipoAudiencia.objects.create(
            nombre="Tipo Modelo Uno"
        )

        self.assertEqual(str(tipo), "Tipo Modelo Uno")

    def test_nombre_es_unico(self):
        """
        No pueden existir dos TipoAudiencia con el mismo nombre:
        desde que se convirtió en catálogo transversal (migración
        0002_alter_tipoaudiencia_options_and_more, que le quitó la
        relación con Competencia), la unicidad ya no depende de
        ninguna otra combinación.
        """
        TipoAudiencia.objects.create(nombre="Tipo Modelo Duplicado")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TipoAudiencia.objects.create(
                    nombre="Tipo Modelo Duplicado"
                )

    def test_activo_es_true_por_defecto(self):
        """
        Un TipoAudiencia recién creado sin especificar "activo"
        queda activo=True. Es el valor del que depende el
        queryset.filter(activo=True) de AudienciaForm
        (audiencias/forms.py), así que el default real importa.
        """
        tipo = TipoAudiencia.objects.create(
            nombre="Tipo Modelo Activo"
        )

        self.assertTrue(tipo.activo)

    def test_ordering_por_nombre_por_defecto(self):
        """
        TipoAudiencia.objects.all() (sin order_by explícito) ya
        devuelve las instancias ordenadas alfabéticamente por
        nombre (Meta.ordering).
        """
        TipoAudiencia.objects.create(nombre="Orden Modelo - Zeta")
        TipoAudiencia.objects.create(nombre="Orden Modelo - Alfa")
        TipoAudiencia.objects.create(nombre="Orden Modelo - Beta")

        nombres = list(
            TipoAudiencia.objects.filter(
                nombre__startswith="Orden Modelo"
            ).values_list("nombre", flat=True)
        )

        self.assertEqual(
            nombres,
            [
                "Orden Modelo - Alfa",
                "Orden Modelo - Beta",
                "Orden Modelo - Zeta",
            ],
        )


# =====================================================
# 2. VISTA (lista_tipos_audiencia)
# =====================================================

class ListaTiposAudienciaViewTests(TestCase):
    """
    Pruebas de integración de la vista lista_tipos_audiencia, ya
    autenticado con un usuario con acceso (rol Administrador). Los
    permisos en sí -quién puede o no entrar- se prueban aparte, en
    PermisosListaTiposAudienciaTests.
    """

    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin_vista_tipos_audiencia",
            email="admin_vista_tipos_audiencia@tribunal.cl",
            password="ClaveSegura123",
            nombre="Admin Vista Tipos Audiencia",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

    def test_administrador_ve_los_tipos_de_audiencia_ordenados_por_nombre(self):
        """
        La respuesta usa el template correcto y el contexto
        "tipos_audiencia" llega ordenado por nombre, tal como arma
        la propia vista (order_by("nombre")).
        """
        TipoAudiencia.objects.create(nombre="Vista Zeta")
        TipoAudiencia.objects.create(nombre="Vista Alfa")

        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "tipos_audiencia/lista.html")

        nombres = [t.nombre for t in respuesta.context["tipos_audiencia"]]
        self.assertEqual(nombres, sorted(nombres))
        self.assertIn("Vista Alfa", nombres)
        self.assertIn("Vista Zeta", nombres)

    def test_muestra_tipos_activos_e_inactivos(self):
        """
        La vista no filtra por "activo" (a diferencia del <select>
        de AudienciaForm, que sí filtra): un tipo de audiencia
        inactivo también debe aparecer en el listado, con su badge
        "Inactivo".
        """
        TipoAudiencia.objects.create(
            nombre="Vista Tipo Activo", activo=True
        )
        TipoAudiencia.objects.create(
            nombre="Vista Tipo Baja", activo=False
        )

        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertContains(respuesta, "Vista Tipo Activo")
        self.assertContains(respuesta, "Vista Tipo Baja")
        self.assertContains(respuesta, "Inactivo")

    def test_listado_vacio_muestra_mensaje(self):
        """
        Sin ningún TipoAudiencia registrado, se muestra el mensaje
        del bloque {% empty %} del template. A diferencia de
        competencias (donde hay que borrar los registros que trae
        la migración de datos), aquí es el estado real por
        defecto: tipos_audiencia no siembra ningún dato inicial.
        """
        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertContains(
            respuesta, "No existen tipos de audiencia registrados."
        )


# =====================================================
# 3. PERMISOS / AUTENTICACIÓN
# =====================================================

class PermisosListaTiposAudienciaTests(TestCase):
    """
    Pruebas de control de acceso de lista_tipos_audiencia: solo
    usuarios autenticados con rol Administrador (o superusuarios de
    Django) pueden acceder.
    """

    def setUp(self):
        self.usuario_comun = Usuario.objects.create_user(
            username="usuario_permisos_tipos_audiencia",
            email="usuario_permisos_tipos_audiencia@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Común Permisos Tipos Audiencia",
            rol=RolUsuario.USUARIO,
        )

        # Superusuario de Django cuyo campo "rol" NO quedó en
        # Administrador (creado con create_user, no con
        # create_superuser: create_superuser fuerza
        # rol=ADMINISTRADOR -ver usuarios/models.py:
        # UsuarioManager-, lo que ocultaría el caso que
        # solo_administrador está pensado para cubrir). Se pasa
        # is_superuser/is_staff directamente como extra_fields.
        self.superusuario_sin_rol = Usuario.objects.create_user(
            username="superusuario_sin_rol_tipos_audiencia",
            email="superusuario_sin_rol_tipos_audiencia@tribunal.cl",
            password="ClaveSegura123",
            nombre="Superusuario Sin Rol Administrador",
            rol=RolUsuario.USUARIO,
            is_superuser=True,
            is_staff=True,
        )

    def test_requiere_login(self):
        """
        Un usuario anónimo es redirigido al login (@login_required),
        no recibe un 403: "no iniciaste sesión" es distinto de "no
        tienes permiso".
        """
        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_usuario_sin_rol_administrador_recibe_403(self):
        """
        Un usuario autenticado con rol=USUARIO recibe 403
        (PermissionDenied), no un redirect: es la regla de negocio
        real de solo_administrador.
        """
        self.client.login(
            username=self.usuario_comun.email, password="ClaveSegura123"
        )

        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertEqual(respuesta.status_code, 403)

    def test_superusuario_puede_acceder_sin_rol_administrador(self):
        """
        Un superusuario de Django puede acceder aunque su campo
        "rol" no sea Administrador -caso borde documentado
        explícitamente en el docstring de solo_administrador, para
        no dejar a un superusuario bloqueado fuera de un módulo de
        Configuración-.
        """
        self.client.login(
            username=self.superusuario_sin_rol.email,
            password="ClaveSegura123",
        )

        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertEqual(respuesta.status_code, 200)
