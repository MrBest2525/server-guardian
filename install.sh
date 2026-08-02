#!/bin/bash

set -e

APP_NAME="server-guardian"

INSTALL_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"

echo "=== Installing $APP_NAME ==="

# root確認
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root."
    exit 1
fi

# 必要パッケージ
apt update
apt install -y \
    python3 \
    python3-yaml \
    wakeonlan

# 配置
mkdir -p "$INSTALL_DIR"
install -Dm644 server_guardian.py "$INSTALL_DIR/server_guardian.py"

# 設定
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    cp config.example.yml "$CONFIG_DIR/config.yml"
    echo "Created config.yml"
else
    echo "config.yml already exists. Skipped."
fi

# systemd
install -Dm644 server-guardian.service \
    /etc/systemd/system/server-guardian.service

systemctl daemon-reload
systemctl enable server-guardian

echo
echo "Installation completed."
echo
echo "Edit:"
echo "  $CONFIG_DIR/config.yml"
echo
echo "Start:"
echo "  systemctl start server-guardian"