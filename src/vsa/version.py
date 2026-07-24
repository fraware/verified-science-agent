"""Package and schema version constants."""

__version__ = "0.7.2"
SCHEMA_VERSION = "1.2.0"
SUPPORTED_SCHEMA_VERSIONS = ("1.0.0", "1.1.0", "1.2.0")
VALIDATION_VERSION = "1.2.0"
RENDERER_VERSION = "1.2.0"
PROMPT_TEMPLATE_VERSION = "claim_extraction_v1"

# Companion integration schemas (additive; do not change SCHEMA_VERSION)
ENVELOPE_SCHEMA_VERSION = "1.0.0"
DECISION_TIME_BUNDLE_SCHEMA_VERSION = "1.0.0"
AKTA_ACTION_CONTEXT_SCHEMA_VERSION = "1.0.0"
OUTCOME_LINK_SCHEMA_VERSION = "1.0.0"
PCS_PORTABLE_REF_SCHEMA_ID = "pcs.portable_evidence_ref/1.0.0"
