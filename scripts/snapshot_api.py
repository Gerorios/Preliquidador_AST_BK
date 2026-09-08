"""
Captura un snapshot de respuestas de la API local para comparar antes y
después de un refactor. Solo endpoints GET, solo lectura. Uso:

    # con el backend corriendo en :8000 contra la base de desarrollo (testing)
    python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_antes.json
    ... (cambiar de rama, reiniciar el backend) ...
    python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_despues.json
    python scripts/snapshot_api.py --comparar C:/Temp/claude/etapa0/api_antes.json C:/Temp/claude/etapa0/api_despues.json

Credenciales: variables SNAPSHOT_EMAIL y SNAPSHOT_PASSWORD (un usuario admin
de la base de desarrollo). Nunca apuntar a producción.
"""
import hashlib
import json
import os
import sys

import httpx

BASE = os.environ.get("SNAPSHOT_BASE", "http://localhost:8000")


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _login(c: httpx.Client) -> str:
    r = c.post(f"{BASE}/api/auth/login", data={
        "username": os.environ["SNAPSHOT_EMAIL"], "password": os.environ["SNAPSHOT_PASSWORD"],
    })
    r.raise_for_status()
    return r.json()["access_token"]


def _rutas(c: httpx.Client) -> list[str]:
    """Rutas GET fijas del módulo, parametrizadas con la primera preliquidación
    y la primera quincena con conceptos que haya en la base."""
    preliqs = c.get(f"{BASE}/api/preliquidacion/").json()
    pid = preliqs[0]["id"] if preliqs else None
    quincenas = c.get(f"{BASE}/api/precios/conceptos/quincenas").json()
    q = quincenas[0] if quincenas else None
    q = q["quincena"] if isinstance(q, dict) else q
    rutas = [
        "/health",
        "/api/auth/me",
        "/api/preliquidacion/",
        "/api/preliquidacion/empresas",
        "/api/precios/maestro/clientes",
        "/api/precios/maestro/tareas",
        "/api/precios/grupos-pago",
        "/api/precios/conceptos/quincenas",
        "/api/gerencial/indicadores",
        "/api/gerencial/evolucion",
    ]
    if pid:
        rutas += [
            f"/api/preliquidacion/{pid}/estadisticas",
            f"/api/preliquidacion/{pid}/lineas",
            f"/api/preliquidacion/{pid}/dashboard-verificacion",
            f"/api/preliquidacion/{pid}/control-plantas-jornal",
            f"/api/preliquidacion/{pid}/control-tancadas-jornal",
            f"/api/preliquidacion/{pid}/operarios-mantenimiento",
        ]
    if q:
        rutas += [
            f"/api/precios/conceptos?quincena={q}",
            f"/api/precios/conceptos/panel?quincena={q}",
            f"/api/precios/conceptos/faltantes?quincena={q}",
            f"/api/precios/conceptos/solapamientos?quincena={q}",
            f"/api/precios/conceptos/supervisores?quincena={q}",
        ]
    return rutas


def capturar(destino: str):
    with httpx.Client(timeout=300) as c:
        c.headers["Authorization"] = f"Bearer {_login(c)}"
        out = {}
        for ruta in _rutas(c):
            r = c.get(f"{BASE}{ruta}")
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = r.text
            out[ruta] = {"status": r.status_code, "hash": _hash(cuerpo)}
            print(f"  {r.status_code} {ruta} {out[ruta]['hash']}")
        json.dump(out, open(destino, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"\n{len(out)} rutas guardadas en {destino}")


def comparar(a: str, b: str) -> int:
    sa, sb = json.load(open(a, encoding="utf-8")), json.load(open(b, encoding="utf-8"))
    dif = 0
    for ruta in sorted(set(sa) | set(sb)):
        if sa.get(ruta) != sb.get(ruta):
            dif += 1
            print(f"DIF {ruta}: {sa.get(ruta)} -> {sb.get(ruta)}")
    print("IDENTICO" if dif == 0 else f"{dif} diferencias")
    return 1 if dif else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--comparar":
        sys.exit(comparar(sys.argv[2], sys.argv[3]))
    if len(sys.argv) == 2:
        capturar(sys.argv[1])
    else:
        sys.exit(__doc__)
