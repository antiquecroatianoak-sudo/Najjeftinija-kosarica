#!/usr/bin/env bash
# Ista topologija kao kontejneri/compose.provjera.yaml, ali kao lokalni procesi (bez Dockera).
# Pokretanje iz mape energija/:  bash provjera/pokreni_lokalno.sh
set -euo pipefail
cd "$(dirname "$0")/.."
RAD=$(mktemp -d)
KOD=482915
trap 'kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; rm -rf "$RAD" || true' EXIT

cat > "$RAD/postavke.json" <<EOF
{"otkrivanje": {"modbus_hostovi": [["127.0.0.1", 15020]], "modbus_jedinice": [1, 2]},
 "prognoza": {"url": "http://127.0.0.1:18080/v1/forecast"},
 "mqtt": {"port": 11883}, "api": {"port": 18443}}
EOF

python3 -m simulator.mock_openmeteo --port 18080 > "$RAD/openmeteo.log" 2>&1 &
ENERGIJA_KOD=$KOD ENERGIJA_PODACI="$RAD" python3 -m jezgra --podaci "$RAD" > "$RAD/jezgra.log" 2>&1 &
python3 -m simulator.modbus_pymodbus --modbus-port 15020 --mqtt-port 11883 --http-port 18081 --brzina 60 \
  > "$RAD/simulator.log" 2>&1 &

JEZGRA_URL=https://localhost:18443 SIM_URL=http://127.0.0.1:18081 OPENMETEO_URL=http://127.0.0.1:18080 \
CA="$RAD/certifikati/ca.pem" ENERGIJA_KOD=$KOD ROK_S=90 python3 provjera/provjera_sustava.py && STATUS=0 || STATUS=$?

if [ $STATUS -ne 0 ]; then echo "--- jezgra.log"; tail -30 "$RAD/jezgra.log"; echo "--- simulator.log"; tail -30 "$RAD/simulator.log"; fi
exit $STATUS
