"""Estaciones de servicio (etapa 10): lo facturado contra lo cargado.

Lo que cuidan estos tests es que la lista de "falta cargar" sea **corta y
verdadera**. Una alerta que avisa veinte cosas de las que dieciocho son
normales se deja de leer a la semana, y ahí deja de servir para lo único que
importa: encontrar la carga que la empresa pagó y no le descontó a nadie.
"""
import io
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CargaCombustible, CargaFacturada, Estacion, Liquidacion,
)
from app.modulos.terceros.services.estaciones_service import (
    ArchivoInvalido, EstacionesService, es_flota_liviana, leer, patente_de,
    vale_de,
)

Q = date(2026, 8, 1)
SIGUIENTE = date(2026, 8, 16)

# El mapeo de una estación real: el vale mezclado con texto en `NumVehiculo`.
MAPEO = {
    "hoja": "Sheet", "fila_encabezado": 1,
    "columnas": {"fecha": "Fecha", "vale": "NumVehiculo", "litros": "CantidadDetalle",
                 "importe": "TotalDetalle", "producto": "Articulo",
                 "patente": "Patente", "chofer": "Chofer"},
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add_all([
        Liquidacion(quincena=Q),
        Estacion(id=1, nombre="Calchaqui", origen_campo="YPF OASIS ALDERETE",
                 mapeo=MAPEO),
        Estacion(id=2, nombre="La Angostura", origen_campo=None, mapeo=None),
    ])
    sesion.commit()
    yield sesion
    sesion.close()


@pytest.fixture()
def servicio(db):
    return EstacionesService(db)


def _liq(db):
    return db.query(Liquidacion).filter(Liquidacion.quincena == Q).first()


def carga(db, **campos):
    """Una carga nuestra, la del sistema de campo."""
    base = dict(tercero="ARANDA, HUGO", fecha_uso=Q, colectivo_patente="FAP480",
                vale="60023", litros=Decimal("150"))
    db.add(CargaCombustible(liquidacion_id=_liq(db).id, **{**base, **campos}))
    db.commit()


def de(cruce, *estados):
    """Las filas del cruce que quedaron en esos estados.

    El cruce devuelve una sola lista con el estado en cada fila; cada problema
    es un estado y no una lista aparte.
    """
    return [f for f in cruce["filas"] if f["estado"] in estados]


def excel(filas, hoja="Sheet") -> bytes:
    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = hoja
    cols = ["Fecha", "NumVehiculo", "CantidadDetalle", "TotalDetalle",
            "Articulo", "Patente", "Chofer"]
    ws.append(cols)
    for f in filas:
        ws.append([f.get(c) for c in cols])
    datos = io.BytesIO()
    libro.save(datos)
    return datos.getvalue()


# ─── Leer el archivo ────────────────────────────────────────────────────────

def test_el_vale_se_saca_de_adentro_del_texto():
    """El campo viene '0332 ORDEN', 'ORDEN:60314' o directamente el número."""
    assert vale_de("60277") == "60277"
    assert vale_de("0332 ORDEN") == "0332"
    assert vale_de("ORDEN:60314") == "60314"
    # La flota liviana no lleva vale: ahí va el apodo de la camioneta.
    assert vale_de("MONTANA") is None
    assert vale_de(None) is None


def test_la_patente_se_compara_sin_espacios():
    """Llega 'FRN 606' de un lado y 'FRN606' del otro, y en el mismo archivo
    aparece de las dos formas."""
    assert patente_de("FRN 606") == patente_de("FRN606") == "FRN606"
    assert patente_de("AC  733  OL") == "AC733OL"
    assert patente_de("") is None


def test_la_nafta_es_flota_liviana_y_el_diesel_no():
    assert es_flota_liviana("NAFTA SUPER") is True
    assert es_flota_liviana("V-POWER DIESEL") is True
    assert es_flota_liviana("DIESEL 500") is False


def test_una_fila_sin_fecha_sin_vale_y_sin_litros_no_es_una_carga():
    """Es el pie del reporte o una fila en blanco que el Excel arrastra."""
    datos = excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150},
        {"Articulo": "TOTAL"},
    ])
    assert len(leer(datos, "x.xlsx", MAPEO)) == 1


