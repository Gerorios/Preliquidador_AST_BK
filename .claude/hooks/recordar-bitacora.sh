#!/bin/sh
# Hook PostToolUse de Claude Code: después de un `gh pr merge`, le recuerda a
# Claude que corra /bitacora sin preguntar. No corre nada ni bloquea nada.
#
# Mira sólo el comando (tool_input.command), no la salida: un texto que
# menciona el comando no cuenta. gh tiene que estar en posición de comando
# (al principio o después de ; & | o salto de línea), como `gh`, una ruta a
# gh.exe o una variable ("$G"). Sin Python no hace nada.

entrada=$(cat)
printf '%s' "$entrada" | python -c '
import json, re, sys
try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(1)
patron = r"(^|[\n;&|(])\s*(\"[^\"]*gh(\.exe)?\"|\S*gh(\.exe)?|\"?\$\{?\w+\}?\"?)\s+pr\s+merge\b"
sys.exit(0 if re.search(patron, cmd) else 1)
' 2>/dev/null || exit 0

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Se acaba de mergear un PR. Corré /bitacora sin preguntar (AGENTS.md, Bitácora y estado): commiteá BITACORA.md y estado.md a main, sin push, y avisale al usuario en una línea qué archivos quedaron anotados."}}'
