from __future__ import annotations

import json
from typing import Any, Dict

from .demo_backend import DemoBackend
from .models import OperationType


def _parse_json_input(raw: str) -> Dict[str, Any]:
    if not raw.strip():
        return {}
    return json.loads(raw)


def run() -> None:
    try:
        import streamlit as st
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise ImportError("Streamlit is required. Install with: pip install streamlit") from exc

    if "backend" not in st.session_state:
        st.session_state.backend = DemoBackend()

    backend: DemoBackend = st.session_state.backend

    st.set_page_config(page_title="Thesis Prototype Demo", layout="wide")
    st.title("Thesis Prototype Demo UI")
    st.caption("T33 + T34 + T35 demo (change submission, conflict detection, validation, traceability)")

    tab_submit, tab_conflicts, tab_validation, tab_registry = st.tabs(
        ["Change Submission", "Conflict Detection", "Validation", "Registry / Traceability"]
    )

    with tab_submit:
        st.subheader("Submit Ontology Change")
        with st.form("change_form"):
            contributor_id = st.text_input("Contributor ID", value="demo-user")
            affected_entity = st.text_input("Affected Entity", value="Disease")
            operation_type = st.selectbox("Operation Type", [op.value for op in OperationType], index=1)
            label = st.text_input("Label", value="Heart Disease")
            description = st.text_area("Description", value="Disease affecting the heart.")
            optional_note = st.text_input("Optional Note", value="")
            scenario_id = st.text_input("Scenario ID (optional)", value="")
            revision_reference = st.text_input("Revision Reference (optional)", value="")
            extra_values_raw = st.text_area(
                "Additional proposed_values JSON (optional)",
                value='{"property":"hasSymptom","domain":"Disease","range":"Symptom"}',
            )
            submitted = st.form_submit_button("Create & Store Change")

        if submitted:
            try:
                change = backend.create_change(
                    contributor_id=contributor_id,
                    affected_entity=affected_entity,
                    operation_type=operation_type,
                    label=label or None,
                    description=description or None,
                    optional_note=optional_note or None,
                    scenario_id=scenario_id or None,
                    revision_reference=revision_reference or None,
                    proposed_values_extra=_parse_json_input(extra_values_raw),
                )
                st.success(f"Created change: {change.change_id}")
                st.json(backend.get_registry_summary()["changes"][-1])
            except Exception as exc:
                st.error(str(exc))

    with tab_conflicts:
        st.subheader("Run Conflict Detection")
        changes = backend.list_changes()
        if not changes:
            st.info("No changes available. Submit one in Change Submission first.")
        else:
            options = [c.change_id for c in changes]
            change_id = st.selectbox("Select Change ID", options, key="conflict_change_id")
            mode = st.radio("Detection mode", ["direct", "near", "overlap", "all"], horizontal=True)
            if st.button("Run Conflict Detection"):
                issues = backend.detect_conflicts(change_id, mode=mode)
                st.write(f"Detected issues: {len(issues)}")
                st.json(issues)

    with tab_validation:
        st.subheader("Run Validation")
        changes = backend.list_changes()
        if not changes:
            st.info("No changes available. Submit one in Change Submission first.")
        else:
            options = [c.change_id for c in changes]
            change_id = st.selectbox("Select Change ID", options, key="validation_change_id")
            if st.button("Run Validation"):
                results = backend.validate_change(change_id)
                st.write(f"Validation results: {len(results)}")
                st.json(results)

    with tab_registry:
        st.subheader("Registry / Traceability")
        summary = backend.get_registry_summary()
        st.markdown("**All changes**")
        st.json(summary["changes"])
        st.markdown("**Issues by change**")
        st.json(summary["issues_by_change"])
        st.markdown("**Validation results by change**")
        st.json(summary["validation_by_change"])
        st.markdown("**Issue history**")
        st.json(summary["history_by_issue"])


if __name__ == "__main__":  # pragma: no cover
    run()
