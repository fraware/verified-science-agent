.PHONY: demo validate render test

validate:
	python scripts/validate_ledger.py examples/brca1_c68_69del_ledger.json

render:
	python scripts/render_report.py examples/brca1_c68_69del_ledger.json --out reports/generated_brca1_report.md

demo: validate render
	@echo "Demo ready: reports/generated_brca1_report.md"

test: validate
