# =====================================================
# MIGRACIÓN DE DATOS
# =====================================================
# Carga inicial de las competencias oficiales del sistema.
# Es idempotente: usa get_or_create(), por lo que puede
# ejecutarse más de una vez sin generar duplicados.

from django.db import migrations

# Nombres de las competencias oficiales a cargar.
COMPETENCIAS_INICIALES = [
    "Garantía",
    "Familia",
    "Civil",
    "Laboral",
]


def cargar_competencias(apps, schema_editor):
    """
    Crea las competencias oficiales del sistema, si es que
    todavía no existen.

    Se obtiene el modelo mediante apps.get_model() (en vez
    de importarlo directamente) porque en una migración se
    debe usar la versión histórica del modelo correspondiente
    a este punto del historial de migraciones, no la versión
    actual de competencias/models.py.
    """

    Competencia = apps.get_model("competencias", "Competencia")

    for nombre in COMPETENCIAS_INICIALES:
        # get_or_create evita duplicados: si la competencia ya
        # existe, no se crea de nuevo ni se modifica.
        Competencia.objects.get_or_create(
            nombre=nombre,
            defaults={
                "descripcion": "",
                "activa": True,
            },
        )


def eliminar_competencias(apps, schema_editor):
    """
    Operación inversa: elimina únicamente las competencias
    oficiales cargadas por esta migración, permitiendo
    revertirla con "migrate competencias 0001_initial".
    """

    Competencia = apps.get_model("competencias", "Competencia")
    Competencia.objects.filter(nombre__in=COMPETENCIAS_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('competencias', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar_competencias, eliminar_competencias),
    ]
