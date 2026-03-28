# Thesis Prototype: Controlled Collaborative Ontology Change Workflow

## 1) Project overview

This repository contains a **thesis-grade, WebProtégé-compatible research prototype** for improving collaborative ontology editing workflows.

The prototype focuses on four capability areas:
- conflict/duplicate detection
- validation
- governance/review workflow
- optional bounded AI explanation support

It now also includes lightweight demo-grade **authentication and role-aware dashboards** for Admin, Reviewer, and Contributor walkthroughs.

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
- ✅ **T36** Governance/Review Service
- ✅ **P1** Defense-stage tests for domain model and registry
- ✅ **P2** Defense-stage tests for conflict detection

### Planned next
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
- `src/thesis_prototype/governance_service.py`  
  Deterministic review workflow orchestration (`GovernanceReviewService`) for flagged issues/failed validations, reviewer assignment, decisions, resubmission lineage, and auditable history.
- `src/thesis_prototype/auth_service.py` + `src/thesis_prototype/permissions.py`  
  Lightweight local authentication, user-management primitives, secure password hashing, and explicit role/permission checks.
- `src/thesis_prototype/demo_backend.py` + `src/thesis_prototype/demo_api.py` + `src/thesis_prototype/demo_ui.py`  
  Thin demo interaction layer (local backend facade, optional FastAPI routes, and Streamlit views).
- Future modules (T37+)  
  Optional bounded AI explanation, dashboards, and integration orchestration.

## 5) Current capabilities

The current prototype can:
- create structured `OntologyChange` records
- create/store/fetch `ConflictIssue`, `ValidationResult`, `ReviewDecision`, and `AIExplanationArtifact` records via the registry
- preserve issue traceability links and issue history
- detect direct duplicates
- detect near-duplicates
- detect overlap/concurrent conflicts
- validate changes against explicit deterministic rules (required label/description, cardinality, domain/range, naming convention)
- open governance review for existing `ConflictIssue` or failed `ValidationResult`
- assign/reassign reviewer deterministically and record approve/reject/request_revision decisions with rationale/timestamp traceability
- link corrected/resubmitted changes back to original review path for auditable lineage
- avoid uncontrolled duplicate-issue spam on repeated detection runs (deterministic fingerprinting/idempotent behavior)
- avoid uncontrolled duplicate validation-result spam on repeated validation runs for unchanged inputs (deterministic result IDs)
- run a local demo UI to submit changes, trigger conflict detection/validation, and inspect registry traceability in one interface
- login/logout with role-specific dashboard routing (Admin, Reviewer, Contributor)
- manage demo users/roles (admin only) and enforce role-based action permissions

## 6) Current assumptions and limitations

- Duplicate and near-duplicate checks currently use `proposed_values["label"]`.
- Near-duplicate threshold behavior is **inclusive at equality**.
- Overlap logic is deterministic and intentionally lightweight.
- “Unresolved context” means prior related issue state is **not `CLOSED`**.
- Persistence is currently **in-memory**.
- Conflict evidence payload shape is flexible and not yet schema-constrained.
- SHACL engine integration is not implemented yet.
- Advanced governance policy/routing logic is not implemented yet.
- Governance policy is intentionally simple (single assigned reviewer policy; no role-based auth integration yet).
- Authentication/RBAC is demo-grade and local-process scoped (no enterprise SSO/OIDC; no production hardening claims).
- Production-grade concurrency/durability guarantees are not implemented yet.

## 7) Testing

This repository uses `pytest`.

### Run all tests
```bash
pytest -q
```

### Run demo backend/API tests
```bash
pytest -q tests/test_demo_backend_api.py
```

### Run only defense-stage domain/registry tests (P1)
```bash
pytest -q tests/test_defense_domain_registry.py
```

### Run only defense-stage conflict-detection tests (P2)
```bash
pytest -q tests/test_defense_conflict_detection.py
```