def test_sin_mapeo_el_archivo_no_se_puede_leer():
    with pytest.raises(ArchivoInvalido) as e:
        leer(b"", "x.xlsx", None)
    assert "mapeo" in str(e.value)


def test_si_falta_la_hoja_lo_dice_con_las_que_hay():
    datos = excel([{"Fecha": Q}], hoja="Otra")
    with pytest.raises(ArchivoInvalido) as e:
        leer(datos, "x.xlsx", MAPEO)
    assert "Otra" in str(e.value)


# ─── Subir ──────────────────────────────────────────────────────────────────

def test_cada_linea_va_a_la_quincena_de_su_fecha(db, servicio):
    """Un reporte que arranca el 1 y termina el 19 cae en las dos."""
    datos = excel([
        {"Fecha": date(2026, 8, 3), "NumVehiculo": "60023", "CantidadDetalle": 150},
        {"Fecha": date(2026, 8, 19), "NumVehiculo": "60099", "CantidadDetalle": 100},
    ])
    r = servicio.subir(1, Q, datos, "calchaqui.xlsx")

    assert r["lineas"] == 2
    assert r["quincenas"] == ["2026-08-01", "2026-08-16"]
    assert len(servicio.lineas_de(1, Q)) == 1
    assert len(servicio.lineas_de(1, SIGUIENTE)) == 1


def test_subir_dos_veces_reemplaza_y_no_acumula(db, servicio):
    """Pasa cuando alguien no está seguro de haberlo subido. Sumarlo dos veces
    duplicaría todo lo facturado sin que se note."""
    datos = excel([{"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150}])
    servicio.subir(1, Q, datos, "calchaqui.xlsx")
    r = servicio.subir(1, Q, datos, "calchaqui.xlsx")

    assert r["reemplazadas"] == 1
    assert len(servicio.lineas_de(1, Q)) == 1


def test_no_se_puede_subir_a_una_estacion_sin_mapeo(db, servicio):
    """La Angostura manda los remitos por foto: sus cargas se tipean."""
    with pytest.raises(ArchivoInvalido) as e:
        servicio.subir(2, Q, excel([{"Fecha": Q}]), "foto.xlsx")
    assert "mapeo" in str(e.value)


# ─── El cruce ───────────────────────────────────────────────────────────────

def test_lo_que_cruza_por_vale(db, servicio):
    carga(db, vale="60023", litros=Decimal("150"))
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "FAP480"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480"})
    assert c["por_vale"] == 1 and de(c, "sin_cargar") == []


def test_lo_que_cruza_por_fecha_patente_y_litros(db, servicio):
    """Una estación escribe sólo los últimos cuatro dígitos del vale: donde el
    sistema de campo tiene 60457, el archivo dice '0457 ORDEN'. Truncar el
    número sería adivinar; esto es exacto."""
    carga(db, vale="60457", colectivo_patente="HBR189", litros=Decimal("200"))
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "0457 ORDEN", "CantidadDetalle": 200,
         "Articulo": "DIESEL 500", "Patente": "HBR 189"}]), "x.xlsx")

    c = servicio.cruce(Q, {"HBR189"})
    assert c["por_vale"] == 0
    assert c["por_huella"] == 1
    assert de(c, "sin_cargar") == []


def test_lo_facturado_sobre_un_colectivo_y_no_cargado_se_avisa(db, servicio):
    """Es plata que la empresa pagó y no le descontó a nadie."""
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60999", "CantidadDetalle": 160,
         "Articulo": "DIESEL 500", "Patente": "HLH811"}]), "x.xlsx")

    c = servicio.cruce(Q, {"HLH811"})
    faltan = de(c, "sin_cargar")
    assert len(faltan) == 1
    assert faltan[0]["facturada"].vale == "60999"


