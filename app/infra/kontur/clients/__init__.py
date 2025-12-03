# NEVER add exports to __init__.py - leave them EMPTY
# Use direct imports instead:
# from app.infra.kontur.clients.base_client import BaseClient  # CORRECT
# from app.infra.kontur.clients import BaseClient  # WRONG - don't do this
