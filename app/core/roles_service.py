"""Roles armables por el admin (ADR-0020): alta, cambio y borrado de roles, y
reemplazo de los roles de una persona.

Lo usa la API de Administración (`app/core/administracion.py`). Como
`usuarios_service.py`, devuelve el motivo del rechazo como texto (o None) y no
conoce el transporte. Los textos y el orden de las validaciones son los del
editor de roles del front (`src/core/administracion/roles.js`,
`motivoParaNoGuardar` y `motivoParaNoBorrar`): si cambian acá, cambian allá.

El catálogo de pantallas llega por parámetro (los `ModuloInfo` activos) porque
el núcleo no importa módulos. Para la API: el único motivo de alta o cambio que
es un conflicto (409) y no una validación (400) es el nombre repetido, y se
reconoce con `rol_con_el_nombre`; el de `borrar_rol` es siempre un conflicto.

`crear_rol`, `actualizar_rol` y `borrar_rol` son operaciones completas y hacen
commit. `reemplazar_roles` sólo deja el cambio en la sesión, como
`reemplazar_modulos`, para poder usarse dentro de otra operación (el alta en
lote); el commit es de quien la llama.
"""
import unicodedata
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.models import Rol, RolPermiso, Usuario, UsuarioRol
from app.core.modulos import ModuloInfo

NIVELES = ("ver", "editar")
LARGO_MAXIMO_NOMBRE = 60  # rol.nombre es VARCHAR(60)

# Lo que el editor del front trata como "sin acceso" (no se guarda: es que no
# haya fila). Se acepta igual que allá para que los dos validen lo mismo.
_SIN_NIVEL = (None, "", "sin")

Permisos = dict[str, dict[str, str | None]]