def test_lo_que_no_salio_a_un_colectivo_no_es_una_alerta(db, servicio):
    """La cisterna, los bidones, las camionetas y la maquinaria no se cargan
    como flete y no le corresponden a ningún tercero."""
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60998", "CantidadDetalle": 400,
         "Articulo": "DIESEL 500", "Patente": "CISTERNA"},
        {"Fecha": Q, "NumVehiculo": "60997", "CantidadDetalle": 50,
         "Articulo": "NAFTA SUPER", "Patente": "KGH823"},
    ]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480"})
    assert de(c, "sin_cargar") == []
    assert len(de(c, "sin_asignar")) == 2


def test_sin_el_maestro_de_patentes_se_avisa_de_todo(db, servicio):
    """Si el sistema de campo no contesta se cruza igual: es mejor una lista
    con cosas de más que no mostrar nada."""
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60998", "CantidadDetalle": 400,
         "Articulo": "DIESEL 500", "Patente": "CISTERNA"}]), "x.xlsx")

    assert len(de(servicio.cruce(Q, None), "sin_cargar")) == 1


def test_cuando_los_litros_no_coinciden_se_avisa(db, servicio):
    """El vale cruza pero la cantidad no: se le está descontando al tercero
    algo distinto de lo que la estación cobró."""
    carga(db, vale="60023", litros=Decimal("150"))
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 200,
         "Articulo": "DIESEL 500", "Patente": "FAP480"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480"})
    distintas = de(c, "litros_distintos")
    assert len(distintas) == 1
    assert distintas[0]["facturada"].litros == Decimal("200.00")
    assert distintas[0]["carga"].litros == Decimal("150.00")


def test_medio_litro_de_diferencia_no_se_avisa(db, servicio):
    """Las estaciones redondean distinto: 200 y 200,0021 son la misma carga."""
    carga(db, vale="60023", litros=Decimal("200"))
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 200.0021,
         "Articulo": "DIESEL 500", "Patente": "FAP480"}]), "x.xlsx")

    assert de(servicio.cruce(Q, {"FAP480"}), "litros_distintos") == []


# ─── Lo que se tipea ────────────────────────────────────────────────────────

def test_las_cargas_a_mano_se_suman_y_no_reemplazan(db, servicio):
    """Se tipean de a poco, a medida que llegan las fotos. Borrar lo anterior
    en cada carga sería perder lo que alguien acaba de escribir."""
    servicio.agregar_a_mano(2, [{"fecha": Q, "vale": "1234", "litros": 100}])
    servicio.agregar_a_mano(2, [{"fecha": Q, "vale": "1235", "litros": 80}])

    assert len(servicio.lineas_de(2, Q)) == 2


def test_una_carga_a_mano_necesita_su_fecha(db, servicio):
    """Es lo que decide en qué quincena entra."""
    with pytest.raises(ArchivoInvalido) as e:
        servicio.agregar_a_mano(2, [{"vale": "1234", "litros": 100}])
    assert "fecha" in str(e.value)


def test_una_linea_tipeada_mal_se_puede_borrar(db, servicio):
    servicio.agregar_a_mano(2, [{"fecha": Q, "vale": "1234", "litros": 100}])
    fila = servicio.lineas_de(2, Q)[0]

    servicio.borrar_linea(fila.id)
    assert servicio.lineas_de(2, Q) == []


def test_se_puede_definir_con_que_nombre_cruza_una_estacion(db, servicio):
    """Sin esto no hay nada que cruzar, y no se puede adivinar."""
    assert db.query(Estacion).filter(Estacion.id == 2).first().origen_campo is None
    servicio.definir_origen(2, "  LA ANGOSTURA  ")
    assert db.query(Estacion).filter(Estacion.id == 2).first().origen_campo == "LA ANGOSTURA"


