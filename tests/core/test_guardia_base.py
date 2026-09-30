"""Guardia de base: la app se niega a arrancar contra la base de producción
salvo que el .env lo permita explícitamente (PERMITIR_BASE_PRODUCCION=1, que
sólo tiene el VPS). Evita que un `uvicorn --reload` local escriba sobre el dato
real de la empresa. Ver "Bases de datos" en AGENTS.md."""
import asyncio

import pytest

import app.main as main
from app.core.config import BASE_PRODUCCION, guardia_base_propia


@pytest.mark.parametrize("nombre", ["testing", "otra_base"])
def test_una_base_que_no_es_produccion_arranca(nombre):
    assert guardia_base_propia(nombre, permitir=False) is None


@pytest.mark.parametrize("nombre", ["preliquidacion", " preliquidacion", "PRELIQUIDACION "])
def test_produccion_sin_permiso_se_frena(nombre):
    mensaje = guardia_base_propia(nombre, permitir=False)
    assert mensaje and "PERMITIR_BASE_PRODUCCION" in mensaje


def test_produccion_con_permiso_arranca():
    assert guardia_base_propia(BASE_PRODUCCION, permitir=True) is None


def _correr_lifespan():
    async def correr():
        async with main.lifespan(main.app):
            pass
    asyncio.run(correr())


@pytest.fixture
def sin_bases(monkeypatch):
    """El lifespan sin conexiones reales: las tres dan error, nada se inspecciona."""
    monkeypatch.setattr(
        main, "verificar_conexiones",
        lambda: {"sueldos": False, "externa": False, "propia": False, "errores": []},
    )


def test_el_lifespan_no_arranca_contra_produccion_sin_permiso(monkeypatch, sin_bases):
    monkeypatch.setattr(main.settings, "db_propia_name", BASE_PRODUCCION)
    monkeypatch.setattr(main.settings, "permitir_base_produccion", False)
    with pytest.raises(SystemExit):
        _correr_lifespan()


def test_el_lifespan_arranca_contra_produccion_con_permiso(monkeypatch, sin_bases):
    monkeypatch.setattr(main.settings, "db_propia_name", BASE_PRODUCCION)
    monkeypatch.setattr(main.settings, "permitir_base_produccion", True)
    _correr_lifespan()


def test_el_lifespan_arranca_contra_testing(monkeypatch, sin_bases, capsys):
    monkeypatch.setattr(main.settings, "db_propia_name", "testing")
    monkeypatch.setattr(main.settings, "permitir_base_produccion", False)
    _correr_lifespan()
    assert "(testing)" in capsys.readouterr().out
