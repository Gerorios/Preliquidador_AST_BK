"""Las Alertas de cruce entre los tres sistemas de origen (etapa 3).

Todo lo de acá es lógica pura sobre listas de diccionarios: no hay base ni red.
Los datos de las fixtures están calcados de casos reales medidos el 2026-09-14,
porque son los que explican por qué cada regla es como es.
"""
import pytest

from app.modulos.terceros.services import alertas_cruce as ac


def compras(id_maquina, nombre):
    return {"id_maquina": id_maquina, "nombre": nombre, "codigo": "", "propiedad": "TERCEROS"}


def taller(id_maquina, nombre):
    return {"id_maquina": id_maquina, "nombre": nombre, "tipo": "", "propiedad": "TERCEROS"}


def colectivo(id, nombre, patente="ABC123", patente_desc=None, propiedad="TERCEROS"):
    return {
        "id": id, "nombre": nombre, "patente": patente,
        "patente_descripcion": patente if patente_desc is None else patente_desc,
        "propiedad": propiedad, "descripcion": "",
    }


def detectar(maquinarias_campo=(), colectivos=(), mc=(), mt=(), lineas=None):
    return ac.detectar(list(maquinarias_campo), list(colectivos), list(mc), list(mt), lineas or {})


def de_tipo(alertas, tipo):
    return [a for a in alertas if a.tipo == tipo]


# ─── Normalización ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("COMEDOR CITRUSVIL N°1", "comedor citrusvil n1"),
    ("TRACTOR DEUTZ N° 113 SOSA ALBERTO", "TRACTOR DEUTZ N113 SOSA ALBERTO"),
    ("MAQUINARIA  RAFAEL  OJEDA ", "MAQUINARIA RAFAEL OJEDA"),
    ("MUÑOZ", "MUNOZ"),
])
def test_dos_escrituras_de_lo_mismo_normalizan_igual(a, b):
    assert ac.normalizar_nombre(a) == ac.normalizar_nombre(b)


@pytest.mark.parametrize("texto,esperado", [
    ("CAMIONETA IVH 219 TOYOTA", {"IVH219"}),
    ("CAMIONETA TOYOTA HILUX IVH219", {"IVH219"}),
    ("TERCEROS;CAMIONETA;TOYOTA;HILUX;AB942JZ", {"AB942JZ"}),
    ("MANITOU MANITOU N°0046 BARRIOS", set()),
    ("", set()),
])
def test_la_patente_se_lee_con_o_sin_espacios_y_en_los_dos_formatos(texto, esperado):
    assert ac.patentes_en(texto) == esperado


# ─── Ids duplicados: la alerta más grave ────────────────────────────────────

def test_la_misma_maquina_con_dos_ids_se_detecta():
    """Caso real: FUMIGADORA 400 LTS CITRUSVIL 570, id 981 en compras y 990 en
    el taller. El id es el puente, así que duplicado significa que repuestos y
    horas no se juntan nunca."""
    a = de_tipo(detectar(
        mc=[compras(981, "FUMIGADORA 400 LTS CITRUSVIL 570")],
        mt=[taller(990, "FUMIGADORA 400 LTS CITRUSVIL 570")],
        lineas={981: 24},
    ), "id_duplicado")
    assert len(a) == 1
    assert a[0].severidad == ac.ALTA
    assert "24" in a[0].impacto
    assert set(a[0].referencias) == {"compras:981", "taller:990"}


def test_un_duplicado_sin_movimiento_baja_de_severidad():
    a = de_tipo(detectar(
        mc=[compras(981, "FUMIGADORA")], mt=[taller(990, "FUMIGADORA")], lineas={},
    ), "id_duplicado")
    assert a[0].severidad == ac.MEDIA


def test_el_mismo_id_en_los_dos_no_es_duplicado():
    assert detectar(mc=[compras(735, "MANITOU")], mt=[taller(735, "MANITOU")]) == []


