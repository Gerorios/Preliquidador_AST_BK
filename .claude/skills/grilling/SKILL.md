---
name: grilling
description: Grill the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any 'grill' trigger phrases.
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a question can be answered by exploring the codebase, explore the codebase instead.

Do not enact the plan until I confirm we have reached a shared understanding.

## En este repo

- **Paso 0, antes de la primera pregunta:** buscar antecedentes del tema con
  `grep -n -i` en `docs/BITACORA.md` y en `docs/adr/`, leer las entradas que
  coincidan, y decir qué se encontró (o que no se encontró nada). Ahí está lo ya
  decidido y lo ya descartado; no se vuelve a proponer sin decir por qué reabrirlo.
- Si el tema toca términos del dominio o una decisión difícil de revertir, usar
  `domain-modeling`.
- Los ADR los escribe el usuario, nunca un agente solo.
- Las preguntas van en español.