def _norm(texto: str | None) -> str:
    """El nombre como lo compara la base (collation utf8mb4_0900_ai_ci): sin
    espacios en los bordes, sin mayúsculas ni acentos. Mismo criterio que
    `_norm` de `precios.py` (ADR-0018), reescrito acá porque el núcleo no
    importa módulos; SQLite no compara así, por eso se hace en Python."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").strip().upper())
    return "".join(ch for ch in descompuesto if unicodedata.category(ch) != "Mn")


def _enumerar(nombres: list[str]) -> str:
    """"A", "A y B", "A, B y C"."""
    if len(nombres) <= 1:
        return nombres[0] if nombres else ""
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _con_nivel(pantallas: dict[str, str | None] | None) -> list[tuple[str, str]]:
    return [(clave, nivel) for clave, nivel in (pantallas or {}).items() if nivel not in _SIN_NIVEL]


def rol_con_el_nombre(db: Session, nombre: str | None, excluir_id: int | None = None) -> Rol | None:
    """El rol que ya se llama así, sin distinguir mayúsculas ni acentos.
    `excluir_id` es el rol que se está editando: su propio nombre no cuenta."""
    buscado = _norm(nombre)
    for rol in db.query(Rol).all():
        if rol.id != excluir_id and _norm(rol.nombre) == buscado:
            return rol
    return None


def motivo_para_no_guardar(db: Session, nombre: str | None, permisos: Permisos | None,
                           catalogo: Iterable[ModuloInfo], rol_id: int | None = None) -> str | None:
    """Por qué no se puede guardar el rol, o None. `permisos` es
    {modulo: {pantalla: nivel}}; `catalogo`, los módulos activos; `rol_id`, el
    del rol que se edita (None en el alta)."""
    nombre = (nombre or "").strip()
    if not nombre:
        return "El rol necesita un nombre."
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        return f"El nombre puede tener hasta {LARGO_MAXIMO_NOMBRE} caracteres."
    repetido = rol_con_el_nombre(db, nombre, excluir_id=rol_id)
    if repetido:
        return f'Ya hay un rol que se llama "{repetido.nombre}".'

    modulos = {m.clave: m for m in catalogo}
    alguna = False
    for clave_modulo, pantallas in (permisos or {}).items():
        con_nivel = _con_nivel(pantallas)
        if not con_nivel:
            continue
        modulo = modulos.get(clave_modulo)
        if modulo is None:
            return f'El módulo "{clave_modulo}" no existe o no está activo.'
        declaradas = {p.clave: p for p in modulo.pantallas}
        for clave_pantalla, nivel in con_nivel:
            pantalla = declaradas.get(clave_pantalla)
            if pantalla is None:
                return f'{modulo.nombre} no tiene la pantalla "{clave_pantalla}".'
            if nivel not in NIVELES:
                return f'{pantalla.nombre} tiene un nivel desconocido: "{nivel}".'
            if nivel == "editar" and not pantalla.editable:
                return f"{pantalla.nombre} sólo admite Ver."
            alguna = True
        # Regla `requiere`: una pantalla con nivel pide al menos Ver en cada una
        # de las que declara (Revisión se abre desde el Inicio del módulo).
        con_acceso = {clave for clave, _ in con_nivel}
        for clave_pantalla, _ in con_nivel:
            pantalla = declaradas[clave_pantalla]
            faltan = [clave for clave in pantalla.requiere if clave not in con_acceso]
            if faltan:
                nombres = [declaradas[c].nombre if c in declaradas else c for c in faltan]
                return f"{pantalla.nombre} necesita al menos Ver en {_enumerar(nombres)}."
    if not alguna:
        return "El rol tiene que dar acceso al menos a una pantalla."
    return None


def _filas(permisos: Permisos | None) -> list[RolPermiso]:
    return [
        RolPermiso(modulo=modulo, pantalla=pantalla, nivel=nivel)
        for modulo, pantallas in (permisos or {}).items()
        for pantalla, nivel in _con_nivel(pantallas)
    ]


def crear_rol(db: Session, nombre: str | None, permisos: Permisos | None,
              catalogo: Iterable[ModuloInfo]) -> tuple[Rol | None, str | None]:
    """(rol creado, None), o (None, motivo) sin crear nada."""
    catalogo = tuple(catalogo)
    motivo = motivo_para_no_guardar(db, nombre, permisos, catalogo)
    if motivo:
        return None, motivo
    rol = Rol(nombre=nombre.strip(), permisos=_filas(permisos))
    db.add(rol)
    db.commit()
    return rol, None


def actualizar_rol(db: Session, rol: Rol, nombre: str | None, permisos: Permisos | None,
                   catalogo: Iterable[ModuloInfo]) -> str | None:
    """Cambia el nombre y reemplaza los permisos de los módulos del catálogo
    (los activos); los de módulos que no están en él se conservan, porque el
    editor sólo muestra los activos. Devuelve el motivo, o None.

    Borra los permisos que se reemplazan y hace flush antes de insertar los
    nuevos: si no, SQLAlchemy inserta antes de borrar y una pantalla que queda
    choca contra la UNIQUE (rol_id, modulo, pantalla), como en
    `reemplazar_modulos`."""
    catalogo = tuple(catalogo)
    motivo = motivo_para_no_guardar(db, nombre, permisos, catalogo, rol_id=rol.id)
    if motivo:
        return motivo
    activos = {m.clave for m in catalogo}
    quedan = [p for p in rol.permisos if p.modulo not in activos]
    for permiso in list(rol.permisos):
        if permiso.modulo in activos:
            db.delete(permiso)
    db.flush()
    rol.nombre = nombre.strip()
    rol.permisos = quedan + _filas(permisos)
    db.commit()
    return None


def personas_con_rol(db: Session, rol: Rol) -> list[Usuario]:
    """Quiénes tienen el rol, por nombre. Las inactivas cuentan: si se
    reactivan, recuperan el acceso (plan, pregunta 8)."""
    return (
        db.query(Usuario)
        .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
        .filter(UsuarioRol.rol_id == rol.id)
        .order_by(Usuario.nombre, Usuario.id)
        .all()
    )


def borrar_rol(db: Session, rol: Rol) -> str | None:
    """Borra el rol con sus permisos si nadie lo tiene. Si alguien lo tiene
    (incluidas las personas inactivas) no borra nada y devuelve el motivo."""
    personas = personas_con_rol(db, rol)
    if personas:
        nombres = [p.nombre if p.activo else f"{p.nombre} (inactiva)" for p in personas]
        quienes = "Lo tiene 1 persona" if len(personas) == 1 else f"Lo tienen {len(personas)} personas"
        return f"{quienes}: {_enumerar(nombres)}. Sacáselo primero para poder borrarlo."
    db.delete(rol)
    db.commit()
    return None


def reemplazar_roles(db: Session, usuario: Usuario, rol_ids: Iterable[int]) -> str | None:
    """Deja a la persona con exactamente esos roles. Un id repetido cuenta una
    vez. Si algún id no existe no cambia nada y devuelve el motivo. No hace
    commit (ver la cabecera)."""
    ids = list(dict.fromkeys(rol_ids))
    por_id = {r.id: r for r in db.query(Rol).filter(Rol.id.in_(ids)).all()} if ids else {}
    for rol_id in ids:
        if rol_id not in por_id:
            return f"No existe el rol con id {rol_id}."
    usuario.roles = [por_id[i] for i in ids]
    db.flush()
    return None