# ─── Lo que la grilla usa para marcar ───────────────────────────────────────

def test_los_vales_facturados_salen_por_numero(db, servicio):
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150},
        {"Fecha": Q, "NumVehiculo": "MONTANA", "CantidadDetalle": 50},
    ]), "x.xlsx")

    vales = servicio.vales_facturados(Q)
    assert set(vales) == {"60023"}      # el que no tiene número no entra


def test_una_quincena_sin_archivos_no_tiene_nada_facturado(servicio):
    assert servicio.vales_facturados(Q) == {}
    assert servicio.cruce(Q, set())["facturadas"] == 0


# ─── Cuando la estación no manda el vale ────────────────────────────────────
#
# Shell Famaillá, que es la más grande, deja `NumVehiculo` vacío en todas sus
# líneas. Sus cargas se encuentran por patente y litros, y ahí la fecha no
# coincide: la estación fecha el remito y el sistema de campo fecha la carga.

def test_un_dia_de_diferencia_no_impide_el_cruce(db, servicio):
    """En agosto, 21 de 23 cargas de Shell que parecían no estar tenían su par
    un día antes, con la misma patente y los mismos litros."""
    carga(db, vale="60630", colectivo_patente="GCQ346",
          fecha_uso=date(2026, 8, 2), litros=Decimal("200"))
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 3), "NumVehiculo": None, "CantidadDetalle": 200,
         "Articulo": "EVOLUX DIESEL", "Patente": "GCQ346"}]), "shell.xlsx")

    c = servicio.cruce(Q, {"GCQ346"})
    assert c["por_huella"] == 1
    assert de(c, "sin_cargar") == []


def test_una_semana_de_diferencia_si_lo_impide(db, servicio):
    """La tolerancia es de días, no de semanas: dos cargas iguales separadas
    por una semana son dos cargas, no una fechada mal."""
    carga(db, colectivo_patente="GCQ346", fecha_uso=Q, litros=Decimal("200"))
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 9), "NumVehiculo": None, "CantidadDetalle": 200,
         "Articulo": "EVOLUX DIESEL", "Patente": "GCQ346"}]), "shell.xlsx")

    assert len(de(servicio.cruce(Q, {"GCQ346"}), "sin_cargar")) == 1


def test_una_carga_nuestra_no_puede_cruzar_con_dos_facturadas(db, servicio):
    """Si no, dos líneas facturadas iguales cruzarían las dos contra la misma y
    una de las dos estaría facturada de más sin que se vea."""
    carga(db, colectivo_patente="FJT630", fecha_uso=Q, litros=Decimal("200"))
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 200,
         "Articulo": "DIESEL 500", "Patente": "FJT630"},
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 200,
         "Articulo": "DIESEL 500", "Patente": "FJT630"},
    ]), "shell.xlsx")

    c = servicio.cruce(Q, {"FJT630"})
    assert c["cruzan"] == 1
    assert len(de(c, "sin_cargar")) == 1


def test_se_elige_la_carga_del_dia_mas_cercano(db, servicio):
    """Emparejarlas al revés daría el mismo total pero dejaría dos fechas
    cruzadas, y la próxima vez que alguien mire una línea no va a entender."""
    carga(db, vale="LEJOS", colectivo_patente="GKX720",
          fecha_uso=date(2026, 8, 5), litros=Decimal("120"))
    carga(db, vale="CERCA", colectivo_patente="GKX720",
          fecha_uso=date(2026, 8, 7), litros=Decimal("120"))
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 7), "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "DIESEL 500", "Patente": "GKX720"}]), "shell.xlsx")

    # La del 7 es la que se consume; la del 5 queda libre.
    c = servicio.cruce(Q, {"GKX720"})
    assert c["por_huella"] == 1 and de(c, "sin_cargar") == []


# ─── El otro lado: lo que está cargado y la estación no facturó ─────────────

