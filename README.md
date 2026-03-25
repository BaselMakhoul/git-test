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

## Intentionally left for later steps

To stay within Step 1 scope, this implementation intentionally does **not** include:

- conflict or duplicate detection algorithms
- SHACL execution engine integration
- governance policy decision logic beyond data capture/state updates
- AI generation logic
- dashboards/UI
- full external API behavior

These models and registry are designed to be consumed by those services in later steps.
