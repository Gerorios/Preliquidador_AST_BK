"""buscar_personas: el buscador del padrón que usa la Administración."""
import pytest

from app.core.sueldos_service import SueldosService


@pytest.fixture()
def servicio():
    """SueldosService con el cache poblado a mano: no toca la base de sueldos."""
    s = SueldosService(db_sueldos=None)
    registros = [
        {"empresa": "LA ASTURIANA", "legajo": "4314", "apellido_nombre": "GOMEZ, JUAN",
         "cuil": "20111111119", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "PROSELECT", "legajo": "20848", "apellido_nombre": "GOMEZ, JUAN",
         "cuil": "20111111119", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "LA ASTURIANA", "legajo": "5000", "apellido_nombre": "PEREZ, ANA MARIA",
         "cuil": "27222222224", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "LA ASTURIANA", "legajo": "6001", "apellido_nombre": "NUÑEZ, JOSE",
         "cuil": "", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
    ]
    s._por_legajo = {}
    s._por_cuil = {}
    s._por_legajo_empresa = {}
    for r in registros:
        s._por_legajo.setdefault(r["legajo"], []).append(r)
        s._por_legajo_empresa[(r["legajo"], r["empresa"])] = r
        if r["cuil"]:
            s._por_cuil.setdefault(r["cuil"], []).append(r)
    s._cache_cargado = True
    return s


def test_busca_por_apellido_y_agrupa_los_empleos_de_la_persona(servicio):
    r = servicio.buscar_personas("gomez")
    assert r["total"] == 1
    persona = r["personas"][0]
    assert persona["cuil"] == "20111111119"
    assert len(persona["empleos"]) == 2
    assert {e["empresa"] for e in persona["empleos"]} == {"LA ASTURIANA", "PROSELECT"}


def test_busca_sin_tildes_ni_mayusculas(servicio):
    assert servicio.buscar_personas("nuñez")["total"] == 1
    assert servicio.buscar_personas("nunez")["total"] == 1


def test_busca_por_prefijo_de_cuil(servicio):
    r = servicio.buscar_personas("27222")
    assert [p["cuil"] for p in r["personas"]] == ["27222222224"]


def test_menos_de_tres_caracteres_no_busca(servicio):
    assert servicio.buscar_personas("go") == {"personas": [], "total": 0}


def test_persona_sin_cuil_aparece_con_cuil_none(servicio):
    persona = servicio.buscar_personas("nunez")["personas"][0]
    assert persona["cuil"] is None


def test_respeta_el_limite_y_reporta_el_total(servicio):
    r = servicio.buscar_personas("a", limite=1)  # menos de 3 → vacío
    assert r["total"] == 0
    r = servicio.buscar_personas("gomez", limite=1)
    assert len(r["personas"]) == 1
