# Thesis Prototype: Controlled Collaborative Ontology Change Workflow

## 1) Project overview

This repository contains a **thesis-grade, WebProtégé-compatible research prototype** for improving collaborative ontology editing workflows.

The prototype focuses on four capability areas:
- conflict/duplicate detection
- validation
- governance/review workflow
- optional bounded AI explanation support

It is designed to evaluate an enhanced process around ontology change submission and review, while remaining explainable and traceable.

## 2) Thesis scope boundary

This project is a **controlled research prototype**, not a production platform.

- AI outputs are **advisory only**.
- Autonomous ontology modification is **not allowed**.
- The goal is to simulate and evaluate an enhanced workflow, **not replace WebProtégé**.

## 3) Current implementation status

### Completed
- ✅ **T33** Build data model and issue registry
- ✅ **T34** Conflict Detection Service
- ✅ **T35** Validation Service
- ✅ **P1** Defense-stage tests for domain model and registry
- ✅ **P2** Defense-stage tests for conflict detection

### Planned next
- ⏳ **T36** Governance/Review Service
- ⏳ **T37** Optional AI Explanation Service
- ⏳ **T38** Dashboard/Reporting
- ⏳ **T39** Integration testing and bug fixing

## 4) Architecture mapping to thesis design

Current code modules map to thesis architecture as follows:

- `src/thesis_prototype/models.py`  
  Domain entities and traceability artifacts (`OntologyChange`, `ConflictIssue`, `ValidationResult`, `ReviewDecision`, `AIExplanationArtifact`) plus enums.
- `src/thesis_prototype/registry.py`  
  In-memory issue/history persistence and retrieval layer (`InMemoryIssueRegistry`).
- `src/thesis_prototype/conflict_detection.py`  
  Duplicate, near-duplicate, and overlap/concurrent conflict analysis (`ConflictDetectionService`).
- `src/thesis_prototype/validation_service.py`  
  Deterministic rule-based validation pipeline (`ValidationService`) producing structured `ValidationResult` records.
- Future modules (T36+)  
  Governance/review, optional bounded AI explanation, dashboards, and integration orchestration.

## 5) Current capabilities

The current prototype can:
- create structured `OntologyChange` records
- create/store/fetch `ConflictIssue`, `ValidationResult`, `ReviewDecision`, and `AIExplanationArtifact` records via the registry
- preserve issue traceability links and issue history
- detect direct duplicates
- detect near-duplicates
- detect overlap/concurrent conflicts
- validate changes against explicit deterministic rules (required label/description, cardinality, domain/range, naming convention)
- avoid uncontrolled duplicate-issue spam on repeated detection runs (deterministic fingerprinting/idempotent behavior)
- avoid uncontrolled duplicate validation-result spam on repeated validation runs for unchanged inputs (deterministic result IDs)

## 6) Current assumptions and limitations

- Duplicate and near-duplicate checks currently use `proposed_values["label"]`.
- Near-duplicate threshold behavior is **inclusive at equality**.
- Overlap logic is deterministic and intentionally lightweight.
- “Unresolved context” means prior related issue state is **not `CLOSED`**.
- Persistence is currently **in-memory**.
- Conflict evidence payload shape is flexible and not yet schema-constrained.
- SHACL engine integration is not implemented yet.
- Full governance/reviewer workflow logic is not implemented yet.
- Production-grade concurrency/durability guarantees are not implemented yet.

## 7) Testing

This repository uses `pytest`.

### Run all tests
```bash
pytest -q
```

### Run only defense-stage domain/registry tests (P1)
```bash
pytest -q tests/test_defense_domain_registry.py
```

### Run only defense-stage conflict-detection tests (P2)
```bash
pytest -q tests/test_defense_conflict_detection.py
```

### What defense-stage tests are intended to prove
- P1 demonstrates stability and safety of domain entities and registry behaviors (immutability, validation, traceability, transition guards, deterministic history).
- P2 demonstrates that the conflict detector catches core collaboration risks (exact duplicates, near-duplicates, overlap conflicts) while controlling false positives and duplicate issue creation.
- Validation tests demonstrate deterministic rule evaluation, traceable `ValidationResult` outputs, configurable rule metadata, and modular adapter boundaries for future SHACL integration.

## 8) Suggested repository usage order

Recommended implementation/extension sequence:
1. foundation (models + registry)
2. conflict detection
3. validation
4. governance/review
5. optional AI explanation
6. integration + evaluation

## 9) Defense-readiness note

The defense-stage suites are scenario-mapped to thesis requirements and are intended to support:
- **Chapter 5** implementation evidence (design decisions and behavior)
- **Chapter 6** evaluation evidence (test-backed claims and limitations)

## Seed/example usage

A small local fixture is available at:
- `examples/seed_data.py`

It seeds a linked in-memory chain for quick manual inspection and local experimentation.
