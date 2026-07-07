"""
Servicio de consulta a la BD de sueldos (solo lectura).
Tabla principal: nuempleados

OPTIMIZACION: en vez de hacer 1 query por cada legajo de cada linea
de la quincena (lo que con miles de lineas son miles de round-trips
a un servidor remoto), este servicio carga TODA la tabla nuempleados
una sola vez a memoria (_cargar_cache) y resuelve todo en RAM.
Con ~19.500 filas esto es liviano y la diferencia de performance
es de minutos a segundos.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import unicodedata


QUERY_TODOS_NUEMPLEADOS = text("""
    SELECT empresa, legajo, apellido_nombre, cuil, categoria,
           seccion, cargo, jornal
    FROM nuempleados
    WHERE (borrado IS NULL OR borrado <> 'S')
""")


def _normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre para comparación: mayúsculas, sin tildes, sin espacios extra."""
    nombre = (nombre or "").upper().strip()
    nombre = ''.join(
        c for c in unicodedata.normalize('NFD', nombre)
        if unicodedata.category(c) != 'Mn'
    )
    return nombre


def _similitud_nombre(nombre1: str, nombre2: str) -> float:
    """Similitud por palabras en común. Devuelve un score entre 0 y 1."""
    palabras1 = set(nombre1.split())
    palabras2 = set(nombre2.split())
    if not palabras1 or not palabras2:
        return 0.0
    comunes = palabras1 & palabras2
    return len(comunes) / max(len(palabras1), len(palabras2))


class SueldosService:

    def __init__(self, db_sueldos: Session):
        self.db = db_sueldos
        self._cache_cargado = False
        # Índices en memoria construidos una sola vez
        self._por_legajo: dict[str, list[dict]] = {}       # legajo -> [registros]
        self._por_legajo_empresa: dict[tuple, dict] = {}   # (legajo, empresa) -> registro
        self._por_cuil: dict[str, list[dict]] = {}         # cuil -> [registros]

    # ─── Carga del cache (una sola vez por instancia/quincena) ────────────────

    def _cargar_cache(self):
        if self._cache_cargado:
            return

        rows = self.db.execute(QUERY_TODOS_NUEMPLEADOS).fetchall()

        for r in rows:
            registro = {
                "empresa": str(r[0]).strip().upper(),
                "legajo": str(r[1]).strip(),
                "apellido_nombre": str(r[2] or "").strip().upper(),
                "cuil": str(r[3] or "").strip(),
                "categoria": str(r[4]).strip() if r[4] else None,
                "seccion": r[5],
                "cargo": r[6],
                "jornal": r[7],
            }
            legajo = registro["legajo"]
            empresa = registro["empresa"]
            cuil = registro["cuil"]

            self._por_legajo.setdefault(legajo, []).append(registro)
            self._por_legajo_empresa[(legajo, empresa)] = registro
            if cuil:
                self._por_cuil.setdefault(cuil, []).append(registro)

        self._cache_cargado = True

    # ─── Resolución de empresa ─────────────────────────────────────────────────

    def resolver_empresa_por_legajo(
        self,
        legajo_campo: str,
        nombre_empleado: str = "",
    ) -> tuple[str, bool]:
        """
        Determina la empresa de un empleado usando doble validación:
        legajo + nombre_empleado. Resuelto 100% en memoria (sin queries).

        - Legajo en una sola empresa → esa empresa, sin alerta
        - Legajo en varias empresas → compara nombre para desempatar
          · Si el nombre coincide con una → esa empresa, sin alerta
          · Si no hay coincidencia clara → la primera, con alerta
        - Legajo no encontrado → ASTURIANA por defecto, con alerta
        """
        self._cargar_cache()
        legajo_campo = str(legajo_campo).strip()

        registros = self._por_legajo.get(legajo_campo, [])
        if not registros:
            return "LA ASTURIANA", True

        empresas_unicas = list(dict.fromkeys(r["empresa"] for r in registros))

        if len(empresas_unicas) == 1:
            return empresas_unicas[0], False

        # Múltiples empresas — desempatar por nombre
        if nombre_empleado:
            nombre_norm = _normalizar_nombre(nombre_empleado)
            mejor_empresa = None
            mejor_score = 0

            for r in registros:
                score = _similitud_nombre(nombre_norm, r["apellido_nombre"])
                if score > mejor_score:
                    mejor_score = score
                    mejor_empresa = r["empresa"]

            if mejor_empresa and mejor_score >= 0.6:
                return mejor_empresa, False

        return empresas_unicas[0], True

    # ─── Resolución de legajo ──────────────────────────────────────────────────

    def resolver_legajo(
        self,
        legajo_campo: str,
        empresa_asignada: str,
    ) -> tuple[str, bool]:
        """
        Dado un legajo de campo y una empresa asignada, verifica si el legajo
        corresponde a esa empresa. Si no, busca el legajo correcto por CUIL.
        Resuelto 100% en memoria (sin queries).
        """
        self._cargar_cache()
        legajo_campo = str(legajo_campo).strip()
        empresa_asignada = str(empresa_asignada).strip().upper()

        # ¿El legajo ya corresponde a la empresa asignada?
        directo = self._por_legajo_empresa.get((legajo_campo, empresa_asignada))
        if directo:
            return directo["legajo"], False

        # No corresponde — buscar el CUIL del empleado por su legajo (cualquier empresa)
        registros = self._por_legajo.get(legajo_campo, [])
        if not registros:
            return legajo_campo, True  # no encontrado en sueldos

        cuil = registros[0]["cuil"]
        if not cuil:
            return legajo_campo, True

        # Buscar entre todos los legajos de ese CUIL, el de la empresa correcta
        for r in self._por_cuil.get(cuil, []):
            if r["empresa"] == empresa_asignada:
                return r["legajo"], False

        return legajo_campo, True  # no tiene legajo en esa empresa

    # ─── Legajos por persona (reasignación masiva de empresa) ─────────────────

    def legajos_por_cuil(self, cuil: str) -> list[dict]:
        """Todos los registros (empresa, legajo, apellido_nombre, ...) de una
        persona por su CUIL — los legajos que esa persona realmente tiene."""
        self._cargar_cache()
        cuil = str(cuil or "").strip()
        if not cuil:
            return []
        return list(self._por_cuil.get(cuil, []))

    def legajo_por_cuil_y_empresa(self, cuil: str, empresa: str) -> Optional[str]:
        """Legajo de una persona (por CUIL) en una empresa específica, o None
        si esa persona no tiene legajo en esa empresa."""
        empresa = str(empresa).strip().upper()
        for r in self.legajos_por_cuil(cuil):
            if r["empresa"] == empresa:
                return r["legajo"]
        return None

    # ─── Categoría (para Mantenimiento Mecánico Talleres) ─────────────────────

    def obtener_categoria(self, legajo: str) -> Optional[str]:
        self._cargar_cache()
        registros = self._por_legajo.get(str(legajo).strip(), [])
        if registros:
            return registros[0]["categoria"]
        return None

    # ─── Consultas auxiliares ──────────────────────────────────────────────────

    def obtener_empleado(self, legajo: str) -> Optional[dict]:
        self._cargar_cache()
        registros = self._por_legajo.get(str(legajo).strip(), [])
        return registros[0] if registros else None

    def listar_empleados(self) -> list[dict]:
        self._cargar_cache()
        todos = [r for registros in self._por_legajo.values() for r in registros]
        return sorted(todos, key=lambda r: r["apellido_nombre"])

    def verificar_conexion(self) -> bool:
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False