#!/bin/bash

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Executa amb sudo: sudo $0" 
  exit 1
fi

if [ $# != 4 ]; then
    echo "USAGE: sudo $0 [backendurl] [pk.pem] [server.crt] [token-enroll]" 
    exit 1
fi

REPO_URL="https://github.com/javichi338/candau.git"
DEST="/opt/candado"
SYSTEM_SERVICES="/etc/systemd/system/" 
TMP_DIR="$(mktemp -d)"
USUARIO="pti"    

backendurl=$1
pkConfigure="$(cat "$2")"
serverCrt=$3
tokenEnroll=$4

apt-get update
apt-get install -y git nodejs npm python3-venv python3-dbus bluez sqlite3 \
    swig python3-dev build-essential liblgpio-dev

git clone --depth 1 "$REPO_URL" "$TMP_DIR"

rm -rf "$DEST"

#distrubicio arxius
cp -a "$TMP_DIR/candado" "$DEST"
chown -R root:root "$DEST"

install -m 644 -o root -g root \
  "$TMP_DIR/candado-ble.service" \
  "$TMP_DIR/candado-express.service" \
  "$SYSTEM_SERVICES"

chown -R "$USUARIO":"$USUARIO" "$DEST"

#instalacio BD
apt install -y sqlite3
sudo sqlite3 /opt/candado/logs/logs.db <<'EOF' 
PRAGMA journal_mode=WAL;

CREATE TABLE logsBle (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha      TEXT NOT NULL DEFAULT (datetime('now')),
  evento     TEXT NOT NULL,
  resultado  TEXT,
  idlock     INTEGER,
  idUser     TEXT,
  idReserva  INTEGER,
  clavefirma TEXT,
  msg        TEXT
);

CREATE TABLE logsExpress (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha        TEXT NOT NULL DEFAULT (datetime('now')),
  evento       TEXT NOT NULL,
  resultado    TEXT,
  idlock       INTEGER,
  clavePublica TEXT,
  msg          TEXT
);

CREATE TRIGGER impedirBorradosBle BEFORE DELETE ON logsBle
WHEN OLD.fecha >= datetime('now', '-7 days')
BEGIN
  SELECT RAISE(ABORT, 'Operacion denegada. Se debe mantener un historial minimo de 7 dias');
END;

CREATE TRIGGER impedirModificacionesBle BEFORE UPDATE ON logsBle
BEGIN
  SELECT RAISE(ABORT, 'Operacion denegada. Los registros son inmutables.');
END;

CREATE TRIGGER impedirBorradosExpress BEFORE DELETE ON logsExpress
WHEN OLD.fecha >= datetime('now', '-7 days')
BEGIN
  SELECT RAISE(ABORT, 'Operacion denegada. Se debe mantener un historial minimo de 7 dias');
END;

CREATE TRIGGER impedirModificacionesExpress BEFORE UPDATE ON logsExpress
BEGIN
  SELECT RAISE(ABORT, 'Operacion denegada. Los registros son inmutables.');
END;
EOF

#depencencies serveis
(cd "$DEST" && npm install)
python3 -m venv --system-site-packages "$DEST/venv"
"$DEST/venv/bin/pip" install bless pyjwt cryptography rpi-lgpio

BACKEND_URL="$backendurl" ENROLL="$tokenEnroll" PK="$pkConfigure" ETC="$DEST/etc" node -e '
const fs = require("fs"), e = process.env;
fs.writeFileSync(e.ETC + "/configSocket.json", JSON.stringify(
  { backendUrl: e.BACKEND_URL, "x-enroll-token": e.ENROLL, "x-device-token": "" }, null, 2));
fs.writeFileSync(e.ETC + "/configCandau.json", JSON.stringify({ publicKey: e.PK }, null, 2));
'
chmod 600 "$DEST/etc/"*

rm -rf "$TMP_DIR"
apt-get purge -y git
apt-get autoremove -y

systemctl daemon-reload
systemctl enable --now candado-express.service candado-ble.service

######################################33
# OPCIONAL: desactivar el plugin midi de bluetoothd (descomenta si cal)
# mkdir -p /etc/systemd/system/bluetooth.service.d
# tee /etc/systemd/system/bluetooth.service.d/override.conf > /dev/null <<'EOF'
# [Service]
# ExecStart=
# ExecStart=/usr/libexec/bluetooth/bluetoothd --noplugin=midi
# EOF