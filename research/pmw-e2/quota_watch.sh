#!/bin/sh
# Vigila el restablecimiento de la cuota de Open-Meteo Single Runs (1 petición cada 15 min). Sale con 0 cuando responde 200.
URL="https://single-runs-api.open-meteo.com/v1/forecast?latitude=51.5&longitude=0&hourly=temperature_2m&models=icon_d2&run=2026-06-02T18:00&timezone=UTC"
while :; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0' --max-time 30 "$URL" || echo 000)
  echo "$(date -u +%FT%TZ) HTTP $code"
  [ "$code" = "200" ] && { echo "CUOTA_RESTABLECIDA $(date -u +%FT%TZ)"; exit 0; }
  sleep 900
done