def test_un_duplicado_no_se_cuenta_ademas_como_sin_par():
    """Una máquina duplicada también parece "sin par" —el cruce por id falla
    justo por eso—, y contarla dos veces infla la lista con el mismo problema."""
    alertas = detectar(
        mc=[compras(981, "FUMIGADORA")], mt=[taller(990, "FUMIGADORA")], lineas={981: 24},
    )
    assert len(de_tipo(alertas, "id_duplicado")) == 1
    assert de_tipo(alertas, "sin_par_en_taller") == []
    assert de_tipo(alertas, "sin_par_en_compras") == []


# ─── Sin par ────────────────────────────────────────────────────────────────

def test_una_maquina_de_compras_sin_par_y_con_repuestos_se_alerta():
    a = de_tipo(detectar(mc=[compras(961, "COMEDOR")], lineas={961: 1}), "sin_par_en_taller")
    assert len(a) == 1
    assert a[0].severidad == ac.ALTA
    assert a[0].sistema == ac.TALLER      # se corrige en el taller, no en compras


def test_una_maquina_de_compras_sin_movimiento_no_se_alerta():
    """De las 11 sin par medidas en 2026, 9 no tenían un solo repuesto:
    listarlas entierra las 2 que importan."""
    assert de_tipo(detectar(mc=[compras(76, "COLECTIVO VNR 500")], lineas={}), "sin_par_en_taller") == []


def test_una_maquina_del_taller_sin_par_se_alerta_siempre():
    """Acá el faltante es al revés: alguien carga horas sobre una máquina que
    compras no conoce, y eso siempre hay que mirarlo."""
    a = de_tipo(detectar(mt=[taller(982, "CINCEL SAN MIGUEL")]), "sin_par_en_compras")
    assert len(a) == 1
    assert a[0].sistema == ac.COMPRAS


def test_la_alerta_sugiere_la_ficha_parecida_del_otro_sistema():
    """Caso real: 'COMEDOR CITRSVIL N° 1' en el taller y 'COMEDOR CITRUSVIL N°1'
    en compras. Sin la pista, la alerta es un misterio; con ella, es una tarea."""
    a = de_tipo(detectar(
        mc=[compras(961, "COMEDOR CITRUSVIL N°1")],
        mt=[taller(968, "COMEDOR CITRSVIL N° 1")],
        lineas={961: 1},
    ), "sin_par_en_taller")
    assert "COMEDOR CITRSVIL N° 1" in a[0].detalle
    assert "968" in a[0].detalle


def test_dos_maquinas_distintas_no_se_sugieren_entre_si():
    a = de_tipo(detectar(
        mc=[compras(961, "TRACTOR DEUTZ SOSA")],
        mt=[taller(968, "CAMIONETA TOYOTA HILUX")],
        lineas={961: 1},
    ), "sin_par_en_taller")
    assert "parecido" not in a[0].detalle


# ─── Colectivos ─────────────────────────────────────────────────────────────

def test_dos_patentes_distintas_en_el_mismo_colectivo():
    """Caso real: DEMARCO, OSCAR con KPH682 en la columna y HFU440 en la
    descripción — y HFU440 es de otro dueño."""
    a = de_tipo(detectar(colectivos=[
        colectivo(216, "DEMARCO, OSCAR", "KPH682", "HFU440")
    ]), "patente_inconsistente")
    assert len(a) == 1
    assert "KPH682" in a[0].detalle and "HFU440" in a[0].detalle
    assert a[0].sistema == ac.CAMPO


def test_la_patente_se_compara_sin_espacios():
    assert detectar(colectivos=[colectivo(1, "X", " FAP364", "FAP364")]) == []


def test_una_propiedad_mal_escrita_se_alerta():
    """Caso real: un colectivo con propiedad 'ERCEROS'. Con ese valor no entra
    ni en la lista de terceros ni en la de propios."""
    a = de_tipo(detectar(colectivos=[
        colectivo(259, "VIDELA, GASTON", propiedad="ERCEROS")
    ]), "propiedad_invalida")
    assert len(a) == 1 and "ERCEROS" in a[0].detalle


def test_una_propiedad_vacia_se_alerta():
    a = de_tipo(detectar(colectivos=[colectivo(273, "TRANSPORTE ALFONSO", propiedad="")]),
                "propiedad_invalida")
    assert len(a) == 1 and "vacío" in a[0].detalle


