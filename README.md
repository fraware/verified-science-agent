# Verified Science Agent

<p align="center">
  <strong>Evidence-backed AI research workflows.</strong>
</p>

<p align="center">
  A lightweight open framework for turning AI-generated scientific outputs into structured, reviewable, and reproducible reports.
</p>

---

## Why this project exists

AI systems can already summarize papers, retrieve biological records, inspect protein structures, and generate scientific hypotheses in seconds. The difficult problem is establishing whether those outputs can be trusted inside real research environments.

Most scientific AI demos stop at generation.

This repository focuses on verification, provenance, and evidence tracking.

The core idea is simple:

- every important claim should be traceable,
- every source should be explicit,
- every generated report should be reviewable,
- every workflow should remain reproducible.

The project was initially built during an AGI House + Google DeepMind builder event focused on Gemini, Managed Agents, and Science Skills. The repository has since been simplified into a reusable developer starter kit for evidence-aware AI systems.

---

## What this repository provides

### Structured evidence records

Scientific claims are stored in a simple JSON format that records:

- claim text
- confidence
- source links
- retrieval paths
- validation state
- review notes

The format is intentionally lightweight and readable.

### Validation tools

The repository includes local validators that check whether reports:

- contain supporting evidence,
- expose provenance paths,
- include verification metadata,
- avoid structurally incomplete records.

### Report rendering

A compact renderer converts evidence records into readable Markdown reports.

### Provenance hash chains

The repository can generate a simple cryptographic hash chain over report claims so downstream systems can verify report integrity.

### Reusable examples

Included examples demonstrate:

- valid evidence-backed reports,
- intentionally invalid reports,
- validation failures,
- reproducible outputs.

---

## Repository structure

```text
examples/       Example evidence records
scripts/        Validation, rendering, and provenance tools
templates/      Reusable JSON templates
reports/        Generated reports
ui/             Lightweight visualization app
integrations/   Example integration adapters
prompts/        Review and verification prompts
```

---

## Quick start

Clone the repository:

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
```

Run the main demo:

```bash
make demo
```

Validate the example report:

```bash
python scripts/validate_ledger.py examples/brca1_c68_69del_ledger.json
```

Generate a Markdown report:

```bash
python scripts/render_report.py examples/brca1_c68_69del_ledger.json --out reports/generated_brca1_report.md
```

Generate a provenance chain:

```bash
python scripts/provenance_hash.py examples/brca1_c68_69del_ledger.json
```

Launch the lightweight UI:

```bash
streamlit run ui/app.py
```

---

## Example workflow

1. An AI system generates a scientific summary.
2. Claims are converted into structured evidence records.
3. Each claim is linked to supporting sources.
4. Validation checks are executed.
5. A reviewable report is rendered.
6. Provenance hashes are generated.

The resulting artifact becomes easier to inspect, reproduce, and share.

---

## Example use cases

The repository is intentionally domain-general.

Potential applications include:

- genomics
- drug discovery
- literature synthesis
- chemistry workflows
- materials science
- clinical research tooling
- AI-assisted peer review
- internal research copilots
- scientific compliance pipelines
- agent evaluation systems

---

## Design principles

### Small surface area

The project avoids heavy infrastructure requirements.

### Human-readable artifacts

Outputs should remain understandable without specialized tooling.

### Local-first execution

All included workflows run locally.

### Interoperable structure

The evidence format is compatible with external agent systems and future orchestration frameworks.

### Research-first orientation

The repository is intended for experimentation, infrastructure exploration, and scientific tooling research.

---

## Relationship to external systems

This repository does not depend on a specific model provider.

It can be connected to:

- Gemini
- OpenAI models
- Claude
- local models
- retrieval systems
- scientific databases
- agent frameworks
- orchestration runtimes

The included integration adapter demonstrates how external systems can normalize outputs into the evidence format.

---

## Safety notice

This repository is a research and infrastructure demonstration.

It is not:

- a medical device,
- a clinical decision system,
- a diagnostic platform,
- a substitute for expert review.

Human oversight remains essential.

---

## Vision

Scientific AI systems are moving from passive assistants toward autonomous research workflows.

As these systems become more capable, the infrastructure surrounding evidence, provenance, reproducibility, and review becomes increasingly important.

The long-term goal of this project is to explore what trustworthy scientific AI pipelines could look like when verification is treated as a first-class system component.

---

## Contributing

Contributions are welcome.

Good extensions include:

- additional report templates,
- new validators,
- integration adapters,
- benchmark datasets,
- provenance systems,
- UI improvements,
- evaluation workflows,
- scientific tooling integrations.

---

## License

MIT License.
