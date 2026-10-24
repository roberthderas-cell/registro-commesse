#!/bin/sh
# Ogni notte alle 2: dump del database e archivio dei documenti caricati, tenuti per $GIORNI giorni.
# Una copia si fa anche subito all'avvio del servizio.
set -u
copia() {
  t=$(date +%Y%m%d-%H%M)
  if pg_dump -h db -U registro -d registro --no-owner | gzip > "/backup/registro-$t.sql.gz.tmp"; then
    mv "/backup/registro-$t.sql.gz.tmp" "/backup/registro-$t.sql.gz"
    tar -czf "/backup/documenti-$t.tar.gz" -C /dati documenti 2>/dev/null || true
    find /backup -name 'registro-*.sql.gz' -mtime +"$GIORNI" -delete
    find /backup -name 'documenti-*.tar.gz' -mtime +"$GIORNI" -delete
    echo "$(date '+%F %T') copia di sicurezza fatta: registro-$t.sql.gz"
  else
    rm -f "/backup/registro-$t.sql.gz.tmp"
    echo "$(date '+%F %T') ERRORE: copia di sicurezza non riuscita" >&2
  fi
}
copia
while true; do
  adesso=$(date +%s)
  prossima=$(date -d "$(date +%F) 02:00" +%s 2>/dev/null || echo $((adesso + 86400)))
  [ "$prossima" -le "$adesso" ] && prossima=$((prossima + 86400))
  sleep $((prossima - adesso))
  copia
done
