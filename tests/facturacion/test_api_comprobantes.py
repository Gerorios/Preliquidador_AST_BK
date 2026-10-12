"""Los endpoints de Comprobantes y de las lecturas del campo (plan de la E2,
sección 3.2; paso A6).

Las reglas ya están probadas en test_comprobantes_service y las consultas en
test_consulta_externa_comprobantes. Acá se prueba lo que agrega la capa HTTP:
quién entra a qué, los códigos y el `detail` de cada error del contrato, y
cómo sale el cuerpo (los decimales como texto). El servicio y la consulta se
reemplazan por dobles, así que no hay ni base ni red.
"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base, ExternaNoDisponible
from app.main import app
from app.modulos.facturacion.api import comprobantes as api
from app.modulos.facturacion.services.comprobantes_service import (
    ComprobanteInvalido, ComprobanteModificado, ComprobanteNoEncontrado,
    ComprobanteRepetido, ComprobantesService, FacturaConNotas,
    HistoricoMismoNumero, HistoricoNoEditable, LineaInvalida,
)

F = "/api/facturacion"

FILA = {
    "id": 5, "tipo": "factura", "numero": "0001-00000123",
    "fecha": date(2026, 10, 5), "mes": "2026-09", "cliente_id": 12,
    "cliente_nombre": "CLIENTE UNO", "empresa_emisora": "EMPRESA A",
    "es_historico": False, "pendiente_de_facturar": False,
    "cantidad_lineas": 1, "cantidad_adjuntos": 0,
    "total_neto": Decimal("121133.34"),
}
DETALLE = {
    **FILA,
    "factura_corregida": None,
    "notas_credito": [{"id": 9, "numero": "0001-00000200", "fecha": date(2026, 10, 9)}],
    "lineas": [{
        "id": 31, "orden": 1, "fecha": date(2026, 9, 16), "tarea_id": 7,
        "tarea_nombre": "TAREA A", "unidad": "plantas", "finca_id": None,
        "finca_nombre": None, "cantidad": Decimal("1234.50"),
        "precio_unitario": Decimal("98.1234"), "importe": Decimal("121133.34"),
    }],
    "adjuntos": [],
    "creado_en": datetime(2026, 10, 5, 12, 0, 0),
    "actualizado_en": None,
}
ENTRADA = {
    "tipo": "factura", "cliente_id": 12, "empresa_emisora": "empresa a",
    "numero": "0001-00000123", "fecha": "2026-10-05",
    "factura_corregida_id": None, "actualizado_en": None,
    "lineas": [{"fecha": "2026-09-16", "tarea_id": 7, "unidad": "plantas",
                "finca_id": None, "cantidad": "1234.50",
                "precio_unitario": "98.1234"}],
}


class ServicioFalso:
    """El ComprobantesService con lo justo: guarda lo que recibe y, si se le
    da un error, lo levanta en cualquier operación."""

    def __init__(self, error=None):
        self.error = error
        self.creados = []
        self.editados = []
        self.borrados = []

    def _quizas_falla(self):
        if self.error is not None:
            raise self.error

    def listar(self):
        self._quizas_falla()
        return [FILA]

    def detalle(self, comprobante_id):
        self._quizas_falla()
        return {**DETALLE, "id": comprobante_id}

    def crear(self, entrada, usuario_id=None):
        self._quizas_falla()
        self.creados.append((entrada, usuario_id))
        return SimpleNamespace(id=5)

    def editar(self, comprobante_id, entrada, usuario_id=None):
        self._quizas_falla()
        self.editados.append((comprobante_id, entrada, usuario_id))
        return SimpleNamespace(id=comprobante_id)

    def borrar(self, comprobante_id):
        self._quizas_falla()
        self.borrados.append(comprobante_id)


class ConsultaFalsa:
    def __init__(self, error=None):
        self.error = error
        self.fincas_pedidas = []
        self.clientes_pedidos = []

    def _quizas_falla(self):
        if self.error is not None:
            raise self.error

    def clientes(self, incluir_baja=False):
        self._quizas_falla()
        self.clientes_pedidos.append(incluir_baja)
        return [{"id": 12, "nombre": "CLIENTE UNO", "activo": True}]

    def fincas_de_cliente(self, cliente_id):
        self._quizas_falla()
        self.fincas_pedidas.append(cliente_id)
        return [{"id": 3, "nombre": "FINCA NORTE"}]

    def empresas(self):
        self._quizas_falla()
        return ["EMPRESA A", "EMPRESA B"]

    def obtener_tareas(self, incluir_baja=False):
        self._quizas_falla()
        assert incluir_baja is False
        return [
            {"tarea_id": 7, "nombre": "TAREA A", "grupo_tarea": "PODA",
             "unidad_sugerida": "plantas", "no_facturable": False},
            {"tarea_id": 8, "nombre": "TAREA B", "grupo_tarea": None,
             "unidad_sugerida": None, "no_facturable": True},
        ]


def _persona(*permisos, rol="usuario"):
    """Una persona con un rol armado a mano: Facturación no está en la
    semilla de roles (tests/roles_de_prueba.py)."""
    return SimpleNamespace(
        id=42, nombre="Test", email="t@t.com", rol=rol, activo=True,
        roles=[SimpleNamespace(nombre="Rol de prueba", permisos=[
            SimpleNamespace(modulo=m, pantalla=p, nivel=n) for m, p, n in permisos
        ])],
    )


CONTADORA = _persona(("facturacion", "comprobantes", "editar"))
LECTORA = _persona(("facturacion", "comprobantes", "ver"))
# Edita otra pantalla del módulo, pero no Comprobantes.
OTRA_PANTALLA = _persona(("facturacion", "equivalencias", "editar"),
                         ("facturacion", "pendientes", "editar"))
DE_OTRO_MODULO = _persona(("preliquidacion", "revision", "editar"))


@pytest.fixture(autouse=True)
def _limpiar():
    yield
    app.dependency_overrides.clear()


def _cliente(persona=CONTADORA, servicio=None, consulta=None):
    if persona is not None:
        app.dependency_overrides[get_usuario_actual] = lambda: persona
    servicio = servicio or ServicioFalso()
    consulta = consulta or ConsultaFalsa()
    app.dependency_overrides[api.get_comprobantes] = lambda: servicio
    app.dependency_overrides[api.get_consulta_externa] = lambda: consulta
    return TestClient(app)


# ─── Lo que devuelve ────────────────────────────────────────────────────────

def test_el_alta_responde_201_con_el_detalle():
    servicio = ServicioFalso()
    r = _cliente(servicio=servicio).post(f"{F}/comprobantes", json=ENTRADA)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id"] == 5
    assert cuerpo["numero"] == "0001-00000123"
    # Los decimales salen como texto, igual que en Terceros.
    assert cuerpo["total_neto"] == "121133.34"
    assert cuerpo["lineas"][0]["cantidad"] == "1234.50"
    assert cuerpo["lineas"][0]["precio_unitario"] == "98.1234"
    assert cuerpo["lineas"][0]["importe"] == "121133.34"
    assert cuerpo["notas_credito"] == [{"id": 9, "numero": "0001-00000200",
                                        "fecha": "2026-10-09"}]
    assert cuerpo["factura_corregida"] is None
    assert cuerpo["actualizado_en"] is None
    # Llega la entrada ya leída, con los decimales exactos y quién la cargó.
    entrada, usuario_id = servicio.creados[0]
    assert entrada.lineas[0].cantidad == Decimal("1234.50")
    assert entrada.lineas[0].precio_unitario == Decimal("98.1234")
    assert usuario_id == 42


def test_el_listado_trae_las_filas():
    r = _cliente().get(f"{F}/comprobantes")
    assert r.status_code == 200
    fila = r.json()[0]
    assert set(fila) == set(FILA)
    assert fila["mes"] == "2026-09"
    assert fila["total_neto"] == "121133.34"
    assert fila["fecha"] == "2026-10-05"


def test_el_detalle_trae_lineas_notas_y_adjuntos():
    r = _cliente().get(f"{F}/comprobantes/5")
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == set(DETALLE)
    assert cuerpo["creado_en"] == "2026-10-05T12:00:00"


def test_la_edicion_responde_200_con_el_detalle_y_sella_quien():
    servicio = ServicioFalso()
    entrada = {**ENTRADA, "actualizado_en": "2026-10-06T09:30:00"}
    r = _cliente(servicio=servicio).put(f"{F}/comprobantes/5", json=entrada)
    assert r.status_code == 200
    assert r.json()["id"] == 5
    comprobante_id, recibida, usuario_id = servicio.editados[0]
    assert comprobante_id == 5
    # El `actualizado_en` llega tal cual, sin zona: el servicio lo compara
    # con el de la base (pregunta 18).
    assert recibida.actualizado_en == datetime(2026, 10, 6, 9, 30, 0)
    assert usuario_id == 42


def test_el_borrado_responde_204_sin_cuerpo():
    servicio = ServicioFalso()
    r = _cliente(servicio=servicio).delete(f"{F}/comprobantes/5")
    assert r.status_code == 204
    assert r.content == b""
    assert servicio.borrados == [5]


def test_los_clientes_son_id_y_nombre_y_solo_activos():
    consulta = ConsultaFalsa()
    r = _cliente(consulta=consulta).get(f"{F}/clientes")
    assert r.status_code == 200
    assert r.json() == [{"id": 12, "nombre": "CLIENTE UNO"}]
    assert consulta.clientes_pedidos == [False]


def test_las_fincas_son_las_del_cliente_pedido():
    consulta = ConsultaFalsa()
    r = _cliente(consulta=consulta).get(f"{F}/clientes/12/fincas")
    assert r.status_code == 200
    assert r.json() == [{"id": 3, "nombre": "FINCA NORTE"}]
    assert consulta.fincas_pedidas == [12]


def test_las_empresas_son_una_lista_de_textos():
    r = _cliente().get(f"{F}/empresas")
    assert r.status_code == 200
    assert r.json() == ["EMPRESA A", "EMPRESA B"]


def test_las_tareas_traen_la_unidad_sugerida_y_no_facturable():
    r = _cliente().get(f"{F}/tareas")
    assert r.status_code == 200
    assert r.json() == [
        {"tarea_id": 7, "nombre": "TAREA A", "grupo_tarea": "PODA",
         "unidad_sugerida": "plantas", "no_facturable": False},
        {"tarea_id": 8, "nombre": "TAREA B", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": True},
    ]


def test_si_el_campo_no_responde_es_503():
    """Lo traduce app/main.py; acá sólo se mira que la excepción llegue."""
    consulta = ConsultaFalsa(error=ExternaNoDisponible("El sistema de campo no respondió."))
    r = _cliente(consulta=consulta).get(f"{F}/clientes")
    assert r.status_code == 503
    assert r.json()["detail"] == "El sistema de campo no respondió."


# ─── Los errores del contrato ───────────────────────────────────────────────

ERRORES_409 = [
    (ComprobanteRepetido(77),
     {"tipo": "comprobante_repetido", "comprobante_id": 77}),
    (HistoricoMismoNumero(78),
     {"tipo": "historico_mismo_numero", "comprobante_id": 78}),
    (HistoricoNoEditable(), {"tipo": "historico_no_editable"}),
    (FacturaConNotas(), {"tipo": "factura_con_notas"}),
    (ComprobanteModificado(), {"tipo": "comprobante_modificado"}),
]


@pytest.mark.parametrize("error, esperado", ERRORES_409,
                         ids=[e["tipo"] for _, e in ERRORES_409])
@pytest.mark.parametrize("metodo, ruta", [
    ("post", "/comprobantes"), ("put", "/comprobantes/5"),
])
def test_cada_409_sale_con_su_detail(error, esperado, metodo, ruta):
    c = _cliente(servicio=ServicioFalso(error=error))
    r = getattr(c, metodo)(f"{F}{ruta}", json=ENTRADA)
    assert r.status_code == 409
    assert r.json()["detail"] == {**esperado, "mensaje": error.mensaje}


@pytest.mark.parametrize("error, tipo", [
    (HistoricoNoEditable(), "historico_no_editable"),
    (FacturaConNotas(), "factura_con_notas"),
], ids=["historico_no_editable", "factura_con_notas"])
def test_el_borrado_rechazado_es_409(error, tipo):
    r = _cliente(servicio=ServicioFalso(error=error)).delete(f"{F}/comprobantes/5")
    assert r.status_code == 409
    assert r.json()["detail"] == {"tipo": tipo, "mensaje": error.mensaje}


def test_un_comprobante_invalido_es_422_con_el_campo():
    error = ComprobanteInvalido("numero", "Falta el número.")
    r = _cliente(servicio=ServicioFalso(error=error)).post(f"{F}/comprobantes", json=ENTRADA)
    assert r.status_code == 422
    assert r.json()["detail"] == {"tipo": "comprobante_invalido",
                                  "mensaje": "Falta el número.", "campo": "numero"}


def test_una_linea_invalida_es_422_con_la_fila_y_el_campo():
    error = LineaInvalida(2, "tarea_id", "Esa tarea no existe o está dada de baja.")
    r = _cliente(servicio=ServicioFalso(error=error)).put(f"{F}/comprobantes/5", json=ENTRADA)
    assert r.status_code == 422
    assert r.json()["detail"] == {
        "tipo": "linea_invalida", "mensaje": "Esa tarea no existe o está dada de baja.",
        "fila": 2, "campo": "tarea_id",
    }


@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("get", "/comprobantes/99", None),
    ("put", "/comprobantes/99", ENTRADA),
    ("delete", "/comprobantes/99", None),
])
def test_un_comprobante_que_no_existe_es_404_con_texto(metodo, ruta, cuerpo):
    c = _cliente(servicio=ServicioFalso(error=ComprobanteNoEncontrado()))
    kwargs = {"json": cuerpo} if cuerpo is not None else {}
    r = c.request(metodo.upper(), f"{F}{ruta}", **kwargs)
    assert r.status_code == 404
    assert r.json()["detail"] == ComprobanteNoEncontrado.mensaje


def test_una_entrada_mal_formada_es_la_lista_de_fastapi():
    r = _cliente().post(f"{F}/comprobantes", json={**ENTRADA, "cliente_id": "doce"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


# ─── Quién entra ────────────────────────────────────────────────────────────

LECTURAS = ["/comprobantes", "/comprobantes/5", "/clientes", "/clientes/12/fincas",
            "/empresas", "/tareas"]
ESCRITURAS = [("POST", "/comprobantes", ENTRADA), ("PUT", "/comprobantes/5", ENTRADA),
              ("DELETE", "/comprobantes/5", None)]


def _escribir(c, metodo, ruta, cuerpo):
    kwargs = {"json": cuerpo} if cuerpo is not None else {}
    return c.request(metodo, f"{F}{ruta}", **kwargs)


@pytest.mark.parametrize("ruta", LECTURAS)
def test_quien_solo_ve_lee_todo(ruta):
    assert _cliente(LECTORA).get(f"{F}{ruta}").status_code == 200


@pytest.mark.parametrize("metodo, ruta, cuerpo", ESCRITURAS)
def test_quien_solo_ve_no_escribe(metodo, ruta, cuerpo):
    servicio = ServicioFalso()
    r = _escribir(_cliente(LECTORA, servicio=servicio), metodo, ruta, cuerpo)
    assert r.status_code == 403
    assert not (servicio.creados or servicio.editados or servicio.borrados)


@pytest.mark.parametrize("persona", [OTRA_PANTALLA, DE_OTRO_MODULO],
                         ids=["otra_pantalla_del_modulo", "otro_modulo"])
@pytest.mark.parametrize("metodo, ruta, cuerpo",
                         [("GET", r, None) for r in LECTURAS] + ESCRITURAS)
def test_sin_la_pantalla_no_entra(persona, metodo, ruta, cuerpo):
    servicio = ServicioFalso()
    r = _escribir(_cliente(persona, servicio=servicio), metodo, ruta, cuerpo)
    assert r.status_code == 403
    assert not (servicio.creados or servicio.editados or servicio.borrados)


def test_el_admin_entra_sin_roles():
    admin = SimpleNamespace(id=1, nombre="A", email="a@t.com", rol="admin",
                            activo=True, roles=[])
    assert _cliente(admin).post(f"{F}/comprobantes", json=ENTRADA).status_code == 201


@pytest.mark.parametrize("metodo, ruta, cuerpo",
                         [("GET", r, None) for r in LECTURAS] + ESCRITURAS)
def test_sin_sesion_es_401(metodo, ruta, cuerpo):
    servicio = ServicioFalso()
    r = _escribir(_cliente(persona=None, servicio=servicio), metodo, ruta, cuerpo)
    assert r.status_code == 401
    assert not (servicio.creados or servicio.editados or servicio.borrados)


# ─── Con el servicio de verdad ──────────────────────────────────────────────

@pytest.fixture()
def db():
    # StaticPool y sin chequeo de hilo: TestClient corre el endpoint en otro
    # hilo y la base en memoria tiene que ser la misma conexión.
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    yield sesion
    sesion.close()
    engine.dispose()


def test_de_punta_a_punta_los_schemas_aceptan_lo_que_devuelve_el_servicio(db):
    """Los dobles de arriba copian el contrato; acá se mira que lo que arma el
    servicio real pase por los schemas de salida, y que el `actualizado_en`
    que devuelve el detalle sirva tal cual para el PUT siguiente."""
    servicio = ComprobantesService(db, ConsultaFalsa())
    c = _cliente(servicio=servicio)

    r = c.post(f"{F}/comprobantes", json=ENTRADA)
    assert r.status_code == 201, r.text
    creado = r.json()
    assert creado["empresa_emisora"] == "EMPRESA A"
    assert creado["lineas"][0]["tarea_nombre"] == "TAREA A"
    assert creado["lineas"][0]["importe"] == "121133.34"
    assert creado["total_neto"] == "121133.34"
    assert creado["mes"] == "2026-09"
    assert creado["actualizado_en"] is None

    ruta = f"{F}/comprobantes/{creado['id']}"
    r = c.put(ruta, json={**ENTRADA, "numero": "0001-00000124"})
    assert r.status_code == 200, r.text
    editado = r.json()
    assert editado["numero"] == "0001-00000124"
    assert editado["actualizado_en"] is not None

    # Con el sello que devolvió el PUT, pasa; con el viejo (null), es el 409.
    r = c.put(ruta, json={**ENTRADA, "actualizado_en": editado["actualizado_en"]})
    assert r.status_code == 200, r.text
    r = c.put(ruta, json={**ENTRADA, "actualizado_en": None})
    assert r.status_code == 409
    assert r.json()["detail"]["tipo"] == "comprobante_modificado"

    filas = c.get(f"{F}/comprobantes").json()
    assert [f["id"] for f in filas] == [creado["id"]]
    assert c.get(ruta).json()["numero"] == "0001-00000123"

    assert c.delete(ruta).status_code == 204
    assert c.get(ruta).status_code == 404
