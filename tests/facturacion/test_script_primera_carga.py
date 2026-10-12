"""El script scripts/importar_unidades_del_maestro.py (plan de la E1, D7).

Con el patrón de tests/core/test_scripts_usuarios.py: se prueba `main(argv)`
contra una SQLite en memoria puesta en lugar de `SessionPropia`, con la
lectura del campo y el nombre de la base reemplazados. No hay red ni base real.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modulos.facturacion.models import TareaFacturacion
from scripts import importar_unidades_del_maestro as script

CAMPO = [
    {"tarea_id": 1, "nombre": "TAREA UNO", "grupo_tarea": None},
    {"tarea_id": 2, "nombre": "TAREA DOS", "grupo_tarea": None},
]


@pytest.fixture()
def csv(tmp_path):
    ruta = tmp_path / "maestro.csv"
    ruta.write_text(
        "nombre_tarea;grupo_tarea;grupo_factura\r\n"
        "Tarea Uno;Grupo A;HORAS PEON\r\n"
        "Tarea Dos;Grupo A;NO FACTURABLE\r\n",
        encoding="utf-8-sig",
    )
    return str(ruta)


@pytest.fixture()
def fabrica(monkeypatch):
    """sessionmaker sobre una SQLite en memoria en lugar de `SessionPropia`,
    el campo como lista y la base en `testing`."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(script, "SessionPropia", Session)
    monkeypatch.setattr(script, "tareas_del_campo", lambda: [dict(t) for t in CAMPO])
    monkeypatch.setattr(script.settings, "db_propia_name", "testing")
    monkeypatch.setattr(script.settings, "permitir_base_produccion", False)
    return Session


def _filas(Session):
    s = Session()
    try:
        return {f.tarea_id: (f.unidad_sugerida, f.no_facturable) for f in s.query(TareaFacturacion)}
    finally:
        s.close()


def test_sin_aplicar_no_escribe(fabrica, csv, capsys):
    assert script.main(["--csv", csv]) == 0
    assert _filas(fabrica) == {}
    salida = capsys.readouterr().out
    assert "simulación" in salida.lower()
    assert "2" in salida


def test_con_aplicar_escribe(fabrica, csv):
    assert script.main(["--csv", csv, "--aplicar"]) == 0
    assert _filas(fabrica) == {1: ("horas_peon", False), 2: (None, True)}


def test_un_archivo_que_no_existe_sale_con_1_y_dice_donde_vive(fabrica, tmp_path, capsys):
    codigo = script.main(["--csv", str(tmp_path / "no-esta.csv"), "--aplicar"])
    assert codigo == 1
    assert "docs/modulos/facturacion/fuentes/" in capsys.readouterr().out
    assert _filas(fabrica) == {}


def test_un_encabezado_distinto_sale_con_1_sin_escribir(fabrica, tmp_path, capsys):
    ruta = tmp_path / "otro.csv"
    ruta.write_text("tarea;unidad\r\nTarea Uno;HORAS PEON\r\n", encoding="utf-8")
    assert script.main(["--csv", str(ruta), "--aplicar"]) == 1
    assert "nombre_tarea;grupo_tarea;grupo_factura" in capsys.readouterr().out
    assert _filas(fabrica) == {}


@pytest.mark.parametrize("extra", [[], ["--confirmar-base", "testing"]])
def test_aplicar_en_otra_base_sin_confirmarla_no_escribe(fabrica, csv, monkeypatch, extra):
    monkeypatch.setattr(script.settings, "db_propia_name", "otra_base")
    codigo = script.main(["--csv", csv, "--aplicar", *extra])
    assert codigo != 0
    assert _filas(fabrica) == {}


def test_aplicar_en_otra_base_confirmandola_escribe(fabrica, csv, monkeypatch):
    monkeypatch.setattr(script.settings, "db_propia_name", "otra_base")
    assert script.main(["--csv", csv, "--aplicar", "--confirmar-base", "otra_base"]) == 0
    assert _filas(fabrica) == {1: ("horas_peon", False), 2: (None, True)}


def test_si_la_guardia_frena_no_conecta(fabrica, csv, monkeypatch, capsys):
    def no_conectar(*a, **k):
        raise AssertionError("conectó a una base")

    monkeypatch.setattr(script, "SessionPropia", no_conectar)
    monkeypatch.setattr(script, "tareas_del_campo", no_conectar)
    monkeypatch.setattr(script.settings, "db_propia_name", "preliquidacion")
    monkeypatch.setattr(script.settings, "permitir_base_produccion", False)

    codigo = script.main(["--csv", csv, "--aplicar", "--confirmar-base", "preliquidacion"])

    assert codigo != 0
    assert "PERMITIR_BASE_PRODUCCION" in capsys.readouterr().out


def test_el_csv_es_obligatorio():
    with pytest.raises(SystemExit) as exc:
        script.construir_parser().parse_args([])
    assert exc.value.code != 0
