"""Configuración propia del módulo Facturación.

Vive en el módulo y no en `app/core/config.py` porque sólo la usa este módulo
(ADR-0013), como la de Preliquidación. Lee el mismo `.env` que el núcleo; los
dos declaran `extra="ignore"`, así que cada uno toma sus variables sin
rechazar las del otro.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

# Lo que acepta un Comprobante (plan de la E2, pregunta 12). El front repite
# los dos controles para avisar antes de subir (FB1).
TAMANO_MAXIMO = 10 * 1024 * 1024
MAXIMO_POR_COMPROBANTE = 5


class ConfigFacturacion(BaseSettings):
    # Carpeta de los adjuntos (ADR-0019): una ruta absoluta del servidor,
    # fuera del código, porque el deploy reemplaza la carpeta del código
    # entera. Vacío = los adjuntos responden 503 en vez de frenar el arranque:
    # el resto de la app anda sin ellos.
    facturacion_adjuntos_dir: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = ConfigFacturacion()
