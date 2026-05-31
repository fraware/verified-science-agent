.PHONY: demo validate render hash test ui install benchmark audit sign

install:
	pip install -e ".[dev,ui,pdf,signing]"

demo: install
	vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
	vsa validate reports/brca1_report.json
	vsa audit reports/brca1_report.json --audit-mode rule --out reports/audit.json
	vsa render reports/brca1_report.json --format markdown --out reports/brca1_report.md
	vsa hash reports/brca1_report.json

validate:
	vsa validate examples/*.json reports/*.json

render:
	vsa render reports/brca1_report.json --format markdown --out reports/brca1_report.md

hash:
	vsa hash reports/brca1_report.json --json

test:
	pytest

benchmark:
	vsa benchmark

audit:
	vsa audit reports/brca1_report.json --audit-mode rule

attest:
	vsa attest reports/brca1_report.json --out reports/attestation.json

serve:
	vsa serve --port 8000

sign:
	vsa sign reports/brca1_report.json

ui:
	streamlit run ui/app.py

invalid:
	vsa validate examples/bad_unsupported_claim.json --skip-hash-check || true
	vsa validate examples/bad_missing_evidence_ref.json --skip-hash-check || true
