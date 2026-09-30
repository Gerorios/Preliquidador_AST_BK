"""Limitador de intentos de login: 5 fallos en 15 minutos por identificador
bloquean 15 minutos; un login correcto resetea.

Parte 1 (unidad): la clase sola, con un reloj manual inyectado para no
depender del tiempo real ni dormir en los tests.
"""
import pytest

from app.core.limite_login import LimitadorIntentos

QUINCE_MIN = 900


@pytest.fixture
def reloj():
    # Lista mutable: el test avanza el tiempo con reloj[0] += segundos.
    return [1000.0]


@pytest.fixture
def lim(reloj):
    return LimitadorIntentos(
        reloj=lambda: reloj[0], maximo=5, ventana_seg=QUINCE_MIN, bloqueo_seg=QUINCE_MIN
    )


def _fallar(lim, clave, veces):
    for _ in range(veces):
        lim.registrar_fallo(clave)


def test_cuatro_fallos_no_bloquean(lim):
    _fallar(lim, "x", 4)
    assert lim.bloqueado_hasta("x") is None
    assert lim.segundos_restantes("x") is None


def test_quinto_fallo_bloquea_quince_minutos(lim, reloj):
    _fallar(lim, "x", 5)
    assert lim.bloqueado_hasta("x") == reloj[0] + QUINCE_MIN
    assert lim.segundos_restantes("x") == QUINCE_MIN


def test_sigue_bloqueado_hasta_que_vence(lim, reloj):
    _fallar(lim, "x", 5)
    reloj[0] += 899
    assert lim.bloqueado_hasta("x") is not None
    assert lim.segundos_restantes("x") == 1


def test_al_vencer_el_bloqueo_el_contador_arranca_de_cero(lim, reloj):
    _fallar(lim, "x", 5)
    reloj[0] += 901
    assert lim.bloqueado_hasta("x") is None
    # Contador en cero: hacen falta otros 5 fallos para volver a bloquear.
    _fallar(lim, "x", 4)
    assert lim.bloqueado_hasta("x") is None
    lim.registrar_fallo("x")
    assert lim.bloqueado_hasta("x") is not None


def test_segundos_restantes_redondea_hacia_arriba(lim, reloj):
    # El endpoint lo usa para Retry-After (entero): nunca decir "0" estando
    # bloqueado.
    _fallar(lim, "x", 5)
    reloj[0] += 899.5
    assert lim.segundos_restantes("x") == 1


def test_exito_resetea_el_contador(lim):
    _fallar(lim, "x", 3)
    lim.exito("x")
    _fallar(lim, "x", 4)
    assert lim.bloqueado_hasta("x") is None


def test_fallos_espaciados_mas_que_la_ventana_no_se_acumulan(lim, reloj):
    for _ in range(10):
        lim.registrar_fallo("x")
        reloj[0] += QUINCE_MIN + 1
    assert lim.bloqueado_hasta("x") is None


def test_la_ventana_cuenta_desde_el_primer_fallo(lim, reloj):
    # 4 fallos al principio de la ventana; el 5° llega cuando ya venció:
    # arranca una ventana nueva y no bloquea.
    _fallar(lim, "x", 4)
    reloj[0] += QUINCE_MIN + 1
    lim.registrar_fallo("x")
    assert lim.bloqueado_hasta("x") is None


def test_claves_distintas_no_se_pisan(lim):
    _fallar(lim, "a", 5)
    _fallar(lim, "b", 4)
    assert lim.bloqueado_hasta("a") is not None
    assert lim.bloqueado_hasta("b") is None
    lim.exito("b")
    assert lim.bloqueado_hasta("a") is not None


def test_limpiar_vacia_todo(lim):
    _fallar(lim, "a", 5)
    _fallar(lim, "b", 2)
    lim.limpiar()
    assert lim.bloqueado_hasta("a") is None
    assert lim._intentos == {}


def test_registrar_fallo_poda_entradas_vencidas(lim, reloj):
    _fallar(lim, "vieja", 2)
    _fallar(lim, "bloqueada", 5)
    reloj[0] += QUINCE_MIN + 1
    _fallar(lim, "otra-bloqueada", 5)
    reloj[0] += 10
    lim.registrar_fallo("nueva")
    # "vieja" venció su ventana y "bloqueada" su bloqueo: se podan. La que
    # sigue bloqueada no.
    assert set(lim._intentos) == {"otra-bloqueada", "nueva"}


def test_instancia_de_modulo_con_la_regla_acordada():
    from app.core.limite_login import limitador_login

    assert limitador_login.maximo == 5
    assert limitador_login.ventana_seg == QUINCE_MIN
    assert limitador_login.bloqueo_seg == QUINCE_MIN


