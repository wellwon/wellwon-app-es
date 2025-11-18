# =============================================================================
# File: app/security/ssl/ssl_manager.py
# Description: Enterprise-grade SSL/TLS certificate management for TradeCore
# =============================================================================

import ssl
import os
import logging
import hashlib
import json
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
import socket
import certifi
import aiohttp
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID, NameOID

log = logging.getLogger("tradecore.security.ssl")


class SSLVerificationMode(Enum):
    """SSL verification modes for different environments."""
    STRICT = "strict"  # Production: Full verification
    RELAXED = "relaxed"  # Staging: Verify but allow self-signed
    DEVELOPMENT = "dev"  # Development: Optional verification
    DISABLED = "disabled"  # Testing only: No verification


@dataclass
class SSLConfig:
    """SSL/TLS configuration with enterprise defaults."""
    verification_mode: SSLVerificationMode = SSLVerificationMode.STRICT

    # Certificate paths
    ca_bundle_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None

    # Certificate stores
    system_ca_bundle: bool = True
    certifi_ca_bundle: bool = True
    custom_ca_bundle: Optional[str] = None

    # SSL/TLS settings
    minimum_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    ciphers: Optional[str] = None  # Use default secure ciphers

    # Validation settings
    check_hostname: bool = True
    verify_cert_chain: bool = True
    verify_cert_dates: bool = True
    allowed_cert_hosts: List[str] = field(default_factory=list)

    # Certificate pinning
    pin_certificates: bool = False
    pinned_certificates: Dict[str, str] = field(default_factory=dict)  # hostname -> cert fingerprint

    # OCSP (Online Certificate Status Protocol)
    check_ocsp: bool = False
    ocsp_timeout: int = 5

    # Connection settings
    connection_timeout: int = 30
    read_timeout: int = 30

    # Retry settings for certificate issues
    max_cert_retries: int = 3
    cert_retry_delay: float = 1.0

    # Monitoring and alerting
    log_cert_details: bool = True
    alert_on_cert_expiry_days: int = 30

    @classmethod
    def for_environment(cls, env: str) -> "SSLConfig":
        """Factory method to create the appropriate config for environment."""
        env = env.lower()

        if env == "production":
            return cls(
                verification_mode=SSLVerificationMode.STRICT,
                check_ocsp=True,
                pin_certificates=True,
                alert_on_cert_expiry_days=30
            )
        elif env == "staging":
            return cls(
                verification_mode=SSLVerificationMode.RELAXED,
                check_ocsp=False,
                pin_certificates=False,
                alert_on_cert_expiry_days=14
            )
        elif env == "development":
            return cls(
                verification_mode=SSLVerificationMode.DEVELOPMENT,
                check_ocsp=False,
                pin_certificates=False,
                log_cert_details=True
            )
        else:  # testing
            return cls(
                verification_mode=SSLVerificationMode.DISABLED,
                check_hostname=False,
                verify_cert_chain=False
            )


