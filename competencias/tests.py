"""
Módulo de pruebas de la aplicación Competencias.

Contiene las pruebas automatizadas (Django Test Framework) del
modelo Competencia, de la vista de solo lectura lista_competencias,
de los permisos que la protegen (módulo de Configuración, exclusivo
de rol Administrador), y de la carga inicial de las competencias
oficiales (migración 0002_cargar_competencias_iniciales).

No se prueba aquí ningún CRUD (crear/editar/eliminar/activar-
desactivar): esta app no lo tiene, es un catálogo de solo lectura
desde la interfaz. Tampoco se repiten las pruebas que ya cubren el
uso de Competencia desde otras apps (por ejemplo, "competencia
inactiva" o "competencia inexistente" en causas/tests/
test_services_unit.py): esas ya están cubiertas donde corresponde.

Cada clase de prueba usa django.test.TestCase, que envuelve cada
método de prueba en su propia transacción y la revierte al
finalizar: no es necesario limpiar manualmente los datos creados en
cada prueba (incluidas las cuatro competencias oficiales que ya trae
la base de datos de pruebas por la migración de datos), y ninguna
prueba depende del estado que haya dejado otra.
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

# Competencias es un módulo de Configuración: su vista exige rol
# Administrador (ver usuarios/decorators.py:solo_administrador).
from usuarios.models import RolUsuario

from .models import Competencia

Usuario = get_user_model()


# =====================================================
# COMPETENCIAS OFICIALES (mismos nombres que la migración de datos)
# =====================================================
# Ver competencias/migrations/0002_cargar_competencias_iniciales.py.
# Se repiten aquí, no se importan desde la migración: una migración
# de datos no está pensada para reutilizarse como módulo, y estos
# nombres son, en sí mismos, el contrato que se está verificando.

COMPETENCIAS_OFICIALES = ["Garantía", "Familia", "Civil", "Laboral"]


# =====================================================
# 1. MODELO
# =====================================================

class CompetenciaModelTests(TestCase):
    """
    Pruebas unitarias del modelo Competencia.
    """

    def test_str_devuelve_el_nombre(self):
        """
        __str__ debe devolver exactamente el nombre: es lo que
        usan ReglaAgendamiento.__str__, DiaAtencion.__str__, el
        admin y el template de esta misma app.
        """
        competencia = Competencia.objects.create(
            nombre="Competencia Modelo Uno"
        )

        self.assertEqual(str(competencia), "Competencia Modelo Uno")

    def test_nombre_es_unico(self):
        """
        No pueden existir dos Competencia con el mismo nombre: es
        la garantía en la que confía causas/services.py
        (ServicioImportacionCausas) al buscar
        Competencia.objects.filter(nombre__iexact=...).first(),
        esperando como máximo una coincidencia.
        """
        Competencia.objects.create(nombre="Competencia Modelo Duplicada")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Competencia.objects.create(
                    nombre="Competencia Modelo Duplicada"
                )

    def test_activa_es_true_por_defecto(self):
        """
        Una Competencia recién creada sin especificar "activa"
        queda activa=True. ServicioImportacionCausas decide si
        rechaza una fila del Excel según este valor, así que el
        default real importa, no solo el declarado en el modelo.
        """
        competencia = Competencia.objects.create(
            nombre="Competencia Modelo Activa"
        )

        self.assertTrue(competencia.activa)

    def test_ordering_por_nombre_por_defecto(self):
        """
        Competencia.objects.all() (sin order_by explícito) ya
        devuelve las instancias ordenadas alfabéticamente por
        nombre (Meta.ordering). Otras pantallas del sistema (por
        ejemplo, la matriz de días de atención en
        reglas_agendamiento) dependen de este orden por defecto.
        """
        Competencia.objects.create(nombre="Orden Modelo - Zeta")
        Competencia.objects.create(nombre="Orden Modelo - Alfa")
        Competencia.objects.create(nombre="Orden Modelo - Beta")

        nombres = list(
            Competencia.objects.filter(
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
# 2. VISTA (lista_competencias)
# =====================================================

class ListaCompetenciasViewTests(TestCase):
    """
    Pruebas de integración de la vista lista_competencias, ya
    autenticado con un usuario con acceso (rol Administrador). Los
    permisos en sí -quién puede o no entrar- se prueban aparte, en
    PermisosListaCompetenciasTests.
    """

    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin_vista_competencias",
            email="admin_vista_competencias@tribunal.cl",
            password="ClaveSegura123",
            nombre="Admin Vista Competencias",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.login(
            username=self.administrador.email, password="ClaveSegura123"
        )

    def test_administrador_ve_las_competencias_ordenadas_por_nombre(self):
        """
        La respuesta usa el template correcto y el contexto
        "competencias" llega ordenado por nombre, tal como arma la
        propia vista (order_by("nombre")).
        """
        Competencia.objects.create(nombre="Vista Zeta")
        Competencia.objects.create(nombre="Vista Alfa")

        respuesta = self.client.get(reverse("lista_competencias"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "competencias/lista.html")

        nombres = [c.nombre for c in respuesta.context["competencias"]]
        self.assertEqual(nombres, sorted(nombres))
        self.assertIn("Vista Alfa", nombres)
        self.assertIn("Vista Zeta", nombres)

    def test_muestra_competencias_activas_e_inactivas(self):
        """
        La vista no filtra por "activa": una competencia inactiva
        también debe aparecer en el listado, con su badge
        "Inactiva" (mismo criterio documentado en el template:
        catálogo de solo lectura, sin ocultar registros).
        """
        Competencia.objects.create(
            nombre="Vista Competencia Activa", activa=True
        )
        Competencia.objects.create(
            nombre="Vista Competencia Baja", activa=False
        )

        respuesta = self.client.get(reverse("lista_competencias"))

        self.assertContains(respuesta, "Vista Competencia Activa")
        self.assertContains(respuesta, "Vista Competencia Baja")
        self.assertContains(respuesta, "Inactiva")

    def test_listado_vacio_muestra_mensaje(self):
        """
        Sin ninguna Competencia registrada (incluidas las cuatro
        oficiales, eliminadas a propósito en esta prueba), se
        muestra el mensaje del bloque {% empty %} del template, en
        vez de una tabla vacía sin explicación.
        """
        Competencia.objects.all().delete()

        respuesta = self.client.get(reverse("lista_competencias"))

        self.assertContains(
            respuesta, "No existen competencias registradas."
        )


# =====================================================
# 3. PERMISOS / AUTENTICACIÓN
# =====================================================

class PermisosListaCompetenciasTests(TestCase):
    """
    Pruebas de control de acceso de lista_competencias: solo
    usuarios autenticados con rol Administrador (o superusuarios de
    Django) pueden acceder.
    """

    def setUp(self):
        self.usuario_comun = Usuario.objects.create_user(
            username="usuario_permisos_competencias",
            email="usuario_permisos_competencias@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario Común Permisos Competencias",
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
            username="superusuario_sin_rol_competencias",
            email="superusuario_sin_rol_competencias@tribunal.cl",
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
        respuesta = self.client.get(reverse("lista_competencias"))

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

        respuesta = self.client.get(reverse("lista_competencias"))

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

        respuesta = self.client.get(reverse("lista_competencias"))

        self.assertEqual(respuesta.status_code, 200)


# =====================================================
# 4. CARGA INICIAL DE COMPETENCIAS (migración de datos)
# =====================================================

class CargaInicialCompetenciasIntegrationTests(TestCase):
    """
    Pruebas de integración sobre el efecto de
    0002_cargar_competencias_iniciales: no vuelven a ejecutar la
    migración (ya se aplicó al construir la base de datos de
    pruebas), verifican el estado que dejó en la base de datos.

    Es la base sobre la que se apoyan reglas de plazo legal, días
    de atención e importación de causas por nombre: si esta carga
    se rompe, esas otras apps fallan en cascada.
    """

    def test_existen_las_cuatro_competencias_oficiales(self):
        nombres = set(
            Competencia.objects.filter(
                nombre__in=COMPETENCIAS_OFICIALES
            ).values_list("nombre", flat=True)
        )

        self.assertEqual(nombres, set(COMPETENCIAS_OFICIALES))

    def test_no_existen_competencias_duplicadas(self):
        """
        get_or_create() en la migración debe cumplir lo que
        promete: como máximo una fila por cada nombre oficial.
        """
        for nombre in COMPETENCIAS_OFICIALES:
            self.assertEqual(
                Competencia.objects.filter(nombre=nombre).count(), 1
            )

    def test_competencias_oficiales_quedan_activas_y_sin_descripcion(self):
        """
        Son exactamente los "defaults" que usa
        cargar_competencias(): activa=True, descripcion="". Si
        cambiaran sin querer, causas/reglas_agendamiento
        empezarían a comportarse distinto sin que nadie tocara esas
        apps.
        """
        for nombre in COMPETENCIAS_OFICIALES:
            competencia = Competencia.objects.get(nombre=nombre)
            self.assertTrue(competencia.activa)
            self.assertEqual(competencia.descripcion, "")
