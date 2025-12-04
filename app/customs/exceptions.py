# =============================================================================
# File: app/customs/exceptions.py
# Description: Exception hierarchy for Customs domain
# =============================================================================


class CustomsError(Exception):
    """Base exception for all customs domain errors."""
    pass


# Declaration Errors
class DeclarationNotFoundError(CustomsError):
    """Raised when a customs declaration is not found."""
    pass


class InvalidDeclarationStatusError(CustomsError):
    """Raised when an operation is invalid for the current declaration status."""
    pass


class DeclarationValidationError(CustomsError):
    """Raised when declaration data fails validation."""
    pass


class DeclarationAlreadySubmittedError(CustomsError):
    """Raised when trying to modify an already submitted declaration."""
    pass


class DeclarationNotSubmittedError(CustomsError):
    """Raised when an operation requires a submitted declaration."""
    pass


# Organization Errors
class OrganizationNotFoundError(CustomsError):
    """Raised when an organization is not found."""
    pass


class OrganizationValidationError(CustomsError):
    """Raised when organization data fails validation."""
    pass


class InvalidINNError(CustomsError):
    """Raised when INN format or checksum is invalid."""
    pass


class InvalidKPPError(CustomsError):
    """Raised when KPP format is invalid."""
    pass


class InvalidOGRNError(CustomsError):
    """Raised when OGRN format or checksum is invalid."""
    pass


# Kontur Integration Errors
class KonturSyncError(CustomsError):
    """Raised when synchronization with Kontur fails."""
    pass


class KonturSubmissionError(CustomsError):
    """Raised when submission to Kontur fails."""
    pass


class KonturDocflowNotFoundError(CustomsError):
    """Raised when Kontur docflow is not found."""
    pass


class KonturConnectionError(CustomsError):
    """Raised when connection to Kontur API fails."""
    pass


# Document Errors
class DocumentNotFoundError(CustomsError):
    """Raised when a document is not found."""
    pass


class DocumentUploadError(CustomsError):
    """Raised when document upload fails."""
    pass


class InvalidDocumentFormatError(CustomsError):
    """Raised when document format is invalid."""
    pass


# Form Errors
class FormDataValidationError(CustomsError):
    """Raised when form data fails validation."""
    pass


class FormImportError(CustomsError):
    """Raised when form data import fails."""
    pass


class FormExportError(CustomsError):
    """Raised when form data export fails."""
    pass


# DTS Errors
class DtsCalculationError(CustomsError):
    """Raised when DTS calculation fails."""
    pass


class DtsValidationError(CustomsError):
    """Raised when DTS data fails validation."""
    pass


# Authorization Errors
class UnauthorizedAccessError(CustomsError):
    """Raised when user doesn't have access to a resource."""
    pass


class DeclarationAccessDeniedError(UnauthorizedAccessError):
    """Raised when user doesn't have access to the declaration."""
    pass


class OrganizationAccessDeniedError(UnauthorizedAccessError):
    """Raised when user doesn't have access to the organization."""
    pass


# =============================================================================
# EOF
# =============================================================================