### Run defense-stage validation tests
```bash
pytest -q tests/test_defense_validation_service.py
```

### What defense-stage tests are intended to prove
- P1 demonstrates stability and safety of domain entities and registry behaviors (immutability, validation, traceability, transition guards, deterministic history).
- P2 demonstrates that the conflict detector catches core collaboration risks (exact duplicates, near-duplicates, overlap conflicts) while controlling false positives and duplicate issue creation.
- Validation tests demonstrate deterministic rule evaluation, traceable `ValidationResult` outputs, configurable rule metadata, and modular adapter boundaries for future SHACL integration.
- Governance tests demonstrate deterministic intake/routing, safe state transitions, reviewer authorization checks, decision traceability, revision/resubmission lineage, and lifecycle closure behavior.

## 8) Suggested repository usage order

Recommended implementation/extension sequence:
1. foundation (models + registry)
2. conflict detection
3. validation
4. governance/review
5. optional AI explanation
6. integration + evaluation

## 10) Local demo UI

This project includes a thin demo UI for Chapter 5 screenshots and walkthroughs.

### Views/screens
- **Login Screen**: authenticate as demo users and route to role-specific dashboard
- **Admin Dashboard**: user management, role/permission overview, system-wide requests/reviews, full traceability
- **Reviewer Dashboard**: assigned review queue, case actions (approve/reject/request revision), ordered history
- **Contributor Dashboard**: my submissions, new change submission, correction/resubmission, own traceability

For all result-oriented views, full nested/raw details remain available in optional expanders.

### Run commands
#### Fresh clone setup (Windows PowerShell)
```powershell
git clone <your-repo-url>
cd <your-repo-folder>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[demo]
```

#### Fresh clone setup (macOS/Linux)
```bash
git clone <your-repo-url>
cd <your-repo-folder>
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[demo]
```

After editable install, the demo entrypoints are package-safe and should run on a clean clone **without manual import edits**.

Demo login users (seeded automatically on backend start):
- `admin` / `admin123` (Admin)
- `reviewer` / `review123` (Reviewer)
- `contributor` / `contrib123` (Contributor)

#### Run Streamlit demo UI
```bash
python -m streamlit run src/thesis_prototype/demo_ui.py
```

#### Run FastAPI demo server (optional)
```bash
uvicorn thesis_prototype.demo_api:app --reload
```

### Export formats in the UI
Each results-oriented tab supports downloads for the currently displayed dataset:
- CSV
- Excel (`.xlsx`)
- JSON
- PDF

PDF export is intentionally simple and optimized for readability/reproducibility (plain tabular text report), not visual styling.

### Supported now
- submit structured ontology changes
- trigger conflict detection and validation on stored changes
- run governance/review workflow actions (open case, assign reviewer, approve/reject/request revision, resubmit linked correction, inspect ordered history)
- inspect traceability/state in a readable registry summary view
- login/logout and role-based access control for dashboard data/actions
- admin-managed user creation, activation/deactivation, and role assignment

### Intentionally not yet implemented
- advanced governance policy/routing UI
- AI explanation generation UI
- full WebProtégé integration
- production-grade authentication, concurrency, and durability

### Governance demo limitations
- in-memory workflow persistence only
- simple single-reviewer assignment policy
- deterministic thesis-demo orchestration, not production governance infrastructure

### Auth/RBAC limitations
- no enterprise SSO, OAuth, or OpenID Connect
- no production-grade account recovery, MFA, or security monitoring
- no multi-tenant isolation

## 9) Defense-readiness note

The defense-stage suites are scenario-mapped to thesis requirements and are intended to support:
- **Chapter 5** implementation evidence (design decisions and behavior)
- **Chapter 6** evaluation evidence (test-backed claims and limitations)

## Seed/example usage

A small local fixture is available at:
- `examples/seed_data.py`

It seeds a linked in-memory chain for quick manual inspection and local experimentation.
