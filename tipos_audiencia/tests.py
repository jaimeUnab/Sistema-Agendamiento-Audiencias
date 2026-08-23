"""
Módulo de pruebas de la aplicación Tipos de Audiencia.

Contiene las pruebas automatizadas (Django Test Framework) del
modelo TipoAudiencia, de la vista de solo lectura
lista_tipos_audiencia, del alta y edición (crear_tipo_audiencia/
editar_tipo_audiencia) y de los permisos que protegen las tres
(módulo de Configuración, exclusivo de rol Administrador).

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

# Permite leer los mensajes (django.contrib.messages) que quedaron
# disponibles para la request final de la respuesta.
from django.contrib.messages import get_messages

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

    def test_botones_nuevo_y_editar_apuntan_a_urls_reales(self):
        """
        Los botones "Nuevo" y "Editar" ya no apuntan a "#": deben
        enlazar a las URLs reales de crear_tipo_audiencia y
        editar_tipo_audiencia. No se verifica la ausencia genérica
        de 'href="#"' en toda la página: base_dashboard.html (menú
        lateral, compartido por todo el sistema) tiene enlaces
        legítimos con ancla ("#menuAgenda", "#menuConfiguracion")
        y hasta un comentario HTML que menciona textualmente
        'href="#"' al documentar un enlace ya corregido en otra
        pantalla -nada de eso tiene que ver con esta prueba-.
        """
        tipo = TipoAudiencia.objects.create(nombre="Vista Botones Reales")

        respuesta = self.client.get(reverse("lista_tipos_audiencia"))

        self.assertContains(respuesta, reverse("crear_tipo_audiencia"))
        self.assertContains(
            respuesta, reverse("editar_tipo_audiencia", args=[tipo.pk])
        )


# =====================================================
# 2B. ALTA (crear_tipo_audiencia)
# =====================================================

class CrearTipoAudienciaTests(TestCase):
    """
    Pruebas del caso de uso "Crear Tipo de Audiencia" (vista
    crear_tipo_audiencia), ya autenticado con un usuario con acceso
    (rol Administrador). Mismo patrón que CrearSalaTests
    (salas/tests.py).
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_crear_tipo",
            email="pruebas_crear_tipo@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.force_login(self.usuario)

    def test_get_muestra_el_formulario_vacio(self):
        """
        Un GET a crear_tipo_audiencia muestra el formulario vacío,
        sin crear ningún registro (comprobación explícita de que
        GET no modifica nada).
        """
        respuesta = self.client.get(reverse("crear_tipo_audiencia"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "tipos_audiencia/formulario.html")
        self.assertIn("form", respuesta.context)
        self.assertEqual(TipoAudiencia.objects.count(), 0)

    def test_usuario_autenticado_puede_crear_tipo_audiencia(self):
        """
        Un usuario autenticado puede crear un tipo de audiencia
        mediante un POST válido: la respuesta redirige al listado,
        el registro queda almacenado en la base de datos (con la
        descripción y el estado indicados) y se muestra el mensaje
        de éxito.
        """
        respuesta = self.client.post(
            reverse("crear_tipo_audiencia"),
            {
                "nombre": "Tipo de Pruebas 1",
                "descripcion": "Descripción de prueba",
                "activo": True,
            },
            follow=True,
        )

        # El POST responde correctamente y redirige al listado.
        self.assertRedirects(respuesta, reverse("lista_tipos_audiencia"))

        # El tipo de audiencia queda almacenado en la base de datos,
        # con exactamente los datos enviados.
        tipo = TipoAudiencia.objects.filter(nombre="Tipo de Pruebas 1").first()
        self.assertIsNotNone(tipo)
        self.assertEqual(tipo.descripcion, "Descripción de prueba")
        self.assertTrue(tipo.activo)

        # Se muestra el mensaje de éxito.
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertIn(
            "Tipo de audiencia «Tipo de Pruebas 1» creado correctamente.",
            mensajes,
        )

    def test_nombre_es_obligatorio(self):
        """
        Un POST sin "nombre" no crea ningún registro: el formulario
        vuelve a mostrarse con errores de validación (sin
        redirección), tal como exige el campo real del modelo
        (nombre no admite blank).
        """
        respuesta = self.client.post(
            reverse("crear_tipo_audiencia"),
            {"nombre": "", "descripcion": "", "activo": True},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors)
        self.assertIn("nombre", respuesta.context["form"].errors)
        self.assertEqual(TipoAudiencia.objects.count(), 0)

    def test_get_no_crea_ningun_registro(self):
        """
        Un GET no debe poder crear un tipo de audiencia: la vista
        solo guarda ante un POST válido (ver el "if request.method
        == 'POST'" de crear_tipo_audiencia).
        """
        self.client.get(
            f"{reverse('crear_tipo_audiencia')}"
            f"?nombre=Intento por GET&descripcion=&activo=True"
        )

        self.assertEqual(TipoAudiencia.objects.count(), 0)


class NombreDuplicadoTipoAudienciaTests(TestCase):
    """
    Pruebas de la validación de nombre único al crear un tipo de
    audiencia (TipoAudiencia.nombre ya lo exige como unique=True,
    ver tipos_audiencia/models.py). Mismo patrón que
    NombreDuplicadoSalaTests (salas/tests.py).
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_dup_tipo",
            email="pruebas_dup_tipo@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.force_login(self.usuario)

        # Tipo de audiencia ya existente, usado para forzar la
        # colisión de nombre en la prueba.
        self.tipo_existente = TipoAudiencia.objects.create(
            nombre="Tipo Compartido"
        )

    def test_no_permite_crear_tipo_audiencia_con_nombre_duplicado(self):
        """
        Un POST con un nombre ya registrado no crea un segundo
        registro: el formulario vuelve a mostrarse con errores de
        validación (sin redirección).
        """
        respuesta = self.client.post(
            reverse("crear_tipo_audiencia"),
            {"nombre": "Tipo Compartido", "descripcion": "", "activo": True},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors)
        self.assertIn("nombre", respuesta.context["form"].errors)

        # No se crea un segundo registro: sigue existiendo un único
        # tipo de audiencia con ese nombre.
        self.assertEqual(
            TipoAudiencia.objects.filter(nombre="Tipo Compartido").count(), 1
        )


# =====================================================
# 2C. EDICIÓN (editar_tipo_audiencia)
# =====================================================

class EditarTipoAudienciaTests(TestCase):
    """
    Pruebas del caso de uso "Editar Tipo de Audiencia" (vista
    editar_tipo_audiencia). Mismo patrón que las pruebas de
    editar_sala.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="usuario_pruebas_editar_tipo",
            email="pruebas_editar_tipo@tribunal.cl",
            password="ClaveSegura123",
            nombre="Usuario de Pruebas",
            rol=RolUsuario.ADMINISTRADOR,
        )
        self.client.force_login(self.usuario)

        self.tipo = TipoAudiencia.objects.create(
            nombre="Tipo Editar Original",
            descripcion="Descripción original",
            activo=True,
        )

    def test_get_muestra_el_formulario_precargado(self):
        """
        Un GET a editar_tipo_audiencia muestra el formulario ya
        completado con los datos actuales del registro.
        """
        respuesta = self.client.get(
            reverse("editar_tipo_audiencia", args=[self.tipo.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "tipos_audiencia/formulario.html")
        self.assertEqual(
            respuesta.context["form"].instance.pk, self.tipo.pk
        )
        self.assertContains(respuesta, "Tipo Editar Original")

    def test_usuario_autenticado_puede_editar_tipo_audiencia(self):
        """
        Un POST válido actualiza el registro existente (no crea uno
        nuevo), redirige al listado, los datos modificados quedan
        persistidos en la base de datos y se muestra el mensaje de
        éxito.
        """
        respuesta = self.client.post(
            reverse("editar_tipo_audiencia", args=[self.tipo.pk]),
            {
                "nombre": "Tipo Editar Modificado",
                "descripcion": "Descripción modificada",
                "activo": False,
            },
            follow=True,
        )

        self.assertRedirects(respuesta, reverse("lista_tipos_audiencia"))

        # No se creó un segundo registro: sigue existiendo uno solo.
        self.assertEqual(TipoAudiencia.objects.count(), 1)

        # Los datos modificados quedan persistidos en la base de
        # datos (se recarga la instancia, no se confía en la que
        # ya estaba en memoria).
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo Editar Modificado")
        self.assertEqual(self.tipo.descripcion, "Descripción modificada")
        self.assertFalse(self.tipo.activo)

        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertIn(
            "Tipo de audiencia «Tipo Editar Modificado» actualizado correctamente.",
            mensajes,
        )

    def test_edicion_respeta_la_validacion_de_nombre_unico(self):
        """
        Editar un tipo de audiencia para que su nombre coincida con
        el de OTRO ya existente tampoco se permite: misma validación
        de unicidad que al crear.
        """
        TipoAudiencia.objects.create(nombre="Tipo Editar Otro")

        respuesta = self.client.post(
            reverse("editar_tipo_audiencia", args=[self.tipo.pk]),
            {
                "nombre": "Tipo Editar Otro",
                "descripcion": "",
                "activo": True,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors)
        self.assertIn("nombre", respuesta.context["form"].errors)

        # El registro original no cambió.
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo Editar Original")

    def test_editar_tipo_audiencia_inexistente_responde_404(self):
        """
        Editar un pk que no corresponde a ningún TipoAudiencia
        responde 404 (get_object_or_404), mismo criterio que
        editar_sala.
        """
        respuesta = self.client.get(
            reverse("editar_tipo_audiencia", args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_get_no_modifica_el_registro(self):
        """
        Un GET no debe poder modificar el registro: la vista solo
        guarda ante un POST válido.
        """
        self.client.get(
            f"{reverse('editar_tipo_audiencia', args=[self.tipo.pk])}"
            f"?nombre=Intento por GET"
        )

        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo Editar Original")


# =====================================================
# 3. PERMISOS / AUTENTICACIÓN
# =====================================================

class PermisosListaTiposAudienciaTests(TestCase):
    """
    Pruebas de control de acceso de lista_tipos_audiencia,
    crear_tipo_audiencia y editar_tipo_audiencia: solo usuarios
    autenticados con rol Administrador (o superusuarios de Django)
    pueden acceder a las tres.
    """

    def setUp(self):
        self.tipo = TipoAudiencia.objects.create(nombre="Tipo Permisos")

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

    def test_crear_tipo_audiencia_requiere_login(self):
        """
        Mismo criterio que test_requiere_login, aplicado a
        crear_tipo_audiencia.
        """
        respuesta = self.client.get(reverse("crear_tipo_audiencia"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)

    def test_editar_tipo_audiencia_requiere_login(self):
        """
        Mismo criterio que test_requiere_login, aplicado a
        editar_tipo_audiencia.
        """
        respuesta = self.client.get(
            reverse("editar_tipo_audiencia", args=[self.tipo.pk])
        )

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

    def test_usuario_sin_rol_administrador_no_puede_crear_tipo_audiencia(self):
        """
        Mismo criterio que test_usuario_sin_rol_administrador_recibe_403,
        aplicado a crear_tipo_audiencia (tanto GET como POST).
        """
        self.client.login(
            username=self.usuario_comun.email, password="ClaveSegura123"
        )

        respuesta = self.client.get(reverse("crear_tipo_audiencia"))
        self.assertEqual(respuesta.status_code, 403)

        respuesta = self.client.post(
            reverse("crear_tipo_audiencia"),
            {"nombre": "Intento Sin Permiso", "descripcion": "", "activo": True},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(
            TipoAudiencia.objects.filter(nombre="Intento Sin Permiso").exists()
        )

    def test_usuario_sin_rol_administrador_no_puede_editar_tipo_audiencia(self):
        """
        Mismo criterio que test_usuario_sin_rol_administrador_recibe_403,
        aplicado a editar_tipo_audiencia.
        """
        self.client.login(
            username=self.usuario_comun.email, password="ClaveSegura123"
        )

        respuesta = self.client.get(
            reverse("editar_tipo_audiencia", args=[self.tipo.pk])
        )
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
