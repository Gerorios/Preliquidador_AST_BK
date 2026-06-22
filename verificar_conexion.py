"""
Script de verificación rápida — ejecutar antes de arrancar el servidor.
Uso: python verificar_conexion.py
"""
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from app.core.database import engine_externa, engine_propia, SessionExterna
from app.services.consulta_externa import ConsultaExternaService
from sqlalchemy import text


def sep(titulo):
    print(f"\n{'─'*50}\n  {titulo}\n{'─'*50}")


def main():
    errores = []

    sep("1. Conexión BD Externa")
    try:
        with engine_externa.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✓ Conexión exitosa")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        errores.append("BD externa no accesible")

    sep("2. Conexión BD Propia")
    try:
        with engine_propia.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✓ Conexión exitosa")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        errores.append("BD propia no accesible")

    sep("3. Tablas en BD Externa")
    try:
        with engine_externa.connect() as conn:
            tablas = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
            for t in tablas:
                print(f"  · {t}")
            print(f"\n  Total: {len(tablas)} tablas")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    sep("4. Query Principal (muestra 3 filas)")
    print("  NOTA: si falla, ajustar QUERY_PRINCIPAL en consulta_externa.py")
    try:
        db = SessionExterna()
        servicio = ConsultaExternaService(db)
        quincena_prueba = date(2026, 3, 1)
        filas = servicio.obtener_tareas_quincena(quincena_prueba)
        if filas:
            print(f"  ✓ {len(filas)} registros para quincena {quincena_prueba}")
            for fila in filas[:3]:
                print(f"    · {fila.get('nombre_empleado')} | "
                      f"{fila.get('nombre_tarea')} | "
                      f"{fila.get('nombre_cliente')} - {fila.get('nombre_finca')}")
        else:
            print(f"  ⚠ Sin datos para {quincena_prueba} — probar con otra fecha")
        db.close()
    except Exception as e:
        print(f"  ✗ Error: {e}")
        errores.append("Query principal falló")

    sep("Resumen")
    if not errores:
        print("  ✓ Todo OK — arrancar con:")
        print("    uvicorn app.main:app --reload")
    else:
        for e in errores:
            print(f"  ✗ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
