"""
Migración de RunSQL (sin cambios de esquema): agrega un trigger de
PostgreSQL que bloquea, a nivel de base de datos, cualquier UPDATE o
DELETE sobre audiencias_registrotrazabilidad.

Motivo: RegistroTrazabilidad es un registro de auditoría -lo crea
ServicioTrazabilidad (audiencias/services.py) y nada más en el
proyecto lo modifica ni lo elimina-, pero hasta esta migración esa
regla solo existía a nivel de aplicación (nadie en el código lo
hace), sin ninguna barrera real si alguien se conecta directo a la
base de datos. Un CHECK constraint o un permiso GRANT/REVOKE no
alcanzan aquí: el usuario con el que Django se conecta
(config/settings.py: DATABASES) es superusuario de PostgreSQL, y un
superusuario ignora cualquier REVOKE. Un trigger si funciona: es
lógica procedural ligada a la tabla, no una verificación de
privilegios, así que se ejecuta sin importar quién ejecute la
sentencia.

reverse_sql deja la migración completamente reversible: elimina el
trigger y la función, sin afectar ninguna fila ni ninguna otra
migración.
"""

from django.db import migrations

CREAR_TRIGGER = """
CREATE OR REPLACE FUNCTION bloquear_modificacion_registrotrazabilidad()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'RegistroTrazabilidad es un registro de auditoria de solo lectura: no se permite UPDATE ni DELETE.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloquear_modificacion_registrotrazabilidad
BEFORE UPDATE OR DELETE ON audiencias_registrotrazabilidad
FOR EACH ROW EXECUTE FUNCTION bloquear_modificacion_registrotrazabilidad();
"""

ELIMINAR_TRIGGER = """
DROP TRIGGER IF EXISTS trg_bloquear_modificacion_registrotrazabilidad
    ON audiencias_registrotrazabilidad;

DROP FUNCTION IF EXISTS bloquear_modificacion_registrotrazabilidad();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('audiencias', '0004_audiencia_anotacion'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREAR_TRIGGER,
            reverse_sql=ELIMINAR_TRIGGER,
        ),
    ]
