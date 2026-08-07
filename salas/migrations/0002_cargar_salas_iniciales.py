# =====================================================
# MIGRACIÓN DE DATOS
# =====================================================
# Carga inicial de las salas oficiales del sistema.
# Es idempotente: usa get_or_create(), por lo que puede
# ejecutarse más de una vez sin generar duplicados.

from django.db import migrations

# Nombres de las salas oficiales a cargar.
SALAS_INICIALES = [
    "Sala 1",
    "Sala 2",
]


def cargar_salas(apps, schema_editor):
    """
    Crea las salas oficiales del sistema, si es que
    todavía no existen.

    Se obtiene el modelo mediante apps.get_model() (en vez
    de importarlo directamente) porque en una migración se
    debe usar la versión histórica del modelo correspondiente
    a este punto del historial de migraciones, no la versión
    actual de salas/models.py.
    """

    Sala = apps.get_model("salas", "Sala")

    for nombre in SALAS_INICIALES:
        # get_or_create evita duplicados: si la sala ya
        # existe, no se crea de nuevo ni se modifica.
        Sala.objects.get_or_create(
            nombre=nombre,
            defaults={
                "activa": True,
            },
        )


def eliminar_salas(apps, schema_editor):
    """
    Operación inversa: elimina únicamente las salas
    oficiales cargadas por esta migración, permitiendo
    revertirla con "migrate salas 0001_initial".
    """

    Sala = apps.get_model("salas", "Sala")
    Sala.objects.filter(nombre__in=SALAS_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('salas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar_salas, eliminar_salas),
    ]
