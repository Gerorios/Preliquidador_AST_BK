"""El script de la migración del histórico (plan de la E2, sección 3.1,
"Guarda de escritura" y "Salida del script", y par C6 de la sección 3.9).

Lo que cuidan estos tests:
- la guarda: `--aplicar` sólo escribe en `testing`, o en producción con
  `permitir_base_produccion` y `--confirmar-base` igual al nombre de la base
  (la convención del script de la E1); cualquier otra base se rechaza sin
  escribir nada ni leer los maestros;
- que sin la planilla el script diga dónde va (`fuentes/`, fuera de git) y
  salga con 1 antes de abrir ninguna base;
- que la simulación no escriba: deshace lo que `aplicar` dejó en la sesión;
- que `--informe` traiga todas las celdas de la conciliación, también las que
  cierran, y que la consola muestre sólo las que tienen diferencia.

El script se carga desde su archivo. Ningún test se conecta a una base real
ni a la consulta externa: la sesión es SQLite en memoria, los maestros son
falsos, y la base y el permiso del .env se pasan. Datos inventados.
"""
import csv
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import BASE_PRODUCCION
from app.core.database import Base
from app.modulos.facturacion.models import Comprobante
from app.modulos.facturacion.services.historico import ENCABEZADOS, Maestros

RUTA_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrar_historico_facturacion.py"
)


def _cargar_script():
    spec = importlib.util.spec_from_file_location("migrar_historico_facturacion", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def script():
    return _cargar_script()


MAESTROS = Maestros(
    clientes=[
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True},
        {"id": 2, "nombre": "CLIENTE DOS", "activo": False},
    ],
    tareas=[
        {"tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
        {"tarea_id": 11, "nombre": "TAREA B", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
    ],
    fincas=[{"id": 100, "nombre": "FINCA X", "cliente_id": 1}],
)

# FECHA A FACTURAR, CLIENTE, FINCA, TAREA, UM, CANT FACTURA, PRECIO UNIT,
# FACTURA, FACT N°, FECHA FAC (el orden de ENCABEZADOS).
FILAS = [
    ["1/9/2025", "CLIENTE UNO", "FINCA X", "TAREA A", "PLANTA", "10", "2,5", "25", "10", ""],
    ["16/9/2025", "CLIENTE UNO", "", "TAREA A", "PLANTA", "4", "2,5", "10", "10", ""],
    ["1/10/2025", "CLIENTE DOS", "", "TAREA B", "TANCADA", "1", "100", "100", "20", ""],
    # Un Cliente que no está en el maestro: se omite, y su celda cierra igual.
    ["1/10/2025", "CLIENTE TRES", "", "TAREA A", "PLANTA", "1", "5", "5", "30", ""],
]


def _planilla(ruta: Path, filas=FILAS) -> Path:
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        escritor.writerows(filas)
    return ruta


@pytest.fixture()
def fabrica():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    yield fabrica
    engine.dispose()


def _comprobantes(fabrica) -> int:
    sesion = fabrica()
    try:
        return sesion.query(Comprobante).count()
    finally:
        sesion.close()


def _sin_base():
    raise AssertionError("no tenía que abrir ninguna base")


def _correr(script, fabrica, *argumentos, base="testing", permitir=False,
            leer_maestros=lambda: MAESTROS):
    return script.main(
        [str(a) for a in argumentos],
        abrir_sesion=fabrica,
        leer_maestros=leer_maestros,
        base=base,
        permitir=permitir,
    )


# ─── La guarda ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("base, permitir, esperado", [
    ("testing", False, True),
    (BASE_PRODUCCION, True, True),
    (BASE_PRODUCCION, False, False),
    ("otra", True, False),
    ("otra", False, False),
])
def test_puede_aplicar_en_los_casos_de_la_seccion_3_1(script, base, permitir, esperado):
    assert script.puede_aplicar(base, permitir) is esperado


