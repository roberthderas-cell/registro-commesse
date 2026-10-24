#!/usr/bin/env bash
# Dal portatile: SOSTITUISCE i dati del server con quelli del portatile (database e documenti caricati).
#   ./deploy/porta-dati.sh ubuntu@INDIRIZZO_IP [chiave-ssh]
set -euo pipefail
dest=${1:?"Uso: ./deploy/porta-dati.sh ubuntu@INDIRIZZO_IP [chiave-ssh]"}
ssh_cmd=(ssh -o StrictHostKeyChecking=accept-new); scp_cmd=(scp -o StrictHostKeyChecking=accept-new)
[ -n "${2:-}" ] && ssh_cmd+=(-i "$2") && scp_cmd+=(-i "$2")
cd "$(dirname "$0")/../backend"
[ -f data/registro.db ] || { echo "Nessun database locale in backend/data/registro.db"; exit 1; }

read -rp "Tutti i dati attuali del server verranno sostituiti da quelli del portatile. Scrivi SOSTITUISCI per procedere: " ok
[ "$ok" = "SOSTITUISCI" ] || { echo "Annullato."; exit 1; }

# copia coerente del database anche se l'app locale è accesa
python3 -c "import sqlite3; s=sqlite3.connect('data/registro.db'); d=sqlite3.connect('/tmp/rc-export.db'); s.backup(d); d.close()"
"${scp_cmd[@]}" /tmp/rc-export.db "$dest":registro-commesse/import.db
rm -f /tmp/rc-export.db
"${ssh_cmd[@]}" "$dest" 'cd ~/registro-commesse && sudo docker compose run --rm -T -v "$PWD/import.db:/import/registro.db:ro" app python scripts/trasferisci_dati.py --da sqlite:////import/registro.db --sovrascrivi && rm import.db'
if [ -d data/documenti ]; then
  tar -C data -cf - documenti | "${ssh_cmd[@]}" "$dest" 'cd ~/registro-commesse && sudo docker cp - "$(sudo docker compose ps -q app)":/app/backend/data/'
fi
echo "Dati trasferiti. Gli utenti e le password sono quelli del portatile."
