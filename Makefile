.PHONY: demo validate render hash test invalid-ledger ui

LEDGER=examples/brca1_c68_69del_ledger.json
INVALID_LEDGER=examples/invalid_ledger_missing_source.json
REPORT=reports/generated_brca1_report.md
HASH_CHAIN=reports/provenance_hash_chain.json

validate:
	python scripts/validate_ledger.py $(LEDGER)

render:
	python scripts/render_report.py $(LEDGER) --out $(REPORT)

hash:
	python scripts/provenance_hash.py $(LEDGER) --out $(HASH_CHAIN)

demo: validate render hash
	@echo "Demo ready: $(REPORT)"
	@echo "Provenance chain ready: $(HASH_CHAIN)"

invalid-ledger:
	python scripts/validate_ledger.py $(INVALID_LEDGER)

test: demo
	@if python scripts/validate_ledger.py $(INVALID_LEDGER); then echo "invalid ledger unexpectedly passed"; exit 1; else echo "invalid ledger failed as expected"; fi

ui:
	streamlit run ui/app.py