def test_los_placeholders_sin_colectivo_no_son_alertas():
    """'SIN COLECTIVO CITROMAX' no es un colectivo: es la opción "ninguno" del
    sistema de campo, y la consulta de viajes ya la deja afuera."""
    alertas = detectar(colectivos=[
        colectivo(10, "SIN COLECTIVO", propiedad=""),
        colectivo(11, "SIN COLECTIVO CITROMAX", propiedad=""),
    ])
    assert alertas == []


def test_dos_dueños_que_difieren_en_una_letra_se_marcan_para_revisar():
    """Caso real: SALOMOM, FELIPE y SALOMON, FELIPE, cada uno con su colectivo."""
    a = de_tipo(detectar(colectivos=[
        colectivo(1, "SALOMOM, FELIPE", "HFU440"),
        colectivo(126, "SALOMON, FELIPE", "GUO852"),
    ]), "dueno_casi_duplicado")
    assert len(a) == 1
    assert a[0].severidad == ac.BAJA     # puede ser legítimo: se mira, no se corrige
    assert "puede ser" in a[0].detalle.lower()


def test_dos_dueños_bien_distintos_no_se_marcan():
    assert de_tipo(detectar(colectivos=[
        colectivo(1, "SALOMOM, FELIPE"), colectivo(2, "DEMARCO, OSCAR"),
    ]), "dueno_casi_duplicado") == []


# ─── Orden ──────────────────────────────────────────────────────────────────

def test_las_urgentes_van_primero():
    alertas = detectar(
        colectivos=[colectivo(1, "SALOMOM, FELIPE"), colectivo(2, "SALOMON, FELIPE")],
        mc=[compras(981, "FUMIGADORA")], mt=[taller(990, "FUMIGADORA")], lineas={981: 24},
    )
    assert [a.severidad for a in alertas] == sorted(
        [a.severidad for a in alertas], key=lambda s: {ac.ALTA: 0, ac.MEDIA: 1, ac.BAJA: 2}[s]
    )
    assert alertas[0].severidad == ac.ALTA


# ─── El resumen estructural ─────────────────────────────────────────────────

def test_el_resumen_separa_las_que_no_tienen_patente_de_las_que_no_cruzan():
    """44 de 46 no cruzan, pero por dos motivos distintos: la mayoría ni
    siquiera tiene patente. Es una sola tarea —cambiar el origen—, no 44."""
    r = ac.resumen_maquinaria_campo(
        [
            {"nombre": "CAMIONETA TOYOTA HILUX IVH219", "descripcion": "TERCEROS;;;;IVH219"},
            {"nombre": "CAMIONETA TOYOTA ODI023", "descripcion": "TERCEROS;;;;ODI023"},
            {"nombre": "MANITOU MANITOU N°0046 BARRIOS", "descripcion": "TERCEROS;IMPLEMENTO;;;"},
            {"nombre": "AUTO FIAT UNO DKD027", "descripcion": "TERCEROS;;;;DKD027"},
        ],
        [{"nombre": "CAMIONETA IVH 219 TOYOTA RUBEN MUÑOZ"}],
        [{"nombre": "CAMIONETA ODI 023 TOYOTA ELIO QUIROGA"}],
    )
    assert r == {"total": 4, "cruzan": 2, "sin_patente": 1, "con_patente_sin_par": 1}


def test_sin_maquinaria_el_resumen_no_se_rompe():
    assert ac.resumen_maquinaria_campo([], [], []) == {
        "total": 0, "cruzan": 0, "sin_patente": 0, "con_patente_sin_par": 0,
    }


def test_el_impacto_se_escribe_en_singular_cuando_es_una_sola():
    """Lo lee una persona en pantalla: «1 líneas» canta."""
    a = de_tipo(detectar(mc=[compras(961, "COMEDOR")], lineas={961: 1}), "sin_par_en_taller")
    assert a[0].impacto.startswith("1 línea de")
    b = de_tipo(detectar(mc=[compras(961, "COMEDOR")], lineas={961: 3}), "sin_par_en_taller")
    assert b[0].impacto.startswith("3 líneas de")