# ─── Parte 2: el limitador en POST /api/auth/login ───────────────────────────
#
# Endpoint real con SQLite en memoria (mismo patrón que test_login_cuil.py) y
# el reloj de la instancia de módulo reemplazado por uno manual. El conftest
# limpia el limitador antes de cada test.

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import auth
from app.core.auth import pwd_context
from app.core.database import Base, get_db_propia
from app.core.identidad import email_de_cuil
from app.core.limite_login import limitador_login
from app.core.models import Usuario
from app.main import app

CUIL = "20111111119"
MAIL = "liq@asturiana.com"
DETAIL_15 = "Demasiados intentos. Probá de nuevo en 15 minutos."


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Usuario(nombre="GOMEZ, JUAN", email=email_de_cuil(CUIL),
                password=pwd_context.hash(CUIL), rol="usuario", activo=True),
        Usuario(nombre="Liq", email=MAIL,
                password=pwd_context.hash("secreta"), rol="admin", activo=True),
    ])
    s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear()
    s.close()


@pytest.fixture()
def reloj_login(monkeypatch):
    t = [5000.0]
    monkeypatch.setattr(limitador_login, "reloj", lambda: t[0])
    return t


@pytest.fixture()
def cliente(db, reloj_login):
    return TestClient(app)


def _login(cliente, usuario, password):
    return cliente.post("/api/auth/login", data={"username": usuario, "password": password})


def _fallar_login(cliente, usuario, veces):
    for i in range(veces):
        r = _login(cliente, usuario, "mala")
        assert r.status_code == 401, f"intento {i + 1}: {r.status_code} {r.text}"


def test_quinto_fallo_bloquea_aunque_despues_la_password_sea_correcta(cliente):
    _fallar_login(cliente, CUIL, 5)
    r = _login(cliente, CUIL, CUIL)
    assert r.status_code == 429
    assert r.json()["detail"] == DETAIL_15
    assert r.headers["Retry-After"] == "900"


def test_los_minutos_se_redondean_hacia_arriba(cliente, reloj_login):
    _fallar_login(cliente, CUIL, 5)
    reloj_login[0] += 13 * 60 + 30  # quedan 90 s
    r = _login(cliente, CUIL, CUIL)
    assert r.status_code == 429
    assert r.json()["detail"] == "Demasiados intentos. Probá de nuevo en 2 minutos."
    assert r.headers["Retry-After"] == "90"


def test_cumplidos_los_quince_minutos_entra(cliente, reloj_login):
    _fallar_login(cliente, CUIL, 5)
    reloj_login[0] += 15 * 60
    r = _login(cliente, CUIL, CUIL)
    assert r.status_code == 200, r.text


def test_cuil_con_y_sin_guiones_y_email_sintetico_son_el_mismo_balde(cliente):
    _fallar_login(cliente, "20-11111111-9", 2)
    _fallar_login(cliente, "20111111119", 2)
    _fallar_login(cliente, email_de_cuil(CUIL), 1)
    for tipeado in (CUIL, "20-11111111-9", email_de_cuil(CUIL)):
        r = _login(cliente, tipeado, CUIL)
        assert r.status_code == 429, tipeado
        assert r.json()["detail"] == DETAIL_15


def test_mail_con_mayusculas_y_espacios_es_el_mismo_balde(cliente):
    _fallar_login(cliente, MAIL, 3)
    _fallar_login(cliente, "LIQ@asturiana.com ", 2)
    r = _login(cliente, MAIL, "secreta")
    assert r.status_code == 429
    assert r.json()["detail"] == DETAIL_15


def test_login_correcto_resetea_el_contador(cliente):
    _fallar_login(cliente, CUIL, 4)
    assert _login(cliente, CUIL, CUIL).status_code == 200
    # Contador en cero: se toleran otros 5 fallos (los cinco dan 401, no 429)...
    _fallar_login(cliente, CUIL, 5)
    # ...y recién ahí bloquea.
    r = _login(cliente, CUIL, CUIL)
    assert r.status_code == 429


def test_usuario_inexistente_tambien_se_limita(cliente):
    # Mismo comportamiento que un usuario real: no se filtra si existe o no.
    _fallar_login(cliente, "nadie@asturiana.com", 5)
    r = _login(cliente, "nadie@asturiana.com", "mala")
    assert r.status_code == 429
    assert r.json()["detail"] == DETAIL_15
    assert r.headers["Retry-After"] == "900"


def test_bloqueado_no_consulta_la_base_ni_paga_el_bcrypt(cliente, monkeypatch):
    _fallar_login(cliente, CUIL, 5)
    llamadas = []
    monkeypatch.setattr(
        auth, "_usuario_por_identificador",
        lambda *a, **k: llamadas.append("base") or None,
    )
    monkeypatch.setattr(
        auth, "verificar_password",
        lambda *a, **k: llamadas.append("bcrypt") or False,
    )
    r = _login(cliente, CUIL, CUIL)
    assert r.status_code == 429
    assert llamadas == []


def test_otro_identificador_no_queda_bloqueado(cliente):
    _fallar_login(cliente, CUIL, 5)
    assert _login(cliente, MAIL, "secreta").status_code == 200
