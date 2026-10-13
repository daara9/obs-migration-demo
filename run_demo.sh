#!/usr/bin/env bash
# Orquestra a demo de migracao on-prem -> OBS (Singapura).
# Uso: ./run_demo.sh [--quick]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"
GEN_ARGS=()
if [[ "${1:-}" == "--quick" ]]; then
  GEN_ARGS=(--small 1000 --large 4 --dump-mb 50)
  echo "[demo] perfil QUICK"
fi

echo "============================================================"
echo " FASE 1/3 - Assessment: gerando origem on-prem"
echo "============================================================"
"$PY" "$DIR/generate_onprem.py" "${GEN_ARGS[@]}"

echo
echo "============================================================"
echo " FASE 2/3 - Transferencia: on-prem -> OBS (ap-southeast-1)"
echo "============================================================"
"$PY" "$DIR/migrate.py" --workers 64 --resume

echo
echo "============================================================"
echo " FASE 3/3 - Verificacao: integridade origem x destino"
echo "============================================================"
"$PY" "$DIR/verify.py"

echo
echo "[demo] concluida."
