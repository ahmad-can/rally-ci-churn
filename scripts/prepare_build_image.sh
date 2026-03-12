#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage:
  prepare_build_image.sh \
    --base-image IMAGE \
    --build-image IMAGE \
    --flavor FLAVOR \
    --network NETWORK \
    --floating-network NETWORK \
    --ssh-user USER \
    --key-name KEYPAIR \
    --identity-file PRIVATE_KEY

Optional flags:
  --security-group GROUP   Security group to use (default: default)
  --install-script PATH    Local script to execute on the temporary server
  --server-name NAME       Temporary server name prefix
  --keep-server            Do not delete the temporary server on failure

The script expects a working OpenStack CLI environment via OS_* variables.
EOF
}

BASE_IMAGE=""
BUILD_IMAGE=""
FLAVOR=""
NETWORK=""
FLOATING_NETWORK=""
SSH_USER=""
KEY_NAME=""
IDENTITY_FILE=""
SECURITY_GROUP="default"
INSTALL_SCRIPT="$(dirname "$0")/install_build_profile.sh"
SERVER_NAME_PREFIX="rally-build-image"
KEEP_SERVER=0

while [ $# -gt 0 ]; do
    case "$1" in
        --base-image) BASE_IMAGE="$2"; shift 2 ;;
        --build-image) BUILD_IMAGE="$2"; shift 2 ;;
        --flavor) FLAVOR="$2"; shift 2 ;;
        --network) NETWORK="$2"; shift 2 ;;
        --floating-network) FLOATING_NETWORK="$2"; shift 2 ;;
        --ssh-user) SSH_USER="$2"; shift 2 ;;
        --key-name) KEY_NAME="$2"; shift 2 ;;
        --identity-file) IDENTITY_FILE="$2"; shift 2 ;;
        --security-group) SECURITY_GROUP="$2"; shift 2 ;;
        --install-script) INSTALL_SCRIPT="$2"; shift 2 ;;
        --server-name) SERVER_NAME_PREFIX="$2"; shift 2 ;;
        --keep-server) KEEP_SERVER=1; shift 1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
    esac
done

for required in BASE_IMAGE BUILD_IMAGE FLAVOR NETWORK FLOATING_NETWORK SSH_USER KEY_NAME IDENTITY_FILE; do
    eval "value=\${$required}"
    if [ -z "$value" ]; then
        echo "Missing required option: $required" >&2
        usage
        exit 2
    fi
done

for binary in openstack ssh scp; do
    command -v "$binary" >/dev/null 2>&1 || {
        echo "Required command not found: $binary" >&2
        exit 2
    }
done

[ -r "$IDENTITY_FILE" ] || {
    echo "Identity file is not readable: $IDENTITY_FILE" >&2
    exit 2
}

[ -r "$INSTALL_SCRIPT" ] || {
    echo "Install script is not readable: $INSTALL_SCRIPT" >&2
    exit 2
}

SERVER_NAME="${SERVER_NAME_PREFIX}-$(date +%s)"
SERVER_ID=""
FLOATING_IP_ID=""
FLOATING_IP_ADDRESS=""

cleanup() {
    set +e
    if [ -n "$SERVER_ID" ] && [ "$KEEP_SERVER" -eq 0 ]; then
        openstack server delete --wait "$SERVER_ID" >/dev/null 2>&1
    fi
    if [ -n "$FLOATING_IP_ID" ] && [ "$KEEP_SERVER" -eq 0 ]; then
        openstack floating ip delete "$FLOATING_IP_ID" >/dev/null 2>&1
    fi
}
trap cleanup EXIT INT TERM

echo "Creating temporary server $SERVER_NAME" >&2
SERVER_ID="$(
    openstack server create \
        --image "$BASE_IMAGE" \
        --flavor "$FLAVOR" \
        --network "$NETWORK" \
        --key-name "$KEY_NAME" \
        --security-group "$SECURITY_GROUP" \
        --wait \
        -f value \
        -c id \
        "$SERVER_NAME"
)"

FLOATING_IP_ID="$(
    openstack floating ip create \
        "$FLOATING_NETWORK" \
        -f value \
        -c id
)"
FLOATING_IP_ADDRESS="$(
    openstack floating ip show \
        "$FLOATING_IP_ID" \
        -f value \
        -c floating_ip_address
)"
openstack server add floating ip "$SERVER_ID" "$FLOATING_IP_ADDRESS"

SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i $IDENTITY_FILE"

echo "Waiting for SSH on $FLOATING_IP_ADDRESS" >&2
attempt=0
until ssh $SSH_OPTS "$SSH_USER@$FLOATING_IP_ADDRESS" true >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 120 ]; then
        echo "SSH did not become ready on $FLOATING_IP_ADDRESS" >&2
        exit 1
    fi
    sleep 5
done

echo "Uploading and executing build profile bootstrap" >&2
scp $SSH_OPTS "$INSTALL_SCRIPT" "$SSH_USER@$FLOATING_IP_ADDRESS:~/install_build_profile.sh" >/dev/null
ssh $SSH_OPTS "$SSH_USER@$FLOATING_IP_ADDRESS" 'chmod +x ~/install_build_profile.sh && ~/install_build_profile.sh'

echo "Stopping server before snapshot" >&2
openstack server stop --wait "$SERVER_ID"

echo "Creating image $BUILD_IMAGE" >&2
openstack server image create --wait --name "$BUILD_IMAGE" "$SERVER_ID" >/dev/null

echo "Build image ready: $BUILD_IMAGE"
