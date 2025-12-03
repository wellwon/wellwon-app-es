# NEVER add exports to __init__.py - leave them EMPTY
# Use direct imports instead:
# from app.infra.kontur.adapter import get_kontur_adapter  # CORRECT
# from app.infra.kontur import get_kontur_adapter  # WRONG - don't do this
