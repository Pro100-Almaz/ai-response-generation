#! /usr/bin/env bash

set -e
set -o pipefail

# Run prestart tasks: wait for DB, apply migrations, seed data
bash scripts/prestart.sh

# Exec the passed command (e.g. uvicorn ...)
exec "$@"


