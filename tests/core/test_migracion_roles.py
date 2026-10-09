"""La migración core/002 (roles armables, ADR-0020) dice lo mismo que el código.

Se lee el `.sql` como texto, sin base: la semilla tiene que ser `SEMILLA`, sus
claves tienen que existir en el catálogo de pantallas, las tablas tienen que
tener las columnas de los modelos, y el archivo tiene que ser seguro de aplicar
con el método que lo corta por `;`.
"""
import re
from pathlib import Path

import app.core.models  # noqa: F401  (registra rol, rol_permiso y usuario_rol)
from app.core.database import Base
from app.modulos import REGISTRO
from tests.roles_de_prueba import SEMILLA

RAIZ = Path(__file__).resolve().parents[2]
MIGRACION = RAIZ / "migrations" / "core" / "002_roles_y_permisos.sql"

FILA_SEMILLA = re.compile(
    r"SELECT\s+'([^']+)'\s+AS\s+rol,\s*'([^']+)'\s+AS\s+modulo,"
    r"\s*'([^']+)'\s+AS\s+pantalla,\s*'([^']+)'\s+AS\s+nivel",
    re.IGNORECASE,
)
FILA_ROL = re.compile(r"SELECT\s+'([^']+)'\s+AS\s+nombre", re.IGNORECASE)
CREATE_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\)\s*ENGINE", re.IGNORECASE | re.DOTALL
)
NO_SON_COLUMNAS = {"UNIQUE", "CONSTRAINT", "PRIMARY", "KEY", "INDEX", "FOREIGN"}


def _sql() -> str:
    return MIGRACION.read_text(encoding="utf-8")


def _catalogo() -> dict:
    """{(módulo, pantalla): Pantalla} de todos los módulos del registro."""
    return {(m.clave, p.clave): p for m in REGISTRO for p in m.pantallas}


# (a) La semilla del SQL es exactamente SEMILLA.

def test_semilla_del_sql_es_la_de_los_tests():
    filas = FILA_SEMILLA.findall(_sql())
    assert len(filas) == 12
    assert sorted(filas) == sorted(SEMILLA)


def test_los_roles_que_se_crean_son_los_de_la_semilla():
    nombres = FILA_ROL.findall(_sql())
    assert sorted(nombres) == sorted({rol for rol, *_ in SEMILLA})


# (b) Cada (módulo, pantalla) existe y `editar` sólo va en pantallas editables.

def test_semilla_usa_pantallas_del_catalogo():
    catalogo = _catalogo()
    inexistentes = [(m, p) for _, m, p, _ in SEMILLA if (m, p) not in catalogo]
    assert inexistentes == []


def test_semilla_no_da_editar_en_pantallas_de_solo_ver():
    catalogo = _catalogo()
    assert {n for *_, n in SEMILLA} <= {"ver", "editar"}
    mal = [
        (r, m, p) for r, m, p, n in SEMILLA
        if n == "editar" and not catalogo[(m, p)].editable
    ]
    assert mal == []


# (c) Las columnas de cada CREATE TABLE son las del modelo.

def test_columnas_de_las_tablas_coinciden_con_los_modelos():
    tablas = {}
    for nombre, cuerpo in CREATE_TABLE.findall(_sql()):
        columnas = set()
        for linea in cuerpo.splitlines():
            palabras = linea.strip().split()
            if palabras and palabras[0].upper() not in NO_SON_COLUMNAS:
                columnas.add(palabras[0])
        tablas[nombre] = columnas
    assert set(tablas) == {"rol", "rol_permiso", "usuario_rol"}
    for nombre, columnas in tablas.items():
        del_modelo = set(Base.metadata.tables[nombre].columns.keys())
        assert columnas == del_modelo, nombre


# (d) Guardas del archivo y la trampa del aplicador.

def test_trae_collation_guarda_y_transaccion():
    sql = _sql()
    assert "SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;" in sql
    assert "SET @sembrar = ((SELECT COUNT(*) FROM rol) = 0);" in sql
    # Los tres INSERT (roles, permisos y personas) corren sólo con la guarda.
    assert sql.count("INSERT INTO") == 3
    assert sql.count("WHERE @sembrar;") == 3
    inicio, fin = sql.index("START TRANSACTION;"), sql.index("COMMIT;")
    assert inicio < sql.index("INSERT INTO") and sql.rindex("WHERE @sembrar;") < fin


def test_ninguna_linea_comentada_tiene_texto_despues_de_un_punto_y_coma():
    # El aplicador corta el archivo por `;`: lo que siga a un `;` en una línea
    # comentada quedaría sin `--` y se ejecutaría.
    malas = [
        linea for linea in _sql().splitlines()
        if linea.strip().startswith("--") and re.search(r";\s*\S", linea)
    ]
    assert malas == []


# (e) La semilla respeta las reglas `requiere` del catálogo.

def test_semilla_respeta_requiere_del_catalogo():
    catalogo = _catalogo()
    por_rol: dict[str, set] = {}
    for rol, modulo, pantalla, _ in SEMILLA:
        por_rol.setdefault(rol, set()).add((modulo, pantalla))
    faltan = [
        (rol, (modulo, pantalla), requerida)
        for rol, pantallas in por_rol.items()
        for modulo, pantalla in pantallas
        for requerida in catalogo[(modulo, pantalla)].requiere
        if (modulo, requerida) not in pantallas
    ]
    assert faltan == []
    # El caso que hoy existe: el Preliquidador tiene Revisión y también Inicio.
    assert {("preliquidacion", "revision"), ("preliquidacion", "inicio")} <= por_rol["Preliquidador"]
