#!/usr/bin/env bash
# Eseguito SUL SERVER (Ubuntu) da deploy/pubblica.sh: si può rilanciare quante volte si vuole.
# Installa Docker se manca, apre le porte web nel firewall, crea il file .env la prima volta,
# poi costruisce e avvia (o aggiorna) l'applicazione.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null || ! sudo docker compose version >/dev/null 2>&1; then
  echo "== Installo Docker"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 >/dev/null
  sudo systemctl enable --now docker
fi

# Le immagini Ubuntu di Oracle Cloud bloccano tutto tranne SSH: apriamo HTTP e HTTPS
for porta in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$porta" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 1 -p tcp --dport "$porta" -j ACCEPT
  fi
done
sudo iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
if command -v netfilter-persistent >/dev/null; then sudo netfilter-persistent save >/dev/null 2>&1 || true; fi

# Con poca memoria (server da 1 GB) la compilazione del frontend ha bisogno di swap
if [ "$(awk '/MemTotal/{print $2}' /proc/meminfo)" -lt 2000000 ] && ! swapon --show | grep -q .; then
  echo "== Aggiungo 2 GB di swap"
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

if [ ! -f .env ]; then
  echo "== Prima configurazione"
  ip=$(curl -fsS -4 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
  proposto="${ip//./-}.sslip.io"
  read -rp "Indirizzo web dell'app [${proposto}]: " dominio
  read -rp "Partita IVA dell'azienda (es. IT01234560157): " piva
  umask 077
  cat > .env <<FINE
DOMINIO=${dominio:-$proposto}
PIVA_AZIENDA=${piva}
DB_PASSWORD=$(openssl rand -hex 24)
ADMIN_PASSWORD=
BACKUP_GIORNI=30
FINE
  echo "Impostazioni salvate in $(pwd)/.env"
fi
mkdir -p backup

echo "== Costruisco e avvio l'applicazione (la prima volta ci vogliono alcuni minuti)"
sudo docker compose up -d --build --remove-orphans
sudo docker image prune -f >/dev/null

dominio=$(grep '^DOMINIO=' .env | cut -d= -f2)
echo -n "== Attendo che l'app risponda"
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "https://${dominio}/api/salute" 2>/dev/null; then echo " ok"; break; fi
  echo -n "."; sleep 5
done

echo
echo "  Registro Commesse: https://${dominio}"
if sudo docker compose exec -T app test -f data/primo_accesso.txt 2>/dev/null; then
  echo
  sudo docker compose exec -T app cat data/primo_accesso.txt
  echo "  Dopo il primo accesso cancella le credenziali con:"
  echo "    cd ~/registro-commesse && sudo docker compose exec app rm data/primo_accesso.txt"
fi
