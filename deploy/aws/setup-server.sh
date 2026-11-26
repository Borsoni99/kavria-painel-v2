#!/usr/bin/env bash
# Preparação única do servidor AWS Lightsail (Ubuntu 24.04). Executado pelo deploy.ps1 com -Setup.
set -euo pipefail

echo "==> Swap de 2 GB (o build do frontend precisa de folga na instância de 1 GB)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Docker e Docker Compose (pacotes oficiais do Ubuntu)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx sqlite3
systemctl enable --now docker

echo "==> Fuso horário e pastas"
timedatectl set-timezone America/Sao_Paulo || true
mkdir -p /opt/kavria/data
# uid 1000 = usuário 'kavria' dentro do container (dono do banco, logs e backups)
chown -R 1000:1000 /opt/kavria/data

echo "==> Atualizações de segurança automáticas"
apt-get install -y unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo "Servidor pronto."
