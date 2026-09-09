# Puesta a punto de una máquina nueva

Qué instalar y qué configurar para dejar los dos proyectos (backend y frontend) corriendo en una computadora desde cero. Pensado para Windows 11, que es donde se desarrolla hoy. Cada paso tiene su comprobación: si la comprobación falla, no seguir al paso siguiente.

Tiempo estimado: una hora, la mayor parte esperando descargas.

---

## 1. Programas a instalar

Instalar en este orden. Aceptar las opciones por defecto salvo donde se indique.

| Programa | Versión | De dónde | Nota |
|---|---|---|---|
| Git para Windows | la última | https://git-scm.com/download/win | Trae Git Bash, que se usa para los comandos de esta guía. Dejar "Git from the command line and also from 3rd-party software". |
| Python | **3.13** | https://www.python.org/downloads/ | Marcar **"Add python.exe to PATH"** en la primera pantalla del instalador. Si no, nada de lo que sigue funciona. |
| Node.js | **22 LTS** | https://nodejs.org/ | Trae npm. No instalar la versión "Current", solo LTS. |
| Visual Studio Code | la última | https://code.visualstudio.com/ | Editor. Cualquier otro sirve, pero este es el que usamos y para el que hay extensiones recomendadas abajo. |
| GitHub CLI | la última | https://cli.github.com/ | Para autenticarse contra GitHub sin manejar tokens a mano. Opcional pero recomendado. |

No instalar MySQL: las bases están en el servidor de la empresa y se accede a ellas por red.

### Comprobación

Abrir una terminal nueva (Git Bash o PowerShell) y ejecutar:

```bash
git --version
python --version
node --version
npm --version
```

Tienen que responder las cuatro. Python tiene que decir `3.13.x` y Node `v22.x`. Si `python` abre la Microsoft Store en vez de responder, el PATH no quedó bien: reinstalar Python marcando la casilla de PATH.

### Extensiones recomendadas para VS Code

- **Python** (Microsoft) y **Pylance**.
- **ES7+ React/Redux/React-Native snippets** o similar, opcional.
- **CSS Modules**, opcional, para autocompletar clases.
- **GitLens**, opcional.

---

## 2. Acceso a GitHub

Los dos repos son privados. Hace falta:

1. Una cuenta de GitHub. Pasarle el usuario a Gero para que la agregue como colaboradora en `Gerorios/Preliquidador_AST_BK` y `Gerorios/Preliquidador_AST_FT`.
2. Aceptar la invitación que llega por mail.
3. Autenticar la máquina. Lo más simple es con GitHub CLI:

```bash
gh auth login
```

Elegir GitHub.com, HTTPS, y autenticar por navegador. Después de esto, `git` ya puede clonar y pushear sin pedir contraseña.

