# Thesis Prototype - Step 1 Foundation

This repository now includes the **Step 1 implementation** for the thesis prototype: foundational domain models and an issue registry persistence layer.

## Model structure

The `src/thesis_prototype/models.py` module defines typed, validated models for:

- `OntologyChange`
- `ConflictIssue`
- `ValidationResult`
- `ReviewDecision`
- `AIExplanationArtifact`

Enums constrain critical fields for consistency and future interoperability:

- operation type
- issue category
- severity
- workflow state
- reviewer decision type
- validation status/rule type
- AI artifact type

## Registry and traceability

The `src/thesis_prototype/registry.py` module provides `InMemoryIssueRegistry` for Step 1 persistence behavior:

- Create/store all core record types
- Fetch by id
- Fetch all issues/validation results for a change
- Fetch ordered issue history events
- Safe workflow state transitions via an explicit state transition map
- Traceability links (issue ↔ validation results, issue ↔ AI artifacts)

> **Important:** This registry is intentionally **in-memory only** for prototype/thesis Step 1 and is **not production persistence**.

## Seed data

`examples/seed_data.py` creates a small in-memory example dataset for local testing and demonstration.

## Step 2: Conflict Detection Service (T34)

`src/thesis_prototype/conflict_detection.py` adds a lightweight, explainable conflict detector that currently covers:

- **Direct duplicate detection** using explicit label normalization (trim, lowercase, collapse repeated spaces).
- **Near-duplicate detection** using deterministic `difflib.SequenceMatcher` similarity with a configurable threshold.
- **Overlapping/concurrent change conflicts** for overlap-sensitive operations and fields when changes are within an active window or tied to unresolved context.

Current scope intentionally does **not** cover:

- SHACL or schema validation execution
- reviewer/governance decision logic
- ontology reasoning/inference
- AI generation or automated ontology modification

The design is intentionally minimal and thesis-friendly: every rule is explicit, deterministic, and easy to describe/cite in methodology and implementation chapters.

## Intentionally left for later steps

After Step 2, this prototype still intentionally does **not** include:

- SHACL execution engine integration (planned for validation service step)
- governance policy decision logic beyond data capture/state updates
- AI generation logic
- dashboards/UI
- full external API behavior

The current models, in-memory registry, and conflict detector are designed to be consumed by those services in later steps.
