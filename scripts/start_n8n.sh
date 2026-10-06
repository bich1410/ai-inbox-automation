#!/usr/bin/env bash
# Chạy n8n trong GitHub Codespaces.
set -e

# Dừng ngay nếu không chạy trong Codespaces (vì khi đó địa chỉ bên dưới sẽ sai)
: "${CODESPACE_NAME:?This script is meant for GitHub Codespaces}"

# Địa chỉ công khai của cổng 5678, để các link của n8n (như form upload) mở được từ trình duyệt
export WEBHOOK_URL="https://${CODESPACE_NAME}-5678.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"

# n8n đứng sau proxy của Codespaces, cần khai báo để không báo lỗi header
export N8N_PROXY_HOPS=1

npx n8n