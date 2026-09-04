"""
Migración de RunSQL (sin cambios de esquema): agrega un trigger de
PostgreSQL que bloquea, a nivel de base de datos, cualquier UPDATE o
DELETE sobre usuarios_registroacceso.

Mismo motivo y mismo criterio que la migración equivalente de
audiencias (0005_bloquear_modificacion_registrotrazabilidad):
RegistroAcceso es un registro de auditoría -lo crea
ServicioRegistroAcceso (usuarios/services.py) y nada más en el
proyecto lo modifica ni lo elimina; el admin ya lo protege
(usuarios/admin.py: has_add/change/delete_permission=False)-, pero
esa regla solo existía a nivel de aplicación. El usuario con el que
Django se conecta es superusuario de PostgreSQL, así que un
GRANT/REVOKE no serviría (un superusuario lo ignora); un trigger sí,
porque es lógica procedural ligada a la tabla, no una verificación
de privilegios.

reverse_sql deja la migración completamente reversible: elimina el
trigger y la función, sin afectar ninguna fila.
"""

from django.db import migrations

CREAR_TRIGGER = """
CREATE OR REPLACE FUNCTION bloquear_modificacion_registroacceso()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'RegistroAcceso es un registro de auditoria de solo lectura: no se permite UPDATE ni DELETE.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloquear_modificacion_registroacceso
BEFORE UPDATE OR DELETE ON usuarios_registroacceso
FOR EACH ROW EXECUTE FUNCTION bloquear_modificacion_registroacceso();
"""

ELIMINAR_TRIGGER = """
DROP TRIGGER IF EXISTS trg_bloquear_modificacion_registroacceso
    ON usuarios_registroacceso;

DROP FUNCTION IF EXISTS bloquear_modificacion_registroacceso();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_registroacceso'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREAR_TRIGGER,
            reverse_sql=ELIMINAR_TRIGGER,
        ),
    ]
