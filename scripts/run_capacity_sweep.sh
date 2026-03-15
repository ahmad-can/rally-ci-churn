#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

usage() {
    cat <<EOF
Usage: $0 --clouds-yaml /path/to/clouds.yaml [options]

Run or generate a percentage-based capacity sweep across the load-bearing
benchmark scenarios.

Examples:
  $0 --clouds-yaml /home/ubuntu/.config/openstack/clouds.yaml
  $0 --clouds-yaml /home/ubuntu/.config/openstack/clouds.yaml --levels 10,25
  $0 --clouds-yaml /home/ubuntu/.config/openstack/clouds.yaml --generate-only
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

if [ ! -d "${VENV_DIR}" ]; then
    echo "Missing .venv at ${VENV_DIR}." >&2
    echo "Run ./scripts/setup_uv.sh first." >&2
    exit 1
fi

export RALLY_CI_CHURN_OPENSTACK_BIN="${VENV_DIR}/bin/openstack"
export RALLY_CI_CHURN_RALLY_BIN="${VENV_DIR}/bin/rally"

exec "${VENV_DIR}/bin/python" -m rally_ci_churn.bootstrap.capacity_sweep "$@"
