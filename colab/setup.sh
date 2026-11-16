#!/usr/bin/env bash
# Set up the Week 6 lab on Google Colab (or any Ubuntu machine where you are root), without Docker.
# Installs PostgreSQL 17, starts it with the same planner settings as docker-compose.yml,
# downloads the lab files and loads the data. Safe to run again: it skips what is already done.
#
#   LAB_BRANCH=main bash setup.sh
set -euo pipefail

BRANCH="${LAB_BRANCH:-main}"
BASE="https://raw.githubusercontent.com/edward1503/adbs-week6-lab/${BRANCH}"
PORT=55432

step() { echo "[$(date +%H:%M:%S)] $*"; }
export DEBIAN_FRONTEND=noninteractive

# 0. tools the script needs (already present on Colab)
if ! command -v curl >/dev/null || ! command -v sudo >/dev/null || ! command -v lsb_release >/dev/null; then
  step "Installing curl and sudo"
  apt-get update -qq >/dev/null
  apt-get install -y -qq curl ca-certificates lsb-release sudo >/dev/null
fi

# 1. lab files (never overwrite answers.json: it holds the student's answers)
step "Downloading the lab files ($BRANCH)"
for f in notebooks/labkit.py tests/conftest.py tests/test_lab.py pytest.ini data/01_init.sql answers.json; do
  if [[ "$f" == answers.json && -f "$f" ]]; then continue; fi
  mkdir -p "$(dirname "$f")"
  curl -fsSL "$BASE/$f" -o "$f"
done

# 2. Python packages (pandas and IPython are already on Colab)
step "Installing Python packages"
python3 -m pip install -q "psycopg[binary]==3.2.3" pytest==8.3.3 pandas >/dev/null

# 3. PostgreSQL 17 from the PostgreSQL apt repository
if [[ ! -x /usr/lib/postgresql/17/bin/postgres ]]; then
  step "Installing PostgreSQL 17 (about a minute)"
  install -d /usr/share/postgresql-common/pgdg
  curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update -qq >/dev/null
  # do not create the default cluster; we create our own below
  mkdir -p /etc/postgresql-common && echo "create_main_cluster = false" > /etc/postgresql-common/createcluster.conf
  apt-get install -y -qq postgresql-17 >/dev/null
fi
PSQL_ADMIN=(sudo -u postgres psql -p "$PORT" -v ON_ERROR_STOP=1 -qAt)   # sudo: on Colab, or installed above

# 4. a cluster with the same settings as docker-compose.yml
if ! pg_lsclusters -h | awk '{print $1"/"$2}' | grep -qx "17/lab"; then
  step "Creating the database server"
  pg_createcluster 17 lab -p "$PORT" \
    -o max_parallel_workers_per_gather=0 -o jit=off -o random_page_cost=4 \
    -o shared_buffers=128MB -o work_mem=4MB >/dev/null
fi
pg_ctlcluster 17 lab start 2>/dev/null || true

# 5. user, database and data (same as the Docker image: user lab is a superuser)
if [[ "$("${PSQL_ADMIN[@]}" -c "SELECT 1 FROM pg_roles WHERE rolname='lab'")" != 1 ]]; then
  "${PSQL_ADMIN[@]}" -c "CREATE ROLE lab LOGIN SUPERUSER PASSWORD 'lab'"
fi
if [[ "$("${PSQL_ADMIN[@]}" -c "SELECT 1 FROM pg_database WHERE datname='tickets'")" != 1 ]]; then
  step "Loading the lab data (about 30 seconds)"
  "${PSQL_ADMIN[@]}" -c "CREATE DATABASE tickets OWNER lab"
  PGPASSWORD=lab psql -h localhost -p "$PORT" -U lab -d tickets -v ON_ERROR_STOP=1 -q -f data/01_init.sql >/dev/null
fi

step "Ready: PostgreSQL $("${PSQL_ADMIN[@]}" -c 'SHOW server_version'), database 'tickets' on port $PORT"
