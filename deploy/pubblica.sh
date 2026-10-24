#!/usr/bin/env bash
# Dal portatile: copia sul server l'ultima versione salvata in git e la avvia (o la aggiorna).
#   ./deploy/pubblica.sh ubuntu@INDIRIZZO_IP [percorso/chiave-ssh]
set -euo pipefail
dest=${1:?"Uso: ./deploy/pubblica.sh ubuntu@INDIRIZZO_IP [chiave-ssh]"}
ssh_cmd=(ssh -o StrictHostKeyChecking=accept-new)
[ -n "${2:-}" ] && ssh_cmd+=(-i "$2")
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain)" ]; then
  echo "Attenzione: ci sono modifiche non salvate in git; viene pubblicata l'ultima versione salvata."
fi
echo "Pubblico la versione $(git rev-parse --short HEAD) su ${dest}"
# Solo i file in git: niente database locale, credenziali o ambienti di sviluppo
git archive --format=tar HEAD | "${ssh_cmd[@]}" "$dest" 'mkdir -p ~/registro-commesse && tar -x -C ~/registro-commesse'
"${ssh_cmd[@]}" -t "$dest" 'bash ~/registro-commesse/deploy/installa-server.sh'
