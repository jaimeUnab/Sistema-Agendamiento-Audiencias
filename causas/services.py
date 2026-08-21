"""
Módulo de servicios (lógica de negocio) de la aplicación Causas.

Contiene ServicioImportacionCausas: procesa un archivo Excel
(.xlsx) y crea/detecta las Causa correspondientes a cada fila.

REGLA PRINCIPAL DEL DISEÑO: el sistema nunca actualiza
silenciosamente una causa ya existente. Si una fila del Excel
corresponde a una combinación Competencia + RIT que ya existe en
la base de datos, esa fila NO se guarda de inmediato: queda
reportada como "duplicado pendiente" (con los datos actuales y
los datos del Excel), para que sea el funcionario -no este
servicio- quien decida si se actualiza o se mantiene sin cambios.
Esa segunda decisión se resuelve con resolverDuplicado(), un
método aparte, invocado por la vista solo después de que el
funcionario elige.

No se integra con SIAGJ, SITFA, SITCI ni SITLA: este servicio solo
lee un archivo Excel ya exportado manualmente, tal como establece
el alcance del proyecto.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import openpyxl

from django.db import transaction

from competencias.models import Competencia

from .models import Causa


# =====================================================
# SERVICIO DE IMPORTACIÓN DE CAUSAS
# =====================================================

class ServicioImportacionCausas:
    """
    Procesa un archivo Excel (.xlsx) con causas a importar.

    Opera sobre "archivo" (un objeto tipo archivo, típicamente
    UploadedFile.cleaned_data["archivo"] de ImportarCausasForm,
    ya validado en su extensión por ese formulario). Este
    servicio NO sabe nada de HTTP: recibe el archivo y devuelve
    un diccionario estructurado; es la vista quien decide qué
    mostrar con ese resultado.

    Las cuatro columnas esperadas, en ese orden, son:
    RIT | RUC | Carátula | Competencia
    (el nombre de la competencia debe coincidir -sin distinguir
    mayúsculas/minúsculas- con una Competencia ya existente).
    """

    COLUMNAS_ESPERADAS = ["rit", "ruc", "carátula", "competencia"]

    MENSAJE_ARCHIVO_NO_LEGIBLE = (
        "No fue posible leer el archivo. Verifica que sea un "
        "Excel (.xlsx) válido, no corrupto."
    )
    MENSAJE_ARCHIVO_VACIO = (
        "El archivo no contiene ninguna fila de datos para importar."
    )
    MENSAJE_ENCABEZADOS_INCORRECTOS = (
        "Los encabezados del archivo no coinciden con los "
        "esperados. La primera fila debe ser exactamente: "
        "RIT | RUC | Carátula | Competencia."
    )

    def __init__(self, archivo):
        self.archivo = archivo

    # =================================================
    # PUNTO DE ENTRADA
    # =================================================

    def procesar(self):
        """
        Lee y procesa el archivo completo. Devuelve:
            {
                "archivoValido": bool,
                "errorArchivo": str | None,
                "creadas": [Causa, ...],
                "duplicados": [
                    {
                        "fila": int,
                        "causaId": int,
                        "rit": str,
                        "competenciaNombre": str,
                        "actual": {"ruc": str, "caratulado": str},
                        "excel": {"ruc": str, "caratulado": str},
                    },
                    ...
                ],
                "errores": [{"fila": int, "motivo": str}, ...],
            }

        Si "archivoValido" es False, las otras tres listas
        quedan vacías: no se procesó ninguna fila (el archivo
        ni siquiera pudo leerse, o sus encabezados no coinciden).

        Las causas "creadas" ya quedan guardadas en la base de
        datos al devolver este resultado (una transacción por
        fila, ver _crearCausa()); los "duplicados", en cambio,
        NO se guardan aquí -quedan pendientes de que el
        funcionario decida, ver resolverDuplicado()-.
        """

        filas = self._leerFilas()

        if filas is None:
            return self._resultadoArchivoInvalido(self.MENSAJE_ARCHIVO_NO_LEGIBLE)

        if not filas:
            return self._resultadoArchivoInvalido(self.MENSAJE_ARCHIVO_VACIO)

        encabezado = [self._limpiar(c).lower() for c in filas[0]]

        if encabezado[: len(self.COLUMNAS_ESPERADAS)] != self.COLUMNAS_ESPERADAS:
            return self._resultadoArchivoInvalido(self.MENSAJE_ENCABEZADOS_INCORRECTOS)

        filas_datos = filas[1:]

        if not filas_datos:
            return self._resultadoArchivoInvalido(self.MENSAJE_ARCHIVO_VACIO)

        creadas = []
        duplicados = []
        errores = []
        claves_vistas = set()

        # numero_fila arranca en 2: la fila 1 es el encabezado,
        # tal como las vería el funcionario abriendo el mismo
        # Excel.
        for numero_fila, fila in enumerate(filas_datos, start=2):
            resultado_fila = self._procesarFila(numero_fila, fila, claves_vistas)

            if resultado_fila["tipo"] == "error":
                errores.append(
                    {"fila": resultado_fila["fila"], "motivo": resultado_fila["motivo"]}
                )
            elif resultado_fila["tipo"] == "creada":
                creadas.append(resultado_fila["causa"])
            else:  # "duplicado"
                duplicados.append(resultado_fila["duplicado"])

        return {
            "archivoValido": True,
            "errorArchivo": None,
            "creadas": creadas,
            "duplicados": duplicados,
            "errores": errores,
        }

    # =================================================
    # LECTURA DEL ARCHIVO
    # =================================================

    def _leerFilas(self):
        """
        Devuelve una lista de filas (cada una, una tupla de
        valores de celda) leídas del archivo, o None si el
        archivo no pudo abrirse como un Excel válido.

        read_only=True: no carga el archivo completo en memoria
        como objetos de celda editables, solo lo necesario para
        recorrerlo -este servicio nunca escribe sobre el Excel.
        data_only=True: si alguna celda tuviera una fórmula, se
        lee su último valor calculado, no el texto de la
        fórmula (no se espera que el Excel exportado use
        fórmulas, pero es más seguro contemplarlo).
        """

        try:
            self.archivo.seek(0)
            libro = openpyxl.load_workbook(
                self.archivo, read_only=True, data_only=True
            )
            hoja = libro.active
            filas = list(hoja.iter_rows(values_only=True))
            libro.close()
        except Exception:
            return None

        # Descarta filas completamente vacías (todas las celdas
        # en None): un Excel exportado suele traer alguna fila
        # en blanco al final, que no debe contarse como dato ni
        # como el archivo estando "vacío" si sí hay filas útiles
        # antes.
        return [fila for fila in filas if any(c is not None for c in fila)]

    # =================================================
    # PROCESAMIENTO DE UNA FILA
    # =================================================

    def _procesarFila(self, numero_fila, fila, claves_vistas):
        """
        Valida y procesa una única fila de datos. Devuelve uno
        de estos tres dicts, según corresponda:
            {"tipo": "error", "fila": int, "motivo": str}
            {"tipo": "creada", "causa": Causa}
            {"tipo": "duplicado", "duplicado": {...}}
        """

        rit = self._limpiar(self._celda(fila, 0))
        ruc = self._limpiar(self._celda(fila, 1))
        caratulado = self._limpiar(self._celda(fila, 2))
        competencia_nombre = self._limpiar(self._celda(fila, 3))

        if not rit:
            return self._error(numero_fila, "Falta el RIT.")
        if not ruc:
            return self._error(numero_fila, "Falta el RUC.")
        if not caratulado:
            return self._error(numero_fila, "Falta la carátula.")
        if not competencia_nombre:
            return self._error(numero_fila, "Falta la competencia.")

        # Comparación insensible a mayúsculas/minúsculas: el
        # Excel es tecleado a mano por una persona, y el nombre
        # de la competencia no debería fallar por una diferencia
        # trivial de mayúsculas (el catálogo de Competencia sí
        # distingue mayúsculas al guardarse, pero para BUSCARLA
        # no hace falta esa exigencia).
        competencia = Competencia.objects.filter(
            nombre__iexact=competencia_nombre
        ).first()

        if competencia is None:
            return self._error(
                numero_fila,
                f"No existe una competencia llamada «{competencia_nombre}».",
            )

        if not competencia.activa:
            return self._error(
                numero_fila,
                f"La competencia «{competencia.nombre}» está inactiva.",
            )

        clave = (competencia.pk, rit)

        if clave in claves_vistas:
            return self._error(
                numero_fila,
                "RIT duplicado dentro del mismo archivo Excel, para la "
                "misma competencia.",
            )
        claves_vistas.add(clave)

        causa_existente = Causa.objects.filter(
            competencia=competencia, rit=rit
        ).first()

        if causa_existente is None:
            causa = self._crearCausa(competencia, rit, ruc, caratulado)
            return {"tipo": "creada", "causa": causa}

        return {
            "tipo": "duplicado",
            "duplicado": {
                "fila": numero_fila,
                "causaId": causa_existente.pk,
                "rit": rit,
                "competenciaNombre": competencia.nombre,
                "actual": {
                    "ruc": causa_existente.ruc,
                    "caratulado": causa_existente.caratulado,
                },
                "excel": {"ruc": ruc, "caratulado": caratulado},
            },
        }

    def _crearCausa(self, competencia, rit, ruc, caratulado):
        """
        Crea una Causa nueva. Cada fila se guarda en su propia
        transacción (no una única transacción para todo el
        archivo): si una fila más adelante fallara, no debe
        revertir las causas de filas anteriores que ya eran
        válidas -el objetivo de la importación es informar
        exactamente qué filas se procesaron y cuáles no, no
        exigir que el archivo sea perfecto para guardar algo-.
        """
        with transaction.atomic():
            return Causa.objects.create(
                competencia=competencia,
                rit=rit,
                ruc=ruc,
                caratulado=caratulado,
            )

    # =================================================
    # RESOLUCIÓN DE UN DUPLICADO (decisión del funcionario)
    # =================================================

    @staticmethod
    def resolverDuplicado(causa, decision, ruc_excel, caratulado_excel):
        """
        Aplica la decisión del funcionario sobre una causa
        reportada como duplicada por procesar().

        "decision" debe ser "actualizar" o "mantener" (cualquier
        otro valor se trata como "mantener", la opción segura
        por defecto: nunca se actualiza sin una instrucción
        explícita).

        Devuelve "actualizada" o "mantenida", para que la vista
        arme el resumen final.
        """

        if decision != "actualizar":
            return "mantenida"

        with transaction.atomic():
            causa.ruc = ruc_excel
            causa.caratulado = caratulado_excel
            causa.save(update_fields=["ruc", "caratulado"])

        return "actualizada"

    # =================================================
    # AUXILIARES
    # =================================================

    def _resultadoArchivoInvalido(self, motivo):
        return {
            "archivoValido": False,
            "errorArchivo": motivo,
            "creadas": [],
            "duplicados": [],
            "errores": [],
        }

    @staticmethod
    def _celda(fila, indice):
        return fila[indice] if indice < len(fila) else None

    @staticmethod
    def _error(numero_fila, motivo):
        return {"tipo": "error", "fila": numero_fila, "motivo": motivo}

    @staticmethod
    def _limpiar(valor):
        """
        Convierte una celda a texto sin espacios accidentales al
        inicio/fin. None (celda vacía) se convierte en "" para
        que las validaciones de "falta el dato" sean uniformes.
        """
        if valor is None:
            return ""
        return str(valor).strip()
