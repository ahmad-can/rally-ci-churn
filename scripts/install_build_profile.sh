#!/bin/sh
set -eu

export DEBIAN_FRONTEND=noninteractive

if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        devscripts \
        dpkg-dev \
        fakeroot \
        git \
        pkg-config \
        python3 \
        python3-venv \
        tar
fi

mkdir -p "$HOME/.rally-ci-churn"
cat > "$HOME/.rally-ci-churn/build-profile.txt" <<'EOF'
This image was prepared for representative CI build profiles.
EOF
