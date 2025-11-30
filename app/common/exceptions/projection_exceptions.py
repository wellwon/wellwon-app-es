# =============================================================================
# File: app/common/exceptions/projection_exceptions.py
# Description: Exceptions for projection processing
# =============================================================================


class RetriableProjectionError(Exception):
    """
    Raised when a projection fails due to a dependency not being ready.

    Examples:
    - FK violation because parent entity hasn't been projected yet
    - Required lookup data not available
    - Transient database connectivity issue

    When raised, the event processor will queue the event for retry
    instead of sending it to the DLQ.
    """
    pass
