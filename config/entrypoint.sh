#!/bin/sh
# =====================================================================
# Odoo Ecuador — production entrypoint (LIVE-CONFIG)
#
# Two sources, one clear split:
#   * TUNABLES  -> /etc/odoo/odoo.conf  (LIVE bind-mount from ./config/odoo.conf)
#                  Edit the file + `docker compose restart odoo` = applied.
#                  NO image rebuild / redeploy required.
#   * SECRETS   -> environment (.env / compose)  gitignored
#                  Injected into the config at boot so credentials never
#                  live in a mountable, committable file.
#
# If no config file is mounted, it falls back to rendering entirely from
# env (kept for `docker compose run` ad-hoc/install containers).
# =====================================================================
set -e

# ---- Secrets & connection (source: .env / compose env) --------------
: "${ODOO_DB:=odooec}"
: "${ODOO_ADMIN_PASSWD:=change-me-master}"
: "${ODOO_DB_TEMPLATE:=template0}"
: "${HOST:=db}"
: "${DB_PORT:=5432}"
: "${USER:=odoo}"
: "${PASSWORD:=odoo}"

# ---- Fallback tunables (only used when NO config file is mounted) ---
: "${ODOO_WORKERS:=4}"
: "${ODOO_MAX_CRON_THREADS:=1}"
: "${ODOO_PROXY_MODE:=true}"
: "${ODOO_LIST_DB:=true}"
: "${ODOO_DBFILTER:=odooec.*}"
: "${ODOO_LIMIT_TIME_CPU:=1200}"
: "${ODOO_LIMIT_TIME_REAL:=2400}"
: "${ODOO_LIMIT_MEMORY_HARD:=536870912}"
: "${ODOO_LIMIT_MEMORY_SOFT:=402653184}"
: "${ODOO_LOG_LEVEL:=info}"

CONF=/var/lib/odoo/odoo.conf
SRC=/etc/odoo/odoo.conf

if [ -f "$SRC" ]; then
    # ---- LIVE bind-mounted config: use it, overlay ONLY secrets ----
    CONF="$CONF" SRC="$SRC" python3 - <<'PY'
import configparser, os
src, dst = os.environ["SRC"], os.environ["CONF"]
cp = configparser.ConfigParser()
cp.optionxform = str               # preserve key case
cp.read(src)
if "options" not in cp:
    cp.add_section("options")
o = cp["options"]
o["admin_passwd"] = os.environ.get("ODOO_ADMIN_PASSWD", "change-me-master")
o["db_host"] = os.environ.get("HOST", "db")
o["db_port"] = os.environ.get("DB_PORT", "5432")
o["db_user"] = os.environ.get("USER", "odoo")
o["db_password"] = os.environ.get("PASSWORD", "odoo")
o["db_template"] = os.environ.get("ODOO_DB_TEMPLATE", "template0")
with open(dst, "w") as fh:
    cp.write(fh)
PY
    echo "[entrypoint] config LIVE desde $SRC (secretos inyectados desde .env)"
else
    # ---- Fallback: render entirely from env -------------------------
    cat > "$CONF" <<EOF
[options]
admin_passwd = ${ODOO_ADMIN_PASSWD}
db_host = ${HOST}
db_port = ${DB_PORT}
db_user = ${USER}
db_password = ${PASSWORD}
db_template = ${ODOO_DB_TEMPLATE}
addons_path = /mnt/extra-addons,/opt/odoo/addons,/opt/odoo/odoo/addons
data_dir = /var/lib/odoo
list_db = ${ODOO_LIST_DB}
dbfilter = ${ODOO_DBFILTER}
proxy_mode = ${ODOO_PROXY_MODE}
workers = ${ODOO_WORKERS}
max_cron_threads = ${ODOO_MAX_CRON_THREADS}
limit_time_cpu = ${ODOO_LIMIT_TIME_CPU}
limit_time_real = ${ODOO_LIMIT_TIME_REAL}
limit_memory_hard = ${ODOO_LIMIT_MEMORY_HARD}
limit_memory_soft = ${ODOO_LIMIT_MEMORY_SOFT}
limit_request = 8192
log_level = ${ODOO_LOG_LEVEL}
log_handler = :INFO
logfile = /var/log/odoo/odoo.log
without_demo = False
unaccent = True
EOF
    echo "[entrypoint] config renderizada desde variables de entorno"
fi

chmod 640 "$CONF"
echo "[entrypoint] Odoo ${ODOO_REF:-18.0} | db=${ODOO_DB} | conf=$CONF"

exec python3 /opt/odoo/odoo-bin -c "$CONF" "$@"
