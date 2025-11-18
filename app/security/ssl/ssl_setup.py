# =============================================================================
# File: app/security/ssl/ssl_setup.py
# Description: SSL/TLS setup for application startup
# =============================================================================

import os
import logging

from app.security.ssl.ssl_manager import SSLConfig, get_ssl_manager
from app.security.ssl.certificate_monitor import get_certificate_monitor, CertificateMonitor
from app.security.ssl.monitoring import get_metrics_collector
from app.security.ssl.alerting import get_alert_manager

log = logging.getLogger("wellwon.security.ssl_setup")


async def initialize_ssl_security(enable_monitoring: bool = True):
    """
    Initialize enterprise SSL/TLS security for the application.

    Args:
        enable_monitoring: Whether to enable certificate monitoring (default: True)

    Returns:
        SSLContextManager: The initialized SSL manager
    """
    # 1. Determine environment
    environment = os.environ.get("ENVIRONMENT", "production")
    log.info(f"Initializing SSL security for environment: {environment}")

    # 2. Create SSL configuration
    ssl_config = SSLConfig.for_environment(environment)

    # 3. Apply any environment variable overrides
    if os.environ.get("SSL_VERIFY_MODE"):
        ssl_config.verification_mode = os.environ["SSL_VERIFY_MODE"]

    if os.environ.get("SSL_CA_BUNDLE"):
        ssl_config.ca_bundle_path = os.environ["SSL_CA_BUNDLE"]

    if os.environ.get("SSL_CLIENT_CERT"):
        ssl_config.client_cert_path = os.environ["SSL_CLIENT_CERT"]

    if os.environ.get("SSL_CLIENT_KEY"):
        ssl_config.client_key_path = os.environ["SSL_CLIENT_KEY"]

    # 4. Initialize SSL manager
    ssl_manager = get_ssl_manager(ssl_config)
    log.info("SSL manager initialized")

    # 5. Start certificate monitoring if enabled and in production/staging
    if enable_monitoring and environment in ["production", "staging"]:
        metrics = get_metrics_collector()
        alerts = get_alert_manager()

        monitor = get_certificate_monitor(
            ssl_config=ssl_config,
            metrics_collector=metrics,
            alert_manager=alerts
        )

        # Start monitoring with the appropriate interval
        check_interval = 3600 if environment == "production" else 7200
        await monitor.start_monitoring(check_interval=check_interval)
        log.info(f"Certificate monitoring started with {check_interval}s interval")
    elif not enable_monitoring:
        log.info("Certificate monitoring disabled")

    # 6. Log SSL configuration summary
    log.info(f"SSL Configuration Summary:")
    log.info(f"  - Verification Mode: {ssl_config.verification_mode.value}")
    log.info(f"  - Minimum TLS Version: {ssl_config.minimum_tls_version.name}")
    log.info(f"  - Certificate Pinning: {'Enabled' if ssl_config.pin_certificates else 'Disabled'}")
    log.info(f"  - OCSP Checking: {'Enabled' if ssl_config.check_ocsp else 'Disabled'}")
    log.info(f"  - CA Bundle: {ssl_manager.ca_bundle_path}")

    return ssl_manager


async def shutdown_ssl_security():
    """Shutdown SSL security components gracefully."""
    try:
        # Stop certificate monitoring
        monitor = get_certificate_monitor()
        if monitor:
            await monitor.stop_monitoring()
            log.info("Certificate monitoring stopped")
    except Exception as e:
        log.error(f"Error shutting down SSL security: {e}")


# Add this to your main application startup
async def setup_application():
    """Main application setup including SSL."""
    # ... other setup code ...

    # Initialize SSL security
    # Can disable monitoring for testing or development
    await initialize_ssl_security(enable_monitoring=True)

    # ... rest of setup ...


# Convenience function for checking certificates without full monitoring
async def check_broker_certificates():
    """Simple certificate check for broker endpoints."""
    ssl_config = SSLConfig.for_environment(os.environ.get("ENVIRONMENT", "production"))
    monitor = CertificateMonitor(ssl_config)

    # Check critical broker endpoints
    critical_endpoints = [
        ("api.alpaca.markets", 443),
        ("paper-api.alpaca.markets", 443),
        ("data.alpaca.markets", 443),
    ]

    results = {}
    for hostname, port in critical_endpoints:
        try:
            cert_info = await monitor.check_certificate(hostname, port)
            results[f"{hostname}:{port}"] = {
                "status": cert_info.status.value,
                "days_until_expiry": cert_info.days_until_expiry,
                "issuer": cert_info.issuer,
                "valid": cert_info.status.value in ["healthy", "warning"]
            }
            log.info(f"Certificate check for {hostname}:{port}: {cert_info.status.value}")
        except Exception as e:
            log.error(f"Failed to check certificate for {hostname}:{port}: {e}")
            results[f"{hostname}:{port}"] = {
                "status": "error",
                "error": str(e),
                "valid": False
            }

    return results


# Add this to your main application shutdown
async def shutdown_application():
    """Main application shutdown including SSL."""
    # ... other shutdown code ...

    # Shutdown SSL security
    await shutdown_ssl_security()

    # ... rest of shutdown ...