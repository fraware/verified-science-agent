# Claim extraction prompt template v1

Version: claim_extraction_v1

## Rules

1. Retrieval produces evidence. Generation produces claims. Validation checks claims against evidence.
2. The LLM may ONLY reference evidence IDs present in the retrieved evidence bundle.
3. Do NOT invent source_name, retrieval_path, identifier, or raw_record_hash fields.
4. Each claim must be atomic, short, and independently reviewable.
5. Assign review_boundary: safe_summary | requires_domain_review | requires_clinical_review | speculative | unsupported.
6. Clinical significance claims MUST use requires_clinical_review.
7. Hypotheses MUST use speculative and uncertainty_level high or medium.

## Input

```json
{
  "subject": { ... },
  "evidence": [ { "evidence_id": "E001", ... } ]
}
```

## Output

```json
{
  "claims": [
    {
      "claim_id": "C001",
      "claim_type": "classification",
      "claim_text": "...",
      "evidence_ids": ["E001"],
      "confidence": 0.0,
      "review_boundary": "requires_clinical_review",
      "uncertainty_level": "low"
    }
  ]
}
```
