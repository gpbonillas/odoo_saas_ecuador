# syntax=docker/dockerfile:1
########################################################################
# Odoo 18 ECUADOR — BUILT FROM SOURCE (no prebuilt Odoo image)
# Source: https://github.com/odoo/odoo  @ branch ${ODOO_REF}
# Base:   debian:bookworm-slim (system libs only — Odoo code is ours)
# Usage:  docker compose build   (ODOO_REF in .env)
########################################################################
FROM debian:bookworm-slim AS source
ARG ODOO_REF=18.0
ARG ODOO_REPO=https://github.com/odoo/odoo

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/*

# --- fetch Odoo source directly from Odoo's official repository -----
RUN mkdir -p /opt/src \
 && curl -fsSL -o /opt/src/odoo.tar.gz "${ODOO_REPO}/archive/refs/heads/${ODOO_REF}.tar.gz" \
 && tar -xzf /opt/src/odoo.tar.gz -C /opt/src --strip-components=1 \
 && rm /opt/src/odoo.tar.gz \
 && test -f /opt/src/odoo-bin \
 && python3 -V || true

FROM debian:bookworm-slim AS runtime
ARG ODOO_REF=18.0
LABEL org.opencontainers.image.title="odoo-ecuador" \
      org.opencontainers.image.description="Odoo ${ODOO_REF} built from source + Ecuador localization" \
      org.opencontainers.image.source="https://github.com/odoo/odoo" \
      odoo.ref="${ODOO_REF}"

ENV ODOO_REF=${ODOO_REF} \
    ODOO_HOME=/opt/odoo \
    ODOO_USER=odoo \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

# ---- system dependencies (Debian repo) -----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-dev python3-pip python3-setuptools python3-wheel python3-venv \
      build-essential gcc \
      libxml2-dev libxslt1-dev zlib1g-dev libjpeg62-turbo-dev libpng-dev \
      libpq-dev libldap2-dev libsasl2-dev libffi-dev libssl-dev libblas-dev liblapack-dev \
      node-less node-clean-css \
      poppler-utils fonts-dejavu-core fonts-liberation fonts-noto-cjk \
      curl ca-certificates gnupg git xz-utils \
 && apt-get install -y --no-install-recommends wkhtmltopdf || echo "WARN: wkhtmltopdf unavailable in repo — PDF rendering via wkhtmltopdf disabled, use QWeb PDF engine fallback" \
 && rm -rf /var/lib/apt/lists/*

# ---- Odoo source (from stage 1) ------------------------------------
COPY --from=source /opt/src /opt/odoo

# ---- python dependencies (Odoo's own requirements.txt) -------------
RUN python3 -m pip install --no-cache-dir -r /opt/odoo/requirements.txt \
 || python3 -m pip install --no-cache-dir --break-system-packages -r /opt/odoo/requirements.txt

# Debian's pkg_resources (setuptools 59) parses dist-info dirs by filename and
# mismatches normalized names (zope_interface vs zope.interface); gevent's own
# entry point (gevent.plugins.monkey.will_patch_all) then dies with
# DistributionNotFound at boot. Provide dotted-name dist-info copies.
# NOTE: no heredocs here — a heredoc mixed with '\' continuations silently
# breaks the script; keep this as plain POSIX sh.
RUN SP=/usr/local/lib/python3.11/dist-packages \
 && for d in "$SP"/zope_interface-*.dist-info; do \
      [ -e "$d" ] || continue; \
      tgt=$(echo "$d" | sed 's/zope_interface/zope.interface/'); \
      [ -e "$tgt" ] || cp -r "$d" "$tgt"; \
    done \
 && for d in "$SP"/zope_event-*.dist-info; do \
      [ -e "$d" ] || continue; \
      tgt=$(echo "$d" | sed 's/zope_event/zope.event/'); \
      [ -e "$tgt" ] || cp -r "$d" "$tgt"; \
    done \
 && rm -rf /var/lib/odoo/.local/lib/python3.11/site-packages

RUN useradd --system --create-home --home-dir /var/lib/odoo --shell /usr/sbin/nologin odoo \
 && mkdir -p /var/lib/odoo /mnt/extra-addons /etc/odoo /var/log/odoo \
 && chown -R odoo:odoo /var/lib/odoo /mnt/extra-addons /var/log/odoo /opt/odoo

COPY --chown=odoo:odoo config/odoo.conf /etc/odoo/odoo.conf
COPY --chown=odoo:odoo config/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh && chmod 640 /etc/odoo/odoo.conf

WORKDIR /opt/odoo
USER odoo

EXPOSE 8069 8072
HEALTHCHECK --interval=30s --timeout=8s --start-period=240s --retries=10 \
  CMD python3 -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8069/web/health', timeout=6)" || exit 1

STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD []
