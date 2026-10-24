#!/usr/bin/env bash
# Dal portatile: scarica le copie di sicurezza del server in ./backup-server (da tenere anche fuori dal server).
#   ./deploy/scarica-backup.sh ubuntu@INDIRIZZO_IP [chiave-ssh]
set -euo pipefail
dest=${1:?"Uso: ./deploy/scarica-backup.sh ubuntu@INDIRIZZO_IP [chiave-ssh]"}
opz=(-o StrictHostKeyChecking=accept-new); [ -n "${2:-}" ] && opz+=(-i "$2")
cd "$(dirname "$0")/.."
mkdir -p backup-server
rsync -av --ignore-existing -e "ssh ${opz[*]}" "$dest":registro-commesse/backup/ backup-server/
echo "Copie di sicurezza in $(pwd)/backup-server"
