.PHONY: demo validate render hash test bad-ledger ui

LEDGER=examples/brca1_c68_69del_ledger.json
BAD_LEDGER=examples/bad_ledger_missing_evidence.json

validate:
	python scripts/validate_ledger.py $(LEDGER)

render:
	python scripts/render_report.py $(LEDGER) --out reports/generated_brca1_report.md

hash:
	python scripts/provenance_hash.py $(LEDGER) --out reports/provenance_hash_chain.json

demo: validate render hash
	@echo "Demo ready: reports/generated_brca1_report.md"

bad-ledger:
	python scripts/validate_ledger.py $(BAD_LEDGER)

test: demo
	@if python scripts/validate_ledger.py $(BAD_LEDGER); then echo "bad ledger unexpectedly passed"; exit 1; else echo "bad ledger failed as expected"; fi

ui:
	streamlit run ui/streamlit_app.py
