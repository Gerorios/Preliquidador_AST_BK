#!/bin/sh
# Hook PostToolUse de Claude Code: después de un `gh pr merge`, le recuerda a
# Claude que pregunte si corre /bitacora. No corre nada ni bloquea nada.
# Lee el JSON del evento por stdin; grep sobre el texto crudo, sin jq.

entrada=$(cat)
printf '%s' "$entrada" | grep -Eq 'gh(\.exe)?(\\")? +pr +merge' || exit 0

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Se acaba de mergear un PR. Preguntale al usuario, en una línea, si corrés /bitacora. No lo corras sin preguntar: escribe directo en main."}}'