4. Configurar la identidad de los commits:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-mail-de-github"
```

### Comprobación

```bash
gh auth status
```

Tiene que decir "Logged in to github.com".

---

## 3. Clonar los repos

Crear una carpeta para el proyecto y clonar los dos adentro, uno al lado del otro. La estructura esperada es:

```
Sistema_Preliquidacion/
├── backend_preliquidacion/
└── frontend_preliquidacion/
```

```bash
mkdir Sistema_Preliquidacion && cd Sistema_Preliquidacion
git clone https://github.com/Gerorios/Preliquidador_AST_BK.git backend_preliquidacion
git clone https://github.com/Gerorios/Preliquidador_AST_FT.git frontend_preliquidacion
```

El nombre de las carpetas importa: la documentación y los scripts asumen esos dos nombres.

---

## 4. Backend

En una terminal, dentro de `backend_preliquidacion/`:

```bash
python -m venv venv
```

Activar el entorno virtual. Esto hay que hacerlo **cada vez** que se abre una terminal nueva para trabajar en el backend:

```bash
# Git Bash
source venv/Scripts/activate
# PowerShell
venv\Scripts\Activate.ps1
# cmd
venv\Scripts\activate.bat
```

Si PowerShell se niega a ejecutar el script de activación por políticas de ejecución, correr una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y volver a intentar.

Con el entorno activado (aparece `(venv)` al principio de la línea):

```bash
pip install -r requirements-dev.txt
```

Instala las dependencias del sistema más pytest. Tarda unos minutos.

### El archivo `.env`

El backend no arranca sin un `.env` en la raíz de `backend_preliquidacion/` con las credenciales de las tres bases y la clave de la aplicación. **Ese archivo lo entrega Gero en mano.** No está en el repo, no se pide por chat, no se manda por mail, y no se commitea nunca (está en `.gitignore`).

La plantilla con todas las variables está en `.env.example`. Para desarrollo, `DB_PROPIA_NAME` tiene que ser `testing`, no `preliquidacion` (ver `GUIA-MODULOS.md`, sección 6.2).

### Comprobación

```bash
python verificar_conexion.py
```

Prueba las tres conexiones y muestra un resumen. Las tres tienen que dar OK. Si una falla, el problema es el `.env` o la red, no el código.

Después:

```bash
python -m pytest -q
```

Tiene que terminar en verde. Al día de hoy son 275 tests y tardan entre uno y cuatro minutos según la máquina. No necesitan las bases: usan SQLite en memoria.

Por último, arrancar el servidor:

```bash
uvicorn app.main:app --reload --port 8000
```

Tiene que imprimir el cartel de arranque con las tres bases en OK y quedar escuchando. Abrir http://localhost:8000/docs en el navegador: es la documentación interactiva de la API. Dejar esta terminal abierta mientras se trabaja.

---

## 5. Frontend

En **otra** terminal, dentro de `frontend_preliquidacion/`:

```bash
npm install
```

Instala las dependencias en `node_modules/`. Tarda unos minutos la primera vez.

### Comprobación

```bash
npm run build
```

Tiene que terminar con "built in" y sin errores. Después:

```bash
npm run dev
```

Queda escuchando en http://localhost:5173 y reenvía todo lo que empieza con `/api` al backend en el puerto 8000. Por eso el backend tiene que estar corriendo antes.

Abrir http://localhost:5173. Tiene que aparecer la pantalla de login. Entrar con el usuario que Gero haya creado en la base `testing`.

---

## 6. Rutina diaria

Cada vez que se empieza a trabajar:

1. Terminal 1, backend: `cd backend_preliquidacion`, activar el venv, `git pull`, `uvicorn app.main:app --reload --port 8000`.
2. Terminal 2, frontend: `cd frontend_preliquidacion`, `git pull`, `npm run dev`.
3. Si `git pull` trajo cambios en `requirements.txt` o `package.json`, volver a correr `pip install -r requirements-dev.txt` o `npm install`.
4. Crear la rama de trabajo antes de tocar nada: `git checkout -b feature/fletes-<tema>`.

Antes de abrir un PR:

```bash
python -m pytest -q      # backend, todo verde
npm run build            # frontend, sin errores
```

---

## 7. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `python` abre la Microsoft Store | Python no está en el PATH | Reinstalar marcando "Add python.exe to PATH" |
| `uvicorn: command not found` | El venv no está activado | Activar el venv (paso 4) |
| El backend arranca pero una base dice ERROR | `.env` mal cargado, o sin acceso de red al servidor | Revisar el `.env` con Gero |
| `UnicodeEncodeError` al arrancar | Consola de Windows sin UTF-8 | Ya está resuelto en `main.py`; si aparece, avisar |
| El frontend muestra "Error de red" al loguear | El backend no está corriendo, o no en el puerto 8000 | Arrancar el backend primero |
| `npm run dev` levanta en otro puerto | El 5173 está ocupado | Cerrar la otra instancia; el proxy y el CORS esperan el 5173 |
| Los tests fallan justo después de clonar | Faltan dependencias de desarrollo | `pip install -r requirements-dev.txt`, no solo `requirements.txt` |
| PowerShell no deja activar el venv | Política de ejecución | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| El asistente de ayuda responde 502 "Connection error" en local, el resto anda | Un antivirus con inspección HTTPS (Avast "análisis HTTPS", y similares) reemite los certificados; Python no confía en su raíz aunque el navegador sí | Desactivar la inspección HTTPS del antivirus (Avast: Protección, Escudos principales, Escudo web, "Habilitar análisis HTTPS"). No es un problema del código ni pasa en producción |

---

## 8. Qué leer después

1. `docs/modulos/GUIA-MODULOS.md`: cómo está armado el sistema y qué tiene que cumplir un módulo. Es la lectura principal.
2. `CONTEXT.md`: el glosario del dominio.
3. `README.md` del backend y del frontend: estructura y convenciones de cada uno.
4. Dos o tres tests de `tests/` para ver cómo se prueba la lógica sin base real.
