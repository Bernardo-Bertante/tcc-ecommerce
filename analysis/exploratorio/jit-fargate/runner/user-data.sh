#!/bin/bash
# user-data do exp-jit-runner (AL2023): ferramentas do driver. Log em /var/log/exp-jit-userdata.log
exec > /var/log/exp-jit-userdata.log 2>&1
set -x
dnf install -y jq postgresql16 python3 tar gzip
dnf install -y https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm
mkdir -p /opt/k6 && cd /opt/k6
curl -sSL https://github.com/grafana/k6/releases/download/v0.45.0/k6-v0.45.0-linux-amd64.tar.gz | tar xz
install -m 0755 /opt/k6/k6-v0.45.0-linux-amd64/k6 /usr/local/bin/k6
mkdir -p /home/ec2-user/exp-jit && chown ec2-user:ec2-user /home/ec2-user/exp-jit
k6 version; psql --version; session-manager-plugin --version
touch /var/log/exp-jit-userdata.DONE
