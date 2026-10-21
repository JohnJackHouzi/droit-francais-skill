#!/bin/sh
set -e
mkdir -p "$DROIT_DATA"
if [ "${DROIT_AUTO_UPDATE:-1}" = "1" ]; then
  if [ "${DROIT_AUTO_INSTALL:-1}" = "1" ]; then
    python -I scripts/install.py --service &
  else
    python -I scripts/install.py --service --sans-installation &
  fi
fi
exec python server/server.py