def test_lo_cargado_que_la_estacion_no_facturo_se_avisa(db, servicio):
    """El espejo de `sin_cargar`, y no significa lo mismo: acá el tercero tiene
    un descuento que la empresa nunca pagó."""
    carga(db, vale="60023", origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60777", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999"})
    assert [f["carga"].vale for f in de(c, "sin_estacion")] == ["60023"]


def test_sin_archivo_de_esa_estacion_no_se_reclama_nada(db, servicio):
    """Si la estación todavía no subió su archivo, lo que falta es el archivo
    y no la carga. Reclamarlas sería llenar la pantalla de falsos."""
    carga(db, vale="60023", origen="LA ANGOSTURA")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60777", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999"})
    assert de(c, "sin_estacion") == []


def test_lo_que_cruza_no_aparece_del_otro_lado(db, servicio):
    carga(db, vale="60023", origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "FAP480"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480"})
    assert de(c, "sin_estacion", "sin_cargar") == []


# ─── Cada fila sabe de qué estación es ─────────────────────────────────────

def test_cada_fila_trae_su_estacion(db, servicio):
    """Es con lo que la pantalla filtra: mirar una estación es quedarse con sus
    filas, no volver a cruzar."""
    carga(db, vale="60023", origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60023", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "FAP480"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480"})
    assert [f["estacion_id"] for f in c["filas"]] == [1]


def test_lo_que_la_estacion_no_facturo_tambien_es_de_esa_estacion(db, servicio):
    """Esa fila no tiene lado de la estación, y sin el id no habría forma de
    saber a cuál reclamarle."""
    carga(db, vale="60023", origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60777", "CantidadDetalle": 99,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999"})
    fila = de(c, "sin_estacion")[0]
    assert fila["facturada"] is None and fila["estacion_id"] == 1


def test_las_filas_de_dos_estaciones_no_se_mezclan(db, servicio):
    db.add(Estacion(id=3, nombre="Garsa", origen_campo="GAR S.A.", mapeo=MAPEO))
    db.commit()
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60111", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "AAA111"}]), "x.xlsx")
    servicio.subir(3, Q, excel([
        {"Fecha": Q, "NumVehiculo": "60222", "CantidadDetalle": 150,
         "Articulo": "DIESEL 500", "Patente": "BBB222"}]), "y.xlsx")

    filas = servicio.cruce(Q, None)["filas"]
    vales = {f["estacion_id"]: f["facturada"].vale for f in filas}
    assert vales == {1: "60111", 3: "60222"}


# ─── La patente tipeada mal ────────────────────────────────────────────────
# La estación la escribe a mano y se equivoca en un carácter. Esa línea cae en
# «sin asignar» y su par real queda en «sin facturar»: un solo error de tipeo
# infla las dos listas a la vez.

def test_una_patente_a_un_caracter_cruza(db, servicio):
    """IKI028 donde el colectivo es ILI028, con los mismos litros y el mismo
    día. Es el caso real de agosto."""
    carga(db, vale="59986", colectivo_patente="ILI028", fecha_uso=Q,
          litros=Decimal("120"), origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "EVOLUX DIESEL", "Patente": "IKI028"}]), "shell.xlsx")

    c = servicio.cruce(Q, {"ILI028"})
    assert c["por_parecida"] == 1
    assert de(c, "sin_asignar", "sin_estacion") == []


def test_si_la_patente_es_de_un_colectivo_no_se_busca_parecida(db, servicio):
    """LFL019 y LFL029 son dos colectivos distintos del mismo tercero. Si la
    que trae el archivo existe, no está tipeada mal, y buscarle una parecida
    sería inventarle un dueño."""
    carga(db, colectivo_patente="LFL029", fecha_uso=Q, litros=Decimal("120"),
          origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "EVOLUX DIESEL", "Patente": "LFL019"}]), "shell.xlsx")

    c = servicio.cruce(Q, {"LFL019", "LFL029"})
    assert c["por_parecida"] == 0
    assert len(de(c, "sin_cargar")) == 1


