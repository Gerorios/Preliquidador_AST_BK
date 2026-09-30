"""Configuración propia del módulo Preliquidación.

Vive en el módulo y no en `app/core/config.py` porque sólo la usa este módulo
(ADR-0013: el núcleo crece sólo cuando dos módulos necesitan lo mismo). Lee el
mismo `.env` que el núcleo; los dos declaran `extra="ignore"`, así que cada uno
toma sus variables sin rechazar las del otro.
"""
import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.identidad import normalizar_cuil

_log = logging.getLogger(__name__)


class ConfigPreliquidacion(BaseSettings):
    # CUIL de los empleados mensualizados, separados por coma, con o sin
    # guiones. Se excluyen de Verificación y del panel gerencial porque su
    # sueldo no sale de la preliquidación quincenal. Va por CUIL y no por
    # nombre: el nombre cambia de formato entre sistemas y, en un repo
    # público, es dato personal; por eso la lista está en el .env del
    # servidor y no en el código. Vacío = nadie es mensualizado.
    empleados_mensualizados_cuil: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = ConfigPreliquidacion()


@lru_cache(maxsize=8)
def _parsear(texto: str) -> frozenset[str]:
    # Cacheado por el texto crudo: el set se pide en cada consulta y en cada
    # línea serializada, y sin la caché un valor inválido repetiría el aviso
    # miles de veces por request. Si el texto cambia (monkeypatch en tests),
    # es otra clave y se vuelve a parsear.
    cuils = set()
    for entrada in texto.split(","):
        entrada = entrada.strip()
        if not entrada:
            continue
        cuil = normalizar_cuil(entrada)
        if cuil is None:
            # Un valor mal tipeado no aborta el arranque (decisión del plan,
            # pregunta 3): sólo deja de excluir a esa persona, y el aviso
            # queda en el log para corregir el .env.
            _log.warning(
                "EMPLEADOS_MENSUALIZADOS_CUIL: %r no es un CUIL de 11 dígitos; se ignora",
                entrada,
            )
            continue
        cuils.add(cuil)
    return frozenset(cuils)


def cuils_mensualizados() -> set[str]:
    """Los CUIL mensualizados, normalizados a 11 dígitos.

    Se lee `config` en cada llamada (no al importar) para que los tests puedan
    cambiar `config.empleados_mensualizados_cuil` con monkeypatch."""
    return set(_parsear(config.empleados_mensualizados_cuil))


def es_mensualizado(cuit: str | None) -> bool:
    """True si el CUIL de la línea está en la lista. Normaliza también el lado
    de la línea, así un valor con guiones o espacios igual coincide."""
    cuil = normalizar_cuil(cuit)
    return cuil is not None and cuil in _parsear(config.empleados_mensualizados_cuil)
