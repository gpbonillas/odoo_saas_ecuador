# official_shadows — neutralización de módulos oficiales de Odoo (CHG-2026-008)

## Problema

Odoo 18 community incluye sus PROPIOS módulos de localización Ecuador en
`/opt/odoo/addons`: `l10n_ec`, `l10n_ec_stock` y `l10n_ec_website_sale` —
**mismos nombres** que nuestra localización en `/mnt/extra-addons`.

El escaneo de módulos (`odoo.modules.module.get_module_path`) recorre
`odoo.addons.__path__` en orden de inserción del namespace, que NO siempre
coincide con el declarado en `--addons-path`. Cuando el directorio oficial
se encuentra primero:

1. `get_manifest('l10n_ec')` devuelve el manifest OFICIAL (depende de
   `base_iban` / `l10n_latam_base`, no instalados en esta BD),
2. el grafo descarta `l10n_ec` → cascada: `l10n_ec_stock` → `l10n_ec_agro`,
3. cargas "planas" (shell CLI, boots sin `-u`) quedan sin nuestra capa legal.

## Solución (order-independent)

Cada subdirectorio aquí está vacío (sin `__manifest__.py`) y se monta POR
ENCIMA del oficial correspondiente en `docker-compose.yml`. Como
`get_module_path()` busca archivos de manifest y no sólo el directorio,
el directorio vacío se salta y resuelve nuestro módulo en
`/mnt/extra-addons`. No toca la BD ni el código: sólo el filesystem del
contenedor.

**No borrar estos directorios ni los mounts del compose.**