def test_con_dos_candidatas_parecidas_no_elige_ninguna(db, servicio):
    """Adivinar cuál de dos es peor que dejar el aviso: el aviso se mira, la
    adivinada no."""
    carga(db, vale="A", colectivo_patente="ILI028", fecha_uso=Q,
          litros=Decimal("120"), origen="YPF OASIS ALDERETE")
    carga(db, vale="B", colectivo_patente="IKI029", fecha_uso=Q,
          litros=Decimal("120"), origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "EVOLUX DIESEL", "Patente": "IKI028"}]), "shell.xlsx")

    c = servicio.cruce(Q, {"ILI028", "IKI029"})
    assert c["por_parecida"] == 0
    assert len(de(c, "sin_asignar")) == 1


def test_una_patente_parecida_con_otros_litros_no_cruza(db, servicio):
    """La patente parecida sola no afirma nada: sin los mismos litros son dos
    cargas distintas."""
    carga(db, colectivo_patente="ILI028", fecha_uso=Q, litros=Decimal("200"),
          origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "EVOLUX DIESEL", "Patente": "IKI028"}]), "shell.xlsx")

    assert servicio.cruce(Q, {"ILI028"})["por_parecida"] == 0


def test_dos_patentes_de_largo_distinto_no_son_un_tipeo(db, servicio):
    """Agregar o sacar un carácter cambia el largo, y las patentes no varían
    de largo."""
    carga(db, colectivo_patente="ILI0288", fecha_uso=Q, litros=Decimal("120"),
          origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": Q, "NumVehiculo": None, "CantidadDetalle": 120,
         "Articulo": "EVOLUX DIESEL", "Patente": "ILI028"}]), "shell.xlsx")

    assert servicio.cruce(Q, {"ILI0288"})["por_parecida"] == 0


# ─── Lo que el archivo no cubre ────────────────────────────────────────────

def test_lo_cargado_en_un_dia_que_el_archivo_no_trae_no_se_reclama(db, servicio):
    """Un reporte puede traer dos días de la quincena. Lo de los otros trece no
    es que la estación no lo facturó: es que no lo mandó."""
    carga(db, vale="60658", fecha_uso=date(2026, 8, 12), origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 2), "NumVehiculo": "60111", "CantidadDetalle": 99,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999"})
    assert de(c, "sin_estacion") == []
    assert [f["carga"].vale for f in de(c, "fuera_del_archivo")] == ["60658"]


def test_dentro_de_los_dias_del_archivo_si_se_reclama(db, servicio):
    carga(db, vale="60658", fecha_uso=date(2026, 8, 2), origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 1), "NumVehiculo": "60111", "CantidadDetalle": 99,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"},
        {"Fecha": date(2026, 8, 5), "NumVehiculo": "60112", "CantidadDetalle": 99,
         "Articulo": "DIESEL 500", "Patente": "ZZZ998"},
    ]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999", "ZZZ998"})
    assert [f["carga"].vale for f in de(c, "sin_estacion")] == ["60658"]
    assert de(c, "fuera_del_archivo") == []


def test_una_carga_sin_fecha_no_se_da_por_fuera_del_archivo(db, servicio):
    """Sin fecha no se puede decidir, y la duda no se cuenta como error."""
    carga(db, vale="60658", fecha_uso=None, origen="YPF OASIS ALDERETE")
    servicio.subir(1, Q, excel([
        {"Fecha": date(2026, 8, 2), "NumVehiculo": "60111", "CantidadDetalle": 99,
         "Articulo": "DIESEL 500", "Patente": "ZZZ999"}]), "x.xlsx")

    c = servicio.cruce(Q, {"FAP480", "ZZZ999"})
    assert [f["carga"].vale for f in de(c, "sin_estacion")] == ["60658"]

