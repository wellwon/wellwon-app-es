# =============================================================================
# File: app/declarant/schema_transform_service.py
# Description: Service for transforming Kontur JSON schemas into form definitions
# =============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.infra.persistence import pg_client
from app.declarant.kontur_client import get_kontur_client, KonturClientError

log = logging.getLogger("wellwon.declarant.schema_transform")


# =============================================================================
# Field Types
# =============================================================================

class FieldType(str, Enum):
    """Supported field types for form rendering"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    CHECKBOX = "checkbox"
    TEXTAREA = "textarea"
    OBJECT = "object"      # Nested object
    ARRAY = "array"        # Repeatable group


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FieldOption:
    """Option for select fields"""
    value: str
    label: str


@dataclass
class FieldDefinition:
    """Processed field definition for form rendering"""
    path: str                                   # Full path: "Contract.ContractDate"
    name: str                                   # Field name: "ContractDate"
    field_type: FieldType = FieldType.TEXT
    required: bool = False
    label_ru: str = ""
    hint_ru: str = ""
    placeholder_ru: str = ""

    # Type-specific options
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    options: List[FieldOption] = field(default_factory=list)
    pattern: Optional[str] = None

    # Nested fields (for OBJECT/ARRAY types)
    children: List['FieldDefinition'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        result = {
            "path": self.path,
            "name": self.name,
            "field_type": self.field_type.value,
            "required": self.required,
            "label_ru": self.label_ru,
            "hint_ru": self.hint_ru,
            "placeholder_ru": self.placeholder_ru,
        }
        if self.min_value is not None:
            result["min_value"] = self.min_value
        if self.max_value is not None:
            result["max_value"] = self.max_value
        if self.max_length is not None:
            result["max_length"] = self.max_length
        if self.options:
            result["options"] = [{"value": o.value, "label": o.label} for o in self.options]
        if self.pattern:
            result["pattern"] = self.pattern
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


@dataclass
class FormSection:
    """Section definition for UI grouping"""
    section_key: str
    title_ru: str
    description_ru: str = ""
    icon: str = "FileText"
    sort_order: int = 0
    field_paths: List[str] = field(default_factory=list)
    fields_config: List[Dict[str, Any]] = field(default_factory=list)  # Full field configurations from Form Builder
    columns: int = 2
    collapsible: bool = False
    default_expanded: bool = True


@dataclass
class FormDefinition:
    """Complete form definition for a document type"""
    document_mode_id: str
    gf_code: str
    type_name: str
    fields: List[FieldDefinition]
    sections: List[FormSection] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    kontur_schema_json: Dict[str, Any] = field(default_factory=dict)
    kontur_schema_hash: str = ""
    version: int = 1
    id: Optional[str] = None
    form_width: int = 100  # Ширина формы в % (70-130)


# =============================================================================
# Section Mapping Configuration
# =============================================================================

# Maps document_mode_id to custom section configuration
# This allows grouping fields by UI logic rather than JSON structure
SECTION_MAPPING = {
    "1002004E": {
        "sections": [
            {
                "key": "contract_terms",
                "title_ru": "Условия контракта",
                "icon": "FileText",
                "field_paths": [
                    "ContractTerms.DealSign",
                    "ContractTerms.ContractTime",
                    "ContractTerms.AdditionalContractTime",
                    "ContractRegistration.ContractPlace",
                    "ContractTerms.Amount",
                    "ContractTerms.CurrencyCode",
                    "ContractTerms.LastDate",
                    "ContractTerms.PaymentPeriod",
                    "ContractTerms.PaymentCurrencyCode",
                    "ContractTerms.DiscountPercentage",
                    "ContractTerms.Discount",
                    "ContractTerms.PaymentModeCode",
                    "ContractTerms.DueDateCode",
                    "ContractTerms.PrepaySign",
                    "ContractTerms.StockCategorySign",
                    "ContractTerms.BuyerLimitationSign",
                    "ContractTerms.InsuranceSign",
                    "SupplementationSign",
                    "ContractTerms.ChangeContract",
                    "ContractDeliveryTerms",
                    "ContractSignedPerson",
                ]
            },
            {
                "key": "foreign_person",
                "title_ru": "Реквизиты иностранной стороны",
                "icon": "Globe",
                "field_paths": ["ForeignPerson"]
            },
            {
                "key": "russian_person",
                "title_ru": "Реквизиты российского контрактодержателя",
                "icon": "Flag",
                "field_paths": ["RussianPerson"]
            },
            {
                "key": "contract_text",
                "title_ru": "Текст контракта",
                "icon": "FileText",
                "field_paths": [
                    "ContractTerms.ContractText",
                    "ContractTerms.ContractSubject",
                    "ContractTerms.ExchangeClause",
                    "ContractTerms.OtherTerms"
                ]
            },
            {
                "key": "specification",
                "title_ru": "Спецификация к контракту",
                "icon": "Package",
                "field_paths": ["ContractSpecification"]
            }
        ]
    }
}


# =============================================================================
# Type Detection Patterns
# =============================================================================

# Patterns for detecting field types by name
DATE_PATTERNS = [
    re.compile(r'Date$', re.IGNORECASE),
    re.compile(r'DateTime$', re.IGNORECASE),
    re.compile(r'^date', re.IGNORECASE),
    re.compile(r'Created', re.IGNORECASE),
    re.compile(r'Updated', re.IGNORECASE),
    re.compile(r'RegisterDate', re.IGNORECASE),
    re.compile(r'ValidityDate', re.IGNORECASE),
    re.compile(r'ExpiryDate', re.IGNORECASE),
]

BOOLEAN_PATTERNS = [
    re.compile(r'Flag$', re.IGNORECASE),
    re.compile(r'Indicator$', re.IGNORECASE),
    re.compile(r'^is[A-Z]'),
    re.compile(r'^has[A-Z]'),
    re.compile(r'Equal', re.IGNORECASE),
    re.compile(r'Active$', re.IGNORECASE),
    re.compile(r'Enabled$', re.IGNORECASE),
]

NUMBER_PATTERNS = [
    re.compile(r'Code$', re.IGNORECASE),
    re.compile(r'Number$', re.IGNORECASE),
    re.compile(r'Count$', re.IGNORECASE),
    re.compile(r'Quantity$', re.IGNORECASE),
    re.compile(r'Amount$', re.IGNORECASE),
    re.compile(r'Price$', re.IGNORECASE),
    re.compile(r'Weight$', re.IGNORECASE),
    re.compile(r'Volume$', re.IGNORECASE),
    re.compile(r'^num', re.IGNORECASE),
    re.compile(r'Cost$', re.IGNORECASE),
    re.compile(r'Total$', re.IGNORECASE),
]

SELECT_PATTERNS = [
    re.compile(r'Type$', re.IGNORECASE),
    re.compile(r'Kind$', re.IGNORECASE),
    re.compile(r'Category$', re.IGNORECASE),
    re.compile(r'Status$', re.IGNORECASE),
    re.compile(r'CountryCode$', re.IGNORECASE),
    re.compile(r'CurrencyCode$', re.IGNORECASE),
]


# =============================================================================
# Schema Transform Service
# =============================================================================

class SchemaTransformService:
    """
    Service for transforming Kontur JSON schemas into form definitions

    Key responsibilities:
    1. Parse Kontur JSON schema
    2. Extract field structure and infer types
    3. Apply Russian localization from database
    4. Generate default form sections
    5. Calculate schema hash for change detection
    """

    @classmethod
    async def transform_schema(
        cls,
        document_mode_id: str,
        gf_code: str = "",
        type_name: str = ""
    ) -> FormDefinition:
        """
        Fetch schema from Kontur API and transform to form definition

        Args:
            document_mode_id: The document mode ID (e.g., "1002007E")
            gf_code: GF code from templates list
            type_name: Type name from templates list

        Returns:
            FormDefinition ready for storage
        """
        log.info(f"Transforming schema for {document_mode_id}")

        # 1. Fetch raw schema from Kontur
        client = get_kontur_client()
        raw_schema_str = await client.get_document_template(document_mode_id)

        try:
            schema = json.loads(raw_schema_str)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse schema JSON for {document_mode_id}: {e}")
            schema = {}

        # 2. Calculate hash for change detection
        schema_hash = hashlib.sha256(raw_schema_str.encode()).hexdigest()

        # 3. Parse schema into field definitions
        fields = cls._parse_schema_fields(schema, "")

        # 4. Load Russian labels
        fields = await cls._apply_russian_labels(fields)

        # 5. Generate sections based on top-level structure or custom mapping
        sections = cls._generate_sections(document_mode_id, fields)

        # 6. Extract default values
        default_values = cls._extract_defaults(schema)

        return FormDefinition(
            document_mode_id=document_mode_id,
            gf_code=gf_code,
            type_name=type_name,
            fields=fields,
            sections=sections,
            default_values=default_values,
            kontur_schema_json=schema,
            kontur_schema_hash=schema_hash,
            version=1
        )

    @classmethod
    def _parse_schema_fields(
        cls,
        schema: Dict[str, Any],
        parent_path: str,
        depth: int = 0
    ) -> List[FieldDefinition]:
        """
        Recursively parse Kontur schema into field definitions

        Handles various schema structures:
        - Plain key-value objects where value is a description string
        - JSON Schema with "type", "properties"
        - Arrays with "items" or array of objects
        - Nested objects (dict values that contain other dicts/strings)
        """
        fields = []

        # Prevent infinite recursion
        if depth > 15:
            log.warning(f"Max depth reached at {parent_path}")
            return fields

        # Determine what to iterate over
        if "properties" in schema:
            # JSON Schema format
            properties = schema.get("properties", {})
            required_fields = set(schema.get("required", []))
        else:
            # Plain object format (Kontur style: key -> description_string or nested_object)
            properties = schema
            required_fields = set()

        for key, value in properties.items():
            # Skip metadata keys
            if key.startswith("$") or key.startswith("@"):
                continue

            path = f"{parent_path}.{key}" if parent_path else key

            # Detect field type
            field_type = cls._detect_field_type(key, value)

            # For Kontur-style schemas, if value is a string, use it as label_ru
            # Otherwise use humanized field name
            label_ru = value if isinstance(value, str) else cls._humanize_field_name(key)

            field_def = FieldDefinition(
                path=path,
                name=key,
                field_type=field_type,
                required=key in required_fields,
                label_ru=label_ru,
            )

            # Handle based on value type
            if isinstance(value, dict):
                # Check if it's a JSON Schema type definition
                schema_type = value.get("type", "")
                max_length = value.get("maxLength")
                min_val = value.get("minimum")
                max_val = value.get("maximum")
                enum_values = value.get("enum", [])

                if max_length:
                    field_def.max_length = max_length
                if min_val is not None:
                    field_def.min_value = min_val
                if max_val is not None:
                    field_def.max_value = max_val

                # Handle enums as SELECT
                if enum_values:
                    field_def.field_type = FieldType.SELECT
                    field_def.options = [
                        FieldOption(value=str(v), label=str(v))
                        for v in enum_values
                    ]

                # Handle nested objects
                if schema_type == "object" or "properties" in value:
                    field_def.field_type = FieldType.OBJECT
                    field_def.children = cls._parse_schema_fields(value, path, depth + 1)

                # Handle arrays
                elif schema_type == "array" or "items" in value:
                    field_def.field_type = FieldType.ARRAY
                    items_schema = value.get("items", {})
                    if isinstance(items_schema, dict):
                        field_def.children = cls._parse_schema_fields(items_schema, path, depth + 1)

                # If no schema type, check if it's a nested object
                # A nested object has values that are dicts (sub-objects) or lists (arrays)
                # If ALL values are strings, this dict itself is a container of simple fields
                elif not schema_type:
                    # Check if this dict contains nested structures (dicts or lists)
                    # vs just being a container of "key: string_description" pairs
                    has_nested_objects = False
                    for v in value.values():
                        if isinstance(v, (dict, list)):
                            has_nested_objects = True
                            break

                    if has_nested_objects and len(value) > 0:
                        # This contains nested objects/arrays - recurse into it
                        field_def.field_type = FieldType.OBJECT
                        field_def.children = cls._parse_schema_fields(value, path, depth + 1)
                    elif len(value) > 0:
                        # All values are strings - this is still a container object
                        # but with simple string fields inside
                        field_def.field_type = FieldType.OBJECT
                        field_def.children = cls._parse_schema_fields(value, path, depth + 1)

            elif isinstance(value, list):
                # Array value - check what's inside
                if value:
                    first_item = value[0]
                    if isinstance(first_item, dict):
                        # Array of objects - this is a repeatable section
                        field_def.field_type = FieldType.ARRAY
                        field_def.children = cls._parse_schema_fields(first_item, path, depth + 1)
                    elif isinstance(first_item, str):
                        # Array with single string like ["Текст контракта"]
                        # This is NOT an array field, it's a TEXT field with Russian label
                        field_def.field_type = FieldType.TEXT
                        field_def.label_ru = first_item
                else:
                    # Empty array - treat as simple array
                    field_def.field_type = FieldType.ARRAY

            # Detect textarea for long text fields
            if field_def.field_type == FieldType.TEXT:
                if field_def.max_length and field_def.max_length > 200:
                    field_def.field_type = FieldType.TEXTAREA

            fields.append(field_def)

        return fields

    @classmethod
    def _detect_field_type(cls, field_name: str, value: Any) -> FieldType:
        """Detect field type from field name and value"""

        # Check by value type first
        if isinstance(value, bool) or value in ("true", "false", True, False):
            return FieldType.CHECKBOX
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return FieldType.NUMBER
        if isinstance(value, list):
            # Check if it's array of objects (real ARRAY) or array with string (TEXT field)
            if value and isinstance(value[0], dict):
                return FieldType.ARRAY
            elif value and isinstance(value[0], str):
                # ["Текст контракта"] -> this is a TEXT field, not ARRAY
                return FieldType.TEXT
            return FieldType.ARRAY
        if isinstance(value, dict) and not value.get("type"):
            # Check if it has nested properties (object)
            # For Kontur schemas: dict with string values is also an object (container of fields)
            if "properties" in value:
                return FieldType.OBJECT
            # Check if any values are dicts (nested objects) or strings (field descriptions)
            has_content = False
            for v in value.values():
                if isinstance(v, (dict, str, list)):
                    has_content = True
                    break
            if has_content:
                return FieldType.OBJECT

        # Check JSON Schema type
        if isinstance(value, dict):
            schema_type = value.get("type", "")
            if schema_type == "boolean":
                return FieldType.CHECKBOX
            if schema_type in ("integer", "number"):
                return FieldType.NUMBER
            if schema_type == "array":
                return FieldType.ARRAY
            if schema_type == "object":
                return FieldType.OBJECT

        # Check by field name patterns
        for pattern in DATE_PATTERNS:
            if pattern.search(field_name):
                return FieldType.DATE

        for pattern in BOOLEAN_PATTERNS:
            if pattern.search(field_name):
                return FieldType.CHECKBOX

        for pattern in NUMBER_PATTERNS:
            if pattern.search(field_name):
                return FieldType.NUMBER

        for pattern in SELECT_PATTERNS:
            if pattern.search(field_name):
                return FieldType.SELECT

        # Check value format for dates
        if isinstance(value, str):
            if re.match(r'^\d{4}-\d{2}-\d{2}', value):
                return FieldType.DATE

        return FieldType.TEXT

    @classmethod
    def _humanize_field_name(cls, name: str) -> str:
        """Convert field name to human-readable label"""
        # Split by underscores and CamelCase
        result = re.sub(r'_', ' ', name)
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)
        return result.strip()

    @classmethod
    async def _apply_russian_labels(
        cls,
        fields: List[FieldDefinition]
    ) -> List[FieldDefinition]:
        """Load Russian labels from dc_field_labels_ru table"""

        # Collect all field paths
        all_paths: List[str] = []

        def collect_paths(field_list: List[FieldDefinition]):
            for f in field_list:
                all_paths.append(f.path)
                if f.children:
                    collect_paths(f.children)

        collect_paths(fields)

        if not all_paths:
            return fields

        # Fetch labels from database
        try:
            placeholders = ", ".join(f"${i+1}" for i in range(len(all_paths)))
            rows = await pg_client.fetch(
                f"""
                SELECT field_path, label_ru, hint_ru, placeholder_ru
                FROM dc_field_labels_ru
                WHERE field_path IN ({placeholders})
                """,
                *all_paths
            )

            labels_map = {
                row["field_path"]: {
                    "label_ru": row["label_ru"],
                    "hint_ru": row["hint_ru"] or "",
                    "placeholder_ru": row["placeholder_ru"] or "",
                }
                for row in rows
            }

            # Apply labels
            def apply_labels(field_list: List[FieldDefinition]):
                for f in field_list:
                    if f.path in labels_map:
                        labels = labels_map[f.path]
                        f.label_ru = labels["label_ru"]
                        f.hint_ru = labels["hint_ru"]
                        f.placeholder_ru = labels["placeholder_ru"]
                    if f.children:
                        apply_labels(f.children)

            apply_labels(fields)

        except Exception as e:
            log.warning(f"Failed to load Russian labels: {e}")

        return fields

    @classmethod
    def _generate_sections(
        cls,
        document_mode_id: str,
        fields: List[FieldDefinition]
    ) -> List[FormSection]:
        """
        Generate sections - use custom mapping if available, otherwise default
        """
        if document_mode_id in SECTION_MAPPING:
            return cls._generate_sections_from_mapping(
                document_mode_id,
                SECTION_MAPPING[document_mode_id],
                fields
            )
        return cls._generate_default_sections(fields)

    @classmethod
    def _generate_sections_from_mapping(
        cls,
        document_mode_id: str,
        mapping: Dict[str, Any],
        fields: List[FieldDefinition]
    ) -> List[FormSection]:
        """
        Generate sections from custom mapping configuration.

        The mapping allows grouping fields from different JSON paths into
        single UI sections (like Kontur does).
        """
        sections = []
        section_configs = mapping.get("sections", [])

        # Build a map of field paths to field definitions for quick lookup
        field_map: Dict[str, FieldDefinition] = {}

        def build_field_map(field_list: List[FieldDefinition]):
            for f in field_list:
                field_map[f.path] = f
                if f.children:
                    build_field_map(f.children)

        build_field_map(fields)

        for sort_order, config in enumerate(section_configs):
            section_key = config.get("key", f"section_{sort_order}")
            title_ru = config.get("title_ru", section_key)
            icon = config.get("icon", "FileText")
            field_paths = config.get("field_paths", [])

            # Expand field paths - if a path points to an object/array,
            # we include it as-is (the frontend will render its children)
            expanded_paths = []
            for path in field_paths:
                # Check if this exact path exists
                if path in field_map:
                    expanded_paths.append(path)
                else:
                    # Try to find fields that start with this path (for nested access)
                    # e.g., "ContractTerms.DealSign" should find the field
                    found = False
                    for field_path in field_map.keys():
                        if field_path == path or field_path.startswith(path + "."):
                            if path not in expanded_paths:
                                expanded_paths.append(path)
                            found = True
                            break

                    if not found:
                        # Path might be a top-level field that we should still include
                        # This handles cases where the path is in the field_paths but
                        # not parsed as a standalone field
                        log.debug(f"Field path not found in field_map: {path}")
                        expanded_paths.append(path)

            sections.append(FormSection(
                section_key=section_key,
                title_ru=title_ru,
                icon=icon,
                sort_order=sort_order,
                field_paths=expanded_paths,
                columns=1,  # Complex sections usually need full width
                collapsible=False,
                default_expanded=True
            ))

        return sections

    @classmethod
    def _generate_default_sections(
        cls,
        fields: List[FieldDefinition]
    ) -> List[FormSection]:
        """Generate default sections by grouping top-level fields"""
        sections = []
        sort_order = 0
        simple_fields = []  # Fields that are not objects/arrays with children

        # Russian section names mapping
        section_names_ru = {
            "ContractTerms": "Условия контракта",
            "ForeignPerson": "Реквизиты иностранной стороны",
            "RussianPerson": "Реквизиты российского контрактодержателя",
            "ContractDeliveryTerms": "Условия поставки",
            "ContractSpecification": "Спецификация к контракту",
            "ContractRegistration": "Регистрация контракта",
            "ContractSignedPerson": "Лицо, подписавшее документ",
            "BankInformation": "Платежные реквизиты",
            "Address": "Адрес",
            "Contact": "Контактная информация",
            "ChangeContract": "Сведения о дополнениях и приложениях",
            "InvoiceSaleTerms": "Срок оплаты по инвойсу",
            "SpecificationGoodsExtended": "Товары спецификации",
            "AdditionalGoodsDescription": "Дополнительные характеристики товара",
            "GoodsPlace": "Грузовые места",
            "GoodsWeight": "Вес товара",
            "RFOrganizationFeatures": "Реквизиты РФ",
            "RKOrganizationFeatures": "Реквизиты РК",
            "RBOrganizationFeatures": "Реквизиты РБ",
            "RAOrganizationFeatures": "Реквизиты РА",
            "KGOrganizationFeatures": "Реквизиты КР",
        }

        # Icon mapping based on field names
        icon_map = {
            "contract": "FileText",
            "person": "User",
            "organization": "Building2",
            "foreign": "Globe",
            "russian": "Flag",
            "delivery": "Truck",
            "terms": "ScrollText",
            "specification": "Package",
            "goods": "Package",
            "registration": "ClipboardCheck",
            "signed": "PenTool",
            "bank": "Landmark",
            "address": "MapPin",
            "contact": "Phone",
        }

        def get_icon(field_name: str) -> str:
            """Get icon based on field name keywords"""
            name_lower = field_name.lower()
            for keyword, icon in icon_map.items():
                if keyword in name_lower:
                    return icon
            return "FileText"

        def get_section_title(field_name: str, label_ru: str) -> str:
            """Get Russian section title"""
            if field_name in section_names_ru:
                return section_names_ru[field_name]
            if label_ru and label_ru != field_name:
                return label_ru
            return cls._humanize_field_name(field_name)

        for field in fields:
            if field.field_type in (FieldType.OBJECT, FieldType.ARRAY) and field.children:
                # Create section from top-level object/array with children
                sections.append(FormSection(
                    section_key=field.name.lower().replace(" ", "_"),
                    title_ru=get_section_title(field.name, field.label_ru),
                    sort_order=sort_order,
                    field_paths=[field.path],  # Include the parent path itself
                    icon=get_icon(field.name),
                    columns=1  # Complex objects usually need full width
                ))
                sort_order += 1
            else:
                # Collect simple fields for "main" section
                simple_fields.append(field.path)

        # Create "main" section for simple fields at the beginning
        if simple_fields:
            sections.insert(0, FormSection(
                section_key="main",
                title_ru="Основные данные",
                sort_order=-1,  # Will be first
                field_paths=simple_fields,
                icon="FileText",
                columns=2
            ))

        # Re-sort by sort_order
        sections.sort(key=lambda s: s.sort_order)
        for i, section in enumerate(sections):
            section.sort_order = i

        return sections

    @classmethod
    def _extract_defaults(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract default values from schema"""
        defaults: Dict[str, Any] = {}

        def extract(obj: Dict[str, Any], path: str = ""):
            if not isinstance(obj, dict):
                return

            properties = obj.get("properties", obj)

            for key, value in properties.items():
                if key.startswith("$") or key.startswith("@"):
                    continue

                current_path = f"{path}.{key}" if path else key

                if isinstance(value, dict):
                    if "default" in value:
                        defaults[current_path] = value["default"]
                    extract(value, current_path)

        extract(schema)
        return defaults
