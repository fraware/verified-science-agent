import json
from pathlib import Path
import streamlit as st

st.title('Verified Science Agent')

ledger = json.loads(Path('examples/brca1_c68_69del_ledger.json').read_text())

st.write('Example evidence-backed report viewer.')

for claim in ledger.get('claims', []):
    st.subheader(claim['claim_id'])
    st.write(claim['claim_text'])
    st.write(f"Support: {claim['support_level']}")
    for ev in claim.get('evidence', []):
        st.write(f"{ev['source_name']} -> {ev['retrieval_path']}")