class CertificateValidator:
    """Validates SSL/TLS certificates with comprehensive checks."""

    def __init__(self, config: SSLConfig):
        self.config = config
        self._cert_cache: Dict[str, Any] = {}

    def validate_certificate(self, cert: x509.Certificate, hostname: str) -> Dict[str, Any]:
        """Perform comprehensive certificate validation."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "details": {}
        }

        # Basic certificate checks
        try:
            # Check certificate dates
            if self.config.verify_cert_dates:
                now = datetime.now(timezone.utc)
                if cert.not_valid_before > now:
                    results["valid"] = False
                    results["errors"].append(f"Certificate not yet valid (starts {cert.not_valid_before})")
                elif cert.not_valid_after < now:
                    results["valid"] = False
                    results["errors"].append(f"Certificate expired on {cert.not_valid_after}")
                else:
                    days_until_expiry = (cert.not_valid_after - now).days
                    if days_until_expiry < self.config.alert_on_cert_expiry_days:
                        results["warnings"].append(f"Certificate expires in {days_until_expiry} days")

            # Check hostname
            if self.config.check_hostname:
                if not self._verify_hostname(cert, hostname):
                    results["valid"] = False
                    results["errors"].append(f"Certificate not valid for hostname {hostname}")

            # Check certificate purpose
            try:
                key_usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
                if not key_usage.digital_signature or not key_usage.key_agreement:
                    results["warnings"].append("Certificate may not be suitable for TLS")
            except x509.ExtensionNotFound:
                pass

            # Extract certificate details
            results["details"] = {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "serial_number": str(cert.serial_number),
                "not_before": cert.not_valid_before.isoformat(),
                "not_after": cert.not_valid_after.isoformat(),
                "signature_algorithm": cert.signature_algorithm_oid._name,
                "version": cert.version.name,
                "fingerprint_sha256": hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
            }

            # Certificate pinning check
            if self.config.pin_certificates and hostname in self.config.pinned_certificates:
                expected_fingerprint = self.config.pinned_certificates[hostname]
                actual_fingerprint = results["details"]["fingerprint_sha256"]
                if expected_fingerprint != actual_fingerprint:
                    results["valid"] = False
                    results["errors"].append(f"Certificate fingerprint mismatch for {hostname}")

        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Certificate validation error: {str(e)}")
            log.exception("Certificate validation failed")

        return results

    def _verify_hostname(self, cert: x509.Certificate, hostname: str) -> bool:
        """Verify that the certificate is valid for the given hostname."""
        try:
            # Check Subject Alternative Names
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_names = san_ext.value.get_values_for_type(x509.DNSName)

            for san_name in san_names:
                if self._match_hostname(san_name, hostname):
                    return True

            # Fallback to Common Name if no SAN
            for attribute in cert.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    if self._match_hostname(attribute.value, hostname):
                        return True

        except x509.ExtensionNotFound:
            # No SAN, check Common Name only
            for attribute in cert.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    if self._match_hostname(attribute.value, hostname):
                        return True

        return False

    def _match_hostname(self, cert_name: str, hostname: str) -> bool:
        """Match hostname with support for wildcards."""
        if cert_name == hostname:
            return True

        # Handle wildcard certificates
        if cert_name.startswith("*."):
            cert_domain = cert_name[2:]
            hostname_parts = hostname.split(".", 1)
            if len(hostname_parts) == 2 and hostname_parts[1] == cert_domain:
                return True

        return False


# noinspection GrazieInspection,SpellCheckingInspection
class SSLContextManager:
    """Manages SSL contexts with enterprise features."""

    def __init__(self, config: SSLConfig):
        self.config = config
        self.validator = CertificateValidator(config)
        self._context_cache: Dict[str, ssl.SSLContext] = {}
        self._initialize_ca_bundle()

    def _initialize_ca_bundle(self):
        """Initialize the CA bundle from multiple sources."""
        self.ca_bundle_path = None

        # Priority order for CA bundles
        if self.config.ca_bundle_path and os.path.exists(self.config.ca_bundle_path):
            self.ca_bundle_path = self.config.ca_bundle_path
            log.info(f"Using configured CA bundle: {self.ca_bundle_path}")
        elif self.config.certifi_ca_bundle:
            self.ca_bundle_path = certifi.where()
            log.info(f"Using certifi CA bundle: {self.ca_bundle_path}")
        elif self.config.system_ca_bundle:
            # Try to find system CA bundle
            system_paths = [
                "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
                "/etc/pki/tls/certs/ca-bundle.crt",  # RedHat/CentOS
                "/etc/ssl/ca-bundle.pem",  # OpenSUSE
                "/etc/ssl/cert.pem",  # macOS/OS X
                "/usr/local/share/certs/ca-root-nss.crt",  # FreeBSD
            ]

            for path in system_paths:
                if os.path.exists(path):
                    self.ca_bundle_path = path
                    log.info(f"Using system CA bundle: {self.ca_bundle_path}")
                    break

        if not self.ca_bundle_path:
            log.warning("No CA bundle found, using system default")

    def create_ssl_context(self, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH) -> ssl.SSLContext:
        """Create a properly configured SSL context."""
        # Check cache
        cache_key = f"{purpose}_{self.config.verification_mode}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        # Create new context
        if self.config.verification_mode == SSLVerificationMode.DISABLED:
            # Testing only - no verification
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            log.warning("SSL verification is DISABLED - use only for testing!")
        else:
            # Create secure context
            context = ssl.create_default_context(
                purpose=purpose,
                cafile=self.ca_bundle_path
            )

            # Set minimum TLS version
            context.minimum_version = self.config.minimum_tls_version

            # Set verification mode
            if self.config.verification_mode == SSLVerificationMode.STRICT:
                context.verify_mode = ssl.CERT_REQUIRED
                context.check_hostname = self.config.check_hostname
            elif self.config.verification_mode == SSLVerificationMode.RELAXED:
                context.verify_mode = ssl.CERT_REQUIRED
                context.check_hostname = self.config.check_hostname
                # Allow self-signed certificates in relaxed mode
                context.check_hostname = False
            elif self.config.verification_mode == SSLVerificationMode.DEVELOPMENT:
                context.verify_mode = ssl.CERT_OPTIONAL
                context.check_hostname = False

            # Load custom CA bundle if provided
            if self.config.custom_ca_bundle and os.path.exists(self.config.custom_ca_bundle):
                context.load_verify_locations(cafile=self.config.custom_ca_bundle)
                log.info(f"Loaded custom CA bundle: {self.config.custom_ca_bundle}")

            # Load client certificate if provided
            if self.config.client_cert_path and self.config.client_key_path:
                if os.path.exists(self.config.client_cert_path) and os.path.exists(self.config.client_key_path):
                    context.load_cert_chain(
                        certfile=self.config.client_cert_path,
                        keyfile=self.config.client_key_path
                    )
                    log.info("Loaded client certificate for mutual TLS")

            # Set custom ciphers if provided
            if self.config.ciphers:
                context.set_ciphers(self.config.ciphers)
            else:
                # Use secure cipher suite
                context.set_ciphers(
                    "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:"
                    "ECDH+AESGCM:DH+AESGCM:ECDH+AES:DH+AES:"
                    "RSA+AESGCM:RSA+AES:"
                    "!aNULL:!eNULL:!MD5:!DSS:!RC4:!3DES"
                )

            # Disable insecure protocols
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.options |= ssl.OP_NO_TLSv1
            context.options |= ssl.OP_NO_TLSv1_1

            # Enable hostname checking
            if self.config.check_hostname:
                context.check_hostname = True

            # Set up certificate verification callback if needed
            if self.config.pin_certificates or self.config.log_cert_details:
                context.verify_mode = ssl.CERT_REQUIRED
                # Note: For advanced verification, we'll check after connection

        # Cache the context
        self._context_cache[cache_key] = context

        return context

    def create_websocket_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context optimized for WebSocket connections.

        WebSocket connections need simpler SSL settings than HTTPS.
        Too strict cipher suites can cause authentication timeouts.
        """
        # Use default SSL context for WebSocket (like standalone clients do)
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        # Minimum TLS 1.2 is fine
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Use default ciphers (don't override with custom strict list)
        # This is key - custom cipher list breaks Alpaca WebSocket!

        # Basic security: disable old protocols
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1

        # For development/testing, be more permissive
        if self.config.verification_mode in (SSLVerificationMode.DEVELOPMENT, SSLVerificationMode.DISABLED):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        log.info("Created WebSocket SSL context (simplified for compatibility)")
        return context

    def create_connector(self, **kwargs) -> aiohttp.TCPConnector:
        """
        Create an aiohttp connector with SSL context.

        Args:
            **kwargs: Additional arguments for TCPConnector

        Returns:
            Configured TCPConnector with SSL
        """
        # Start with SSL context
        connector_kwargs = {
            'ssl': self.create_ssl_context(),
        }

        # Add user-provided kwargs
        connector_kwargs.update(kwargs)

        # Handle force_close/keepalive_timeout conflict
        if connector_kwargs.get('force_close', False):
            # Remove incompatible parameters when force_close is True
            incompatible_params = ['keepalive_timeout']
            for param in incompatible_params:
                if param in connector_kwargs:
                    log.debug(f"Removing {param} due to force_close=True")
                    connector_kwargs.pop(param)

        try:
            return aiohttp.TCPConnector(**connector_kwargs)
        except Exception as e:
            log.error(f"Failed to create connector: {e}")
            # Fallback to basic connector
            return aiohttp.TCPConnector(ssl=self.create_ssl_context())

    def log_certificate_info(self, hostname: str, cert_der: bytes):
        """Log certificate information for monitoring."""
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            validation_result = self.validator.validate_certificate(cert, hostname)

            log_data = {
                "hostname": hostname,
                "subject": validation_result["details"]["subject"],
                "issuer": validation_result["details"]["issuer"],
                "not_after": validation_result["details"]["not_after"],
                "fingerprint": validation_result["details"]["fingerprint_sha256"],
                "valid": validation_result["valid"],
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"]
            }

            if validation_result["valid"]:
                if validation_result["warnings"]:
                    log.warning(f"Certificate validation warnings for {hostname}: {json.dumps(log_data)}")
                else:
                    log.info(f"Certificate validated for {hostname}: {json.dumps(log_data)}")
            else:
                log.error(f"Certificate validation failed for {hostname}: {json.dumps(log_data)}")

        except Exception as e:
            log.error(f"Failed to log certificate info for {hostname}: {e}")


# Singleton instance for the application
_ssl_manager: Optional[SSLContextManager] = None


def get_ssl_manager(config: Optional[SSLConfig] = None) -> SSLContextManager:
    """Get or create the global SSL manager."""
    global _ssl_manager

    if _ssl_manager is None:
        if config is None:
            # Create default config based on environment
            env = os.environ.get("ENVIRONMENT", "production")
            config = SSLConfig.for_environment(env)

        _ssl_manager = SSLContextManager(config)

    return _ssl_manager


# Convenience functions
def create_secure_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create a secure aiohttp connector with default settings."""
    manager = get_ssl_manager()
    return manager.create_connector(**kwargs)


def create_ssl_context(purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH) -> ssl.SSLContext:
    """Create a secure SSL context with default settings."""
    manager = get_ssl_manager()
    return manager.create_ssl_context(purpose)