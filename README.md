# Test-Project

This repository provides a minimal Docker Compose setup for running an Odoo server with a PostgreSQL database.

## Prerequisites

- Docker 20.10+
- Docker Compose 1.29+ or the Docker CLI with Compose V2 support

## Getting Started

1. Create the persistent data directories (already present in the repo):
   - `odoo-web-data`
   - `odoo-db-data`
   - `addons`
   - `config`
2. Start the stack:
   ```bash
   docker compose up -d
   ```
3. Access Odoo at [http://localhost:8069](http://localhost:8069).

## Configuration

- Odoo configuration is stored in `config/odoo.conf`.
- Custom add-ons can be placed in the `addons/` directory.
- Data is persisted in `odoo-web-data/` and `odoo-db-data/`.

## Stopping the Stack

```bash
docker compose down
```

Add `-v` to also remove the persistent volumes if you want a clean slate.
