# =============================================================================
# File: app/security/ssl/certificate_monitor.py
# Description: Certificate monitoring and alerting service
# =============================================================================

import asyncio
import ssl

import ssl_test
import socket
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from app.security.ssl.ssl_manager import SSLConfig, CertificateValidator

# Optional imports for monitoring and alerting
try:
    from app.security.ssl.monitoring import MetricsCollector
    from app.security.ssl.alerting import AlertManager
except ImportError:
    log = logging.getLogger("wellwon.security.cert_monitor")
    log.warning("Monitoring and alerting modules not available - metrics and alerts will be disabled")
    MetricsCollector = None
    AlertManager = None

log = logging.getLogger("wellwon.security.cert_monitor")


class CertificateStatus(Enum):
    """Certificate health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass
class CertificateInfo:
    """Certificate information and health status."""
    hostname: str
    port: int
    status: CertificateStatus
    issuer: str
    subject: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    days_until_expiry: int
    fingerprint_sha256: str
    san_names: List[str]
    signature_algorithm: str
    key_size: int
    is_self_signed: bool
    chain_length: int
    ocsp_status: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    last_checked: datetime = None


# noinspection GrazieInspection,SpellCheckingInspection
class CertificateMonitor:
    """Monitors SSL/TLS certificates and sends alerts."""

    def __init__(
            self,
            ssl_config: SSLConfig,
            metrics_collector: Optional['MetricsCollector'] = None,
            alert_manager: Optional['AlertManager'] = None
    ):
        self.ssl_config = ssl_config
        self.validator = CertificateValidator(ssl_config)
        self.metrics = metrics_collector
        self.alerts = alert_manager

        # Monitoring state
        self._monitored_hosts: Dict[str, CertificateInfo] = {}
        self._check_interval = 3600  # 1 hour default
        self._monitoring_task: Optional[asyncio.Task] = None

        # Broker endpoints to monitor
        self.broker_endpoints = {
            "alpaca": [
                ("api.alpaca.markets", 443),
                ("paper-api.alpaca.markets", 443),
                ("data.alpaca.markets", 443),
                ("stream.data.alpaca.markets", 443),
            ],
            "tradestation": [
                ("api.tradestation.com", 443),
                ("sim-api.tradestation.com", 443),
            ],
            "tradier": [
                ("api.tradier.com", 443),
                ("sandbox.tradier.com", 443),
            ],
            "interactive_brokers": [
                ("api.ibkr.com", 443),
                ("gateway.ibkr.com", 443),
            ],
        }

    async def start_monitoring(self, check_interval: int = 3600):
        """Start the certificate monitoring service."""
        self._check_interval = check_interval

        if self._monitoring_task and not self._monitoring_task.done():
            log.warning("Certificate monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        log.info(f"Started certificate monitoring with {check_interval}s interval")

    async def stop_monitoring(self):
        """Stop the certificate monitoring service."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        log.info("Stopped certificate monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while True:
            try:
                # Check all configured endpoints
                for broker, endpoints in self.broker_endpoints.items():
                    for hostname, port in endpoints:
                        try:
                            cert_info = await self.check_certificate(hostname, port)
                            await self._process_certificate_status(cert_info)
                        except Exception as e:
                            log.error(f"Error checking {hostname}:{port} - {e}")
                            await self._handle_check_error(hostname, port, e)

                # Check for any custom monitored hosts
                custom_hosts = set(self._monitored_hosts.keys()) - {
                    f"{h}:{p}" for endpoints in self.broker_endpoints.values()
                    for h, p in endpoints
                }

                for host_key in custom_hosts:
                    hostname, port = host_key.split(":")
                    try:
                        cert_info = await self.check_certificate(hostname, int(port))
                        await self._process_certificate_status(cert_info)
                    except Exception as e:
                        log.error(f"Error checking {hostname}:{port} - {e}")
                        await self._handle_check_error(hostname, int(port), e)

                # Wait for next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retrying

    async def check_certificate(self, hostname: str, port: int = 443) -> CertificateInfo:
        """Check a certificate and return its status."""
        log.debug(f"Checking certificate for {hostname}:{port}")

        try:
            # Create SSL context for checking
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_REQUIRED

            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    # Get certificate chain
                    der_cert = ssock.getpeercert(binary_form=True)
                    cert = x509.load_der_x509_certificate(der_cert, default_backend())

                    # Get full certificate chain
                    cert_chain = ssock.getpeercert_chain()
                    chain_length = len(cert_chain) if cert_chain else 1

                    # Validate certificate
                    validation_result = self.validator.validate_certificate(cert, hostname)

                    # Calculate days until expiry
                    now = datetime.now(timezone.utc)
                    days_until_expiry = (cert.not_valid_after - now).days

                    # Determine status
                    if not validation_result["valid"]:
                        status = CertificateStatus.INVALID
                    elif days_until_expiry < 0:
                        status = CertificateStatus.EXPIRED
                    elif days_until_expiry <= 7:
                        status = CertificateStatus.CRITICAL
                    elif days_until_expiry <= 30:
                        status = CertificateStatus.WARNING
                    else:
                        status = CertificateStatus.HEALTHY

                    # Extract SAN names
                    san_names = []
                    try:
                        san_ext = cert.extensions.get_extension_for_oid(
                            x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                        )
                        san_names = [n.value for n in san_ext.value]
                    except x509.ExtensionNotFound:
                        pass

                    # Check if self-signed
                    is_self_signed = cert.issuer == cert.subject

                    # Get key size
                    public_key = cert.public_key()
                    if hasattr(public_key, 'key_size'):
                        key_size = public_key.key_size
                    else:
                        key_size = 0

                    # Create certificate info
                    cert_info = CertificateInfo(
                        hostname=hostname,
                        port=port,
                        status=status,
                        issuer=cert.issuer.rfc4514_string(),
                        subject=cert.subject.rfc4514_string(),
                        serial_number=str(cert.serial_number),
                        not_before=cert.not_valid_before,
                        not_after=cert.not_valid_after,
                        days_until_expiry=days_until_expiry,
                        fingerprint_sha256=validation_result["details"]["fingerprint_sha256"],
                        san_names=san_names,
                        signature_algorithm=cert.signature_algorithm_oid._name,
                        key_size=key_size,
                        is_self_signed=is_self_signed,
                        chain_length=chain_length,
                        errors=validation_result["errors"],
                        warnings=validation_result["warnings"],
                        last_checked=datetime.now(timezone.utc)
                    )

                    # Check OCSP if enabled
                    if self.ssl_config.check_ocsp:
                        cert_info.ocsp_status = await self._check_ocsp(cert)

                    # Store in monitoring cache
                    self._monitored_hosts[f"{hostname}:{port}"] = cert_info

                    # Log certificate details if enabled
                    if self.ssl_config.log_cert_details:
                        self._log_certificate_details(cert_info)

                    return cert_info

        except socket.timeout:
            raise ConnectionError(f"Timeout connecting to {hostname}:{port}")
        except socket.gaierror as e:
            raise ConnectionError(f"DNS resolution failed for {hostname}: {e}")
        except ssl.SSLError as e:
            raise ConnectionError(f"SSL error for {hostname}:{port}: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to check certificate for {hostname}:{port}: {e}")

    async def _check_ocsp(self, cert: x509.Certificate) -> str:
        """Check OCSP status for a certificate."""
        # This is a placeholder - real OCSP checking requires additional implementation
        # involving extracting OCSP URL from certificate, making OCSP request, etc.
        return "not_checked"

    async def _process_certificate_status(self, cert_info: CertificateInfo):
        """Process certificate status and send alerts if needed."""
        host_key = f"{cert_info.hostname}:{cert_info.port}"

        # Update metrics if available
        if self.metrics and MetricsCollector:
            labels = {
                "hostname": cert_info.hostname,
                "port": str(cert_info.port),
                "issuer": cert_info.issuer,
                "status": cert_info.status.value
            }

            self.metrics.gauge(
                "ssl_certificate_expiry_days",
                cert_info.days_until_expiry,
                labels
            )

            self.metrics.gauge(
                "ssl_certificate_valid",
                1 if cert_info.status == CertificateStatus.HEALTHY else 0,
                labels
            )

        # Check if we need to send alerts
        previous_info = self._monitored_hosts.get(host_key)

        # Send alert if status changed or if critical/expired
        if (not previous_info or
                previous_info.status != cert_info.status or
                cert_info.status in [CertificateStatus.CRITICAL, CertificateStatus.EXPIRED]):
            await self._send_certificate_alert(cert_info)

    async def _send_certificate_alert(self, cert_info: CertificateInfo):
        """Send alert for certificate issues."""
        if not self.alerts or not AlertManager:
            # Just log if no alert manager available
            if cert_info.status in [CertificateStatus.CRITICAL, CertificateStatus.EXPIRED, CertificateStatus.INVALID]:
                log.error(f"Certificate alert for {cert_info.hostname}:{cert_info.port} - Status: {cert_info.status.value}")
            elif cert_info.status == CertificateStatus.WARNING:
                log.warning(f"Certificate warning for {cert_info.hostname}:{cert_info.port} - Status: {cert_info.status.value}")
            return

        severity = "info"
        if cert_info.status == CertificateStatus.WARNING:
            severity = "warning"
        elif cert_info.status == CertificateStatus.CRITICAL:
            severity = "critical"
        elif cert_info.status in [CertificateStatus.EXPIRED, CertificateStatus.INVALID]:
            severity = "critical"

        message = f"SSL Certificate Alert for {cert_info.hostname}:{cert_info.port}"

        details = {
            "hostname": cert_info.hostname,
            "port": cert_info.port,
            "status": cert_info.status.value,
            "days_until_expiry": cert_info.days_until_expiry,
            "issuer": cert_info.issuer,
            "subject": cert_info.subject,
            "expires": cert_info.not_after.isoformat(),
            "errors": cert_info.errors,
            "warnings": cert_info.warnings,
            "fingerprint": cert_info.fingerprint_sha256
        }

        await self.alerts.send_alert(
            severity=severity,
            message=message,
            details=details,
            alert_type="ssl_certificate"
        )

    async def _handle_check_error(self, hostname: str, port: int, error: Exception):
        """Handle errors during certificate checking."""
        host_key = f"{hostname}:{port}"

        # Create error certificate info
        cert_info = CertificateInfo(
            hostname=hostname,
            port=port,
            status=CertificateStatus.UNKNOWN,
            issuer="Unknown",
            subject="Unknown",
            serial_number="Unknown",
            not_before=datetime.min,
            not_after=datetime.min,
            days_until_expiry=-1,
            fingerprint_sha256="Unknown",
            san_names=[],
            signature_algorithm="Unknown",
            key_size=0,
            is_self_signed=False,
            chain_length=0,
            errors=[str(error)],
            last_checked=datetime.now(timezone.utc)
        )

        self._monitored_hosts[host_key] = cert_info

        # Send alert or log
        if self.alerts and AlertManager:
            await self.alerts.send_alert(
                severity="critical",
                message=f"Failed to check SSL certificate for {hostname}:{port}",
                details={
                    "hostname": hostname,
                    "port": port,
                    "error": str(error),
                    "error_type": type(error).__name__
                },
                alert_type="ssl_certificate_error"
            )
        else:
            log.error(f"Failed to check SSL certificate for {hostname}:{port}: {error}")

    def _log_certificate_details(self, cert_info: CertificateInfo):
        """Log certificate details for audit/debugging."""
        log_data = {
            "hostname": cert_info.hostname,
            "port": cert_info.port,
            "status": cert_info.status.value,
            "issuer": cert_info.issuer,
            "subject": cert_info.subject,
            "serial": cert_info.serial_number,
            "not_before": cert_info.not_before.isoformat(),
            "not_after": cert_info.not_after.isoformat(),
            "days_until_expiry": cert_info.days_until_expiry,
            "fingerprint": cert_info.fingerprint_sha256,
            "san_names": cert_info.san_names,
            "signature_algorithm": cert_info.signature_algorithm,
            "key_size": cert_info.key_size,
            "is_self_signed": cert_info.is_self_signed,
            "chain_length": cert_info.chain_length,
            "ocsp_status": cert_info.ocsp_status,
            "errors": cert_info.errors,
            "warnings": cert_info.warnings
        }

        log.info(f"Certificate check completed: {log_data}")

    def get_certificate_status(self, hostname: str, port: int = 443) -> Optional[CertificateInfo]:
        """Get the current status of a monitored certificate."""
        return self._monitored_hosts.get(f"{hostname}:{port}")

    def get_all_certificate_statuses(self) -> Dict[str, CertificateInfo]:
        """Get status of all monitored certificates."""
        return self._monitored_hosts.copy()

    async def add_custom_host(self, hostname: str, port: int = 443):
        """Add a custom host to monitor."""
        cert_info = await self.check_certificate(hostname, port)
        await self._process_certificate_status(cert_info)
        log.info(f"Added custom host for monitoring: {hostname}:{port}")

    def remove_custom_host(self, hostname: str, port: int = 443):
        """Remove a custom host from monitoring."""
        host_key = f"{hostname}:{port}"
        if host_key in self._monitored_hosts:
            del self._monitored_hosts[host_key]
            log.info(f"Removed custom host from monitoring: {hostname}:{port}")


# Create a global certificate monitor instance
_certificate_monitor: Optional[CertificateMonitor] = None


def get_certificate_monitor(
        ssl_config: Optional[SSLConfig] = None,
        metrics_collector: Optional['MetricsCollector'] = None,
        alert_manager: Optional['AlertManager'] = None
) -> CertificateMonitor:
    """Get or create the global certificate monitor."""
    global _certificate_monitor

    if _certificate_monitor is None:
        if ssl_config is None:
            from app.security.ssl.ssl_manager import get_ssl_manager
            ssl_config = get_ssl_manager().config

        _certificate_monitor = CertificateMonitor(
            ssl_config=ssl_config,
            metrics_collector=metrics_collector,
            alert_manager=alert_manager
        )

    return _certificate_monitor