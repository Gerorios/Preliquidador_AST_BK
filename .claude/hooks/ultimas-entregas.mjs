// Hook SessionStart: imprime las 2 últimas entradas de la bitácora del backend para que cada sesión arranque
// sabiendo lo último que se hizo (lo pendiente lo trae docs/estado.md, que importa CLAUDE.md). Claude Code suma al
// contexto lo que este hook escribe en stdout, con un tope de 10.000 caracteres.
//
// El mismo archivo se copia tal cual en el front y en la carpeta que contiene los dos repos: la bitácora es una
// sola y vive en el backend, así que el hook la busca subiendo por las carpetas en vez de suponer dónde arrancó la
// sesión.
//
// Sale siempre con 0: si falta la bitácora o algo falla, la sesión arranca igual.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const ENTRADAS = 2;
const TOPE = 8000; // por debajo del límite de 10.000 de Claude Code
const REPO_BITACORA = "backend_preliquidacion";

// Busca <ancestro>/backend_preliquidacion/docs/BITACORA.md desde la carpeta de la sesión hacia arriba. Eso cubre
// la carpeta de los dos repos, el backend mismo, el front y los worktrees de cualquiera de los dos (que viven en
// <repo>/.claude/worktrees/<nombre>). Si no aparece, un clon del backend con otro nombre de carpeta usa su propia
// docs/BITACORA.md. Si tampoco está, no hay nada que mostrar.
function buscarBitacora(inicio) {
  let actual = resolve(inicio);
  for (;;) {
    const candidata = join(actual, REPO_BITACORA, "docs", "BITACORA.md");
    if (existsSync(candidata)) return candidata;
    const padre = dirname(actual);
    if (padre === actual) break; // llegó a la raíz del disco
    actual = padre;
  }
  const propia = join(resolve(inicio), "docs", "BITACORA.md");
  return existsSync(propia) ? propia : null;
}

try {
  const inicio = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const ruta = buscarBitacora(inicio);
  if (!ruta) process.exit(0);
  // estado.md vive al lado de la bitácora. Se imprime la ruta absoluta porque el @import de CLAUDE.md no resuelve
  // desde un worktree del front: así la sesión sabe dónde leerlo igual.
  const rutaEstado = join(dirname(ruta), "estado.md");

  // La bitácora real tiene CRLF en Windows: se normaliza para cortar bien y no pasarle \r al contexto.
  // Cada entrada empieza con "## "; lo de antes del primer "## " es la introducción del diario y no se muestra.
  const secciones = readFileSync(ruta, "utf8")
    .replace(/\r\n?/g, "\n")
    .split(/^(?=## )/m)
    .filter((s) => s.startsWith("## "));
  if (secciones.length === 0) process.exit(0);

  // La bitácora es append-only con la más nueva abajo: las últimas son las del final del archivo, y se muestran en
  // el mismo orden en que están (penúltima, última) para no contradecir lo que se lee al abrirla.
  const ultimas = secciones.slice(-ENTRADAS);
  const titulo = ultimas.length === 1 ? "Última entrega" : `Últimas ${ultimas.length} entregas`;
  let texto =
    `${titulo} de la bitácora (${ruta}), en orden de archivo: la más reciente al final. ` +
    `Lo pendiente y en curso está en ${rutaEstado}.\n\n` +
    ultimas.join("").trim();
  // Con entradas largas se corta la última y se avisa: mejor un recorte visible que pasarse del tope y que Claude
  // Code descarte o trunque sin decirlo.
  if (texto.length > TOPE) texto = texto.slice(0, TOPE) + `\n… (recortado: el resto está en ${ruta})`;

  process.stdout.write(texto + "\n");
} catch {
  // Nunca bloquear el arranque.
}
// exitCode y no process.exit(): así node termina de vaciar stdout antes de salir, aunque la salida sea larga y
// stdout sea un pipe asíncrono (macOS, por ejemplo).
process.exitCode = 0;