def test_aplicar_en_otra_base_se_rechaza_sin_escribir(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")

    salida = _correr(script, fabrica, ruta, "--aplicar", "--confirmar-base", "otra",
                     base="otra", permitir=True, leer_maestros=_sin_base)

    assert salida == 1
    assert _comprobantes(fabrica) == 0
    assert "otra" in capsys.readouterr().out


def test_aplicar_en_produccion_sin_permiso_se_rechaza(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")

    salida = _correr(script, fabrica, ruta, "--aplicar", "--confirmar-base", BASE_PRODUCCION,
                     base=BASE_PRODUCCION, leer_maestros=_sin_base)

    assert salida == 1
    assert _comprobantes(fabrica) == 0


def test_aplicar_en_produccion_sin_confirmar_base_no_escribe_y_dice_como(
        script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")

    salida = _correr(script, fabrica, ruta, "--aplicar", base=BASE_PRODUCCION,
                     permitir=True, leer_maestros=_sin_base)

    assert salida == 1
    assert _comprobantes(fabrica) == 0
    assert f"--confirmar-base {BASE_PRODUCCION}" in capsys.readouterr().out


@pytest.mark.parametrize("nombre", ["testing", BASE_PRODUCCION.upper(), f" {BASE_PRODUCCION}", ""])
def test_aplicar_en_produccion_con_otro_nombre_no_escribe(script, fabrica, tmp_path, nombre):
    ruta = _planilla(tmp_path / "planilla.csv")

    salida = _correr(script, fabrica, ruta, "--aplicar", f"--confirmar-base={nombre}",
                     base=BASE_PRODUCCION, permitir=True, leer_maestros=_sin_base)

    assert salida == 1
    assert _comprobantes(fabrica) == 0


def test_aplicar_en_produccion_con_el_nombre_de_la_base_escribe(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")

    _correr(script, fabrica, ruta, "--aplicar", "--confirmar-base", BASE_PRODUCCION,
            base=BASE_PRODUCCION, permitir=True)

    assert _comprobantes(fabrica) == 2


def test_aplicar_en_testing_no_pide_confirmar_base(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")

    _correr(script, fabrica, ruta, "--aplicar", base="testing")

    assert _comprobantes(fabrica) == 2


def test_sin_aplicar_confirmar_base_no_cambia_nada(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")

    salida = _correr(script, fabrica, ruta, "--confirmar-base", "otra",
                     base=BASE_PRODUCCION, permitir=True)

    # Simula como siempre: no escribe y sale con 1 por los nuevos.
    assert salida == 1
    assert _comprobantes(fabrica) == 0
    assert "nuevos: 2" in capsys.readouterr().out


# ─── La planilla ────────────────────────────────────────────────────────────

def test_sin_la_planilla_avisa_que_va_en_fuentes_y_sale_con_1(script, tmp_path, capsys):
    salida = script.main(
        [str(tmp_path / "no-esta.csv")],
        abrir_sesion=_sin_base, leer_maestros=_sin_base,
        base="testing", permitir=False,
    )

    assert salida == 1
    assert "fuentes/" in capsys.readouterr().out


def test_por_defecto_lee_la_planilla_de_fuentes_del_checkout(script):
    esperada = (RUTA_SCRIPT.parents[1] / "docs" / "modulos" / "facturacion" / "fuentes"
                / "planilla-facturacion.csv")
    assert script.PLANILLA == esperada


def test_una_planilla_sin_encabezados_sale_con_1_sin_abrir_la_base(script, tmp_path, capsys):
    ruta = tmp_path / "planilla.csv"
    ruta.write_text("CLIENTE,TAREA\nCLIENTE UNO,TAREA A\n", encoding="utf-8")

    salida = script.main(
        [str(ruta)], abrir_sesion=_sin_base, leer_maestros=_sin_base,
        base="testing", permitir=False,
    )

    assert salida == 1
    assert "FECHA A FACTURAR" in capsys.readouterr().out


# ─── Simular y aplicar ──────────────────────────────────────────────────────

def test_la_simulacion_no_escribe(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")
    antes = _comprobantes(fabrica)

    salida = _correr(script, fabrica, ruta)

    assert antes == 0
    assert _comprobantes(fabrica) == 0
    # Hay 2 Comprobantes nuevos para migrar: la simulación no puede salir con 0.
    assert salida == 1
    salida_consola = capsys.readouterr().out
    assert "nuevos: 2" in salida_consola
    assert "cliente_no_encontrado" in salida_consola


def test_la_simulacion_con_reemplazar_cambiados_tampoco_escribe(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")
    _correr(script, fabrica, ruta, "--aplicar")
    cambiada = [list(f) for f in FILAS]
    cambiada[0][7] = "26"
    cambiada[0][6] = "2,6"
    _planilla(ruta, cambiada)

    _correr(script, fabrica, ruta, "--reemplazar-cambiados")

    sesion = fabrica()
    try:
        importes = sorted(
            str(linea.importe)
            for c in sesion.query(Comprobante).all() for linea in c.lineas
        )
    finally:
        sesion.close()
    assert importes == ["10.00", "100.00", "25.00"]


def test_aplicar_en_testing_escribe_y_la_simulacion_siguiente_sale_con_0(
        script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")

    primera = _correr(script, fabrica, ruta, "--aplicar")
    segunda = _correr(script, fabrica, ruta)

    assert _comprobantes(fabrica) == 2
    # La corrida que aplica sale con 1 por los nuevos; la simulación siguiente,
    # sin nada pendiente ni diferencias, con 0.
    assert (primera, segunda) == (1, 0)
    assert "nuevos: 0" in capsys.readouterr().out


def test_desde_deja_afuera_lo_anterior(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")

    _correr(script, fabrica, ruta, "--aplicar", "--desde", "2025-10-01")

    # El grupo de septiembre queda omitido por anterior a la fecha de inicio.
    assert _comprobantes(fabrica) == 1
    assert "anterior_a_desde" in capsys.readouterr().out


# ─── La salida ──────────────────────────────────────────────────────────────

def _con_importe_ilegible():
    """La planilla de FILAS con la primera fila ilegible: el grupo 10 de
    CLIENTE UNO se omite, y su histórico, si ya está en la base, deja una
    diferencia en (CLIENTE UNO, 2025-09)."""
    filas = [list(f) for f in FILAS]
    filas[0][7] = "#VALUE!"
    return filas


def test_por_consola_solo_las_celdas_con_diferencia(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")
    _correr(script, fabrica, ruta, "--aplicar")
    _planilla(ruta, _con_importe_ilegible())
    capsys.readouterr()

    salida = _correr(script, fabrica, ruta)

    assert salida == 1
    consola = capsys.readouterr().out
    diferencias = consola.split("Celdas con diferencia")[1]
    assert "CLIENTE UNO" in diferencias and "2025-09" in diferencias
    assert "CLIENTE DOS" not in diferencias
    assert "CLIENTE TRES" not in diferencias


def test_la_tarea_sin_maestro_sale_en_los_avisos_y_en_los_no_resueltos(
        script, fabrica, tmp_path, capsys):
    filas = [list(f) for f in FILAS]
    filas[2][3] = "TAREA NUEVA"
    ruta = _planilla(tmp_path / "planilla.csv", filas)

    _correr(script, fabrica, ruta)

    consola = capsys.readouterr().out
    avisos = consola.split("Avisos por motivo:")[1].split("Nombres no resueltos")[0]
    assert "tarea_no_encontrada: 1" in avisos
    no_resueltos = consola.split("Nombres no resueltos")[1].split("Aplicar:")[0]
    assert "tarea_no_encontrada  TAREA NUEVA: 1" in no_resueltos
    # El Comprobante se migra igual: siguen siendo 2 nuevos.
    assert "nuevos: 2" in consola


def test_sin_diferencias_la_consola_lo_dice(script, fabrica, tmp_path, capsys):
    ruta = _planilla(tmp_path / "planilla.csv")
    _correr(script, fabrica, ruta, "--aplicar")
    capsys.readouterr()

    _correr(script, fabrica, ruta)

    assert "Diferencias: 0" in capsys.readouterr().out


def _leer_informe(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo, delimiter=";"))


def test_informe_escribe_todas_las_celdas_de_la_conciliacion(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")
    _correr(script, fabrica, ruta, "--aplicar")
    _planilla(ruta, _con_importe_ilegible())
    informe = tmp_path / "informe.csv"

    _correr(script, fabrica, ruta, "--informe", informe)

    filas = _leer_informe(informe)
    # Las tres celdas, también las dos que cierran.
    assert [(f["cliente"], f["mes"]) for f in filas] == [
        ("CLIENTE DOS", "2025-10"),
        ("CLIENTE TRES", "2025-10"),
        ("CLIENTE UNO", "2025-09"),
    ]
    uno = filas[2]
    assert (uno["planilla"], uno["omitido"], uno["omitido_importe_ilegible"],
            uno["migrable"], uno["en_base"], uno["diferencia"]) == (
        "10,00", "10,00", "10,00", "0,00", "35,00", "-35,00")
    tres = filas[1]
    assert (tres["planilla"], tres["omitido_cliente_no_encontrado"],
            tres["diferencia"]) == ("5,00", "5,00", "0,00")
    dos = filas[0]
    assert (dos["planilla"], dos["sin_numero"], dos["pendiente"], dos["migrable"],
            dos["en_base"], dos["diferencia"]) == (
        "100,00", "0,00", "0,00", "100,00", "100,00", "0,00")
    # Las columnas de un motivo que no tiene la celda van en 0.
    assert dos["omitido_cliente_no_encontrado"] == "0,00"


def test_informe_en_la_simulacion_tampoco_escribe_en_la_base(script, fabrica, tmp_path):
    ruta = _planilla(tmp_path / "planilla.csv")
    informe = tmp_path / "informe.csv"

    _correr(script, fabrica, ruta, "--informe", informe)

    assert _comprobantes(fabrica) == 0
    assert len(_leer_informe(informe)) == 3
