# =====================================================
# MIGRACIÓN DE ESQUEMA
# =====================================================
# Renombra BloqueHorario.activo a
# permiteAgendamientoAutomatico. Se usa RenameField (no un
# remove + add) para que PostgreSQL conserve los valores ya
# almacenados en la columna: ningún bloque pierde su dato.
#
# El autodetector de "makemigrations" no reconoció esto como
# un rename automáticamente (al cambiar también el
# verbose_name, lo interpretó como quitar un campo y agregar
# otro), por lo que esta migración se escribió a mano con
# RenameField para evitar esa pérdida de datos.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bloques', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bloquehorario',
            old_name='activo',
            new_name='permiteAgendamientoAutomatico',
        ),
        # RenameField ya renombra la columna preservando los
        # datos. AlterField solo actualiza metadatos que
        # RenameField no toca (en este caso, el verbose_name).
        migrations.AlterField(
            model_name='bloquehorario',
            name='permiteAgendamientoAutomatico',
            field=models.BooleanField(
                default=True,
                verbose_name='Permite agendamiento automático',
            ),
        ),
    ]
