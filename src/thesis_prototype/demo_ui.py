from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from thesis_prototype.demo_backend import DemoBackend
from thesis_prototype.demo_exports import (
    export_csv_bytes,
    export_json_bytes,
    export_pdf_bytes,
    export_xlsx_bytes,
    normalize_records,
)
from thesis_prototype.models import OperationType


def _parse_json_input(raw: str) -> Dict[str, Any]:
    if not raw.strip():
        return {}
    return json.loads(raw)


def _render_download_buttons(st, records: Iterable[Dict[str, Any]], base_name: str, title: str) -> None:
    rows = normalize_records(records)
    if not rows:
        st.info("No data to export yet.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.download_button(
            "Export CSV",
            data=export_csv_bytes(rows),
            file_name=f"{base_name}_{timestamp}.csv",
            mime="text/csv",
        )
    with col2:
        try:
            xlsx_bytes = export_xlsx_bytes(rows, sheet_name=base_name)
            st.download_button(
                "Export Excel",
                data=xlsx_bytes,
                file_name=f"{base_name}_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except RuntimeError as exc:
            st.caption(str(exc))
    with col3:
        st.download_button(
            "Export JSON",
            data=export_json_bytes(rows),
            file_name=f"{base_name}_{timestamp}.json",
            mime="application/json",
        )
    with col4:
        try:
            pdf_bytes = export_pdf_bytes(rows, title=title)
            st.download_button(
                "Export PDF",
                data=pdf_bytes,
                file_name=f"{base_name}_{timestamp}.pdf",
                mime="application/pdf",
            )
        except RuntimeError as exc:
            st.caption(str(exc))


def _issue_rows(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for issue in issues:
        evidence = issue.get("evidence", {})
        rows.append(
            {
                "issue_id": issue.get("issue_id"),
                "originating_change_id": issue.get("originating_change_id"),
                "issue_category": issue.get("issue_category"),
                "severity": issue.get("severity"),
                "workflow_state": issue.get("current_workflow_state"),
                "summary": evidence.get("user_readable_description", ""),
                "evidence_summary": evidence.get("machine_code", ""),
                "created_at": issue.get("created_at", ""),
            }
        )
    return rows


def _validation_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for result in results:
        rows.append(
            {
                "validation_result_id": result.get("validation_result_id"),
                "change_id": result.get("change_id"),
                "rule_id": result.get("rule_id"),
                "rule_type": result.get("rule_type"),
                "status": result.get("status"),
                "target_node": result.get("target_node"),
                "affected_property_path": result.get("affected_property_path"),
                "message": result.get("user_readable_message", ""),
                "created_at": result.get("created_at", ""),
            }
        )
    return rows


def _review_case_rows(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for case in cases:
        rows.append(
            {
                "review_case_id": case.get("review_case_id"),
                "originating_change_id": case.get("originating_change_id"),
                "current_change_id": case.get("current_change_id"),
                "linked_issue_id": case.get("linked_issue_id"),
                "source_validation_result_id": case.get("source_validation_result_id", ""),
                "workflow_state": case.get("workflow_state"),
                "assigned_reviewer": case.get("assigned_reviewer", ""),
                "final_decision": case.get("final_decision", ""),
                "updated_at": case.get("updated_at", ""),
            }
        )
    return rows


def _history_rows(review_case_id: str, case: Dict[str, Any], history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for event in history:
        rows.append(
            {
                "review_case_id": review_case_id,
                "linked_change_id": case.get("current_change_id") or case.get("originating_change_id"),
                "linked_issue_id": case.get("linked_issue_id"),
                "linked_validation_result_id": case.get("source_validation_result_id", ""),
                "event_type": event.get("event_type"),
                "workflow_state": case.get("workflow_state"),
                "reviewer_id": event.get("actor_id"),
                "rationale_or_detail": event.get("detail"),
                "created_at": event.get("timestamp"),
            }
        )
    return rows


def run() -> None:
    try:
        import streamlit as st
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise ImportError("Streamlit is required. Install with: pip install streamlit") from exc

    if "backend" not in st.session_state:
        st.session_state.backend = DemoBackend()
    if "last_conflict_results" not in st.session_state:
        st.session_state.last_conflict_results = []
    if "last_validation_results" not in st.session_state:
        st.session_state.last_validation_results = []

    backend: DemoBackend = st.session_state.backend

    st.set_page_config(page_title="Thesis Prototype Demo", layout="wide")
    st.title("Thesis Prototype Demo UI")
    st.caption("T33 + T34 + T35 + T36 demo (change submission, conflict detection, validation, governance, traceability)")

    tab_submit, tab_conflicts, tab_validation, tab_governance, tab_registry = st.tabs(
        [
            "Change Submission",
            "Conflict Detection",
            "Validation",
            "Governance / Review",
            "Registry / Traceability",
        ]
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
                st.dataframe(normalize_records([backend.get_registry_summary()["changes"][-1]]), use_container_width=True)
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
                st.session_state.last_conflict_results = backend.detect_conflicts(change_id, mode=mode)

            issues = st.session_state.last_conflict_results
            issue_rows = _issue_rows(issues)
            if issue_rows:
                st.dataframe(normalize_records(issue_rows), use_container_width=True)
                _render_download_buttons(st, issue_rows, base_name=f"conflicts_{change_id}", title="Conflict Detection Results")
                with st.expander("Show full issue evidence"):
                    st.json(issues)
            else:
                st.info("No conflict issues detected for the selected change/mode.")

    with tab_validation:
        st.subheader("Run Validation")
        changes = backend.list_changes()
        if not changes:
            st.info("No changes available. Submit one in Change Submission first.")
        else:
            options = [c.change_id for c in changes]
            change_id = st.selectbox("Select Change ID", options, key="validation_change_id")
            if st.button("Run Validation"):
                st.session_state.last_validation_results = backend.validate_change(change_id)

            results = st.session_state.last_validation_results
            rows = _validation_rows(results)
            if rows:
                st.dataframe(normalize_records(rows), use_container_width=True)
                _render_download_buttons(st, rows, base_name=f"validation_{change_id}", title="Validation Results")
                with st.expander("Show full validation details"):
                    st.json(results)
            else:
                st.info("No validation results available yet. Run validation first.")

    with tab_governance:
        st.subheader("Governance / Review Workflow")

        # 1) Select reviewable item
        st.markdown("### 1) Select reviewable item")
        summary = backend.get_registry_summary()
        all_issues = []
        for issue_list in summary["issues_by_change"].values():
            all_issues.extend(issue_list)
        all_validation_results = []
        for val_list in summary["validation_by_change"].values():
            all_validation_results.extend(val_list)
        failed_validation_results = [v for v in all_validation_results if v.get("status") == "fail"]
        existing_cases = backend.list_review_cases()

        selectable_items: List[Dict[str, str]] = []
        for issue in all_issues:
            selectable_items.append(
                {
                    "label": f"Issue | {issue.get('issue_id')} | change={issue.get('originating_change_id')} | {issue.get('issue_category')}",
                    "type": "issue",
                    "id": issue.get("issue_id"),
                }
            )
        for result in failed_validation_results:
            selectable_items.append(
                {
                    "label": f"Failed Validation | {result.get('validation_result_id')} | change={result.get('change_id')} | {result.get('rule_id')}",
                    "type": "validation",
                    "id": result.get("validation_result_id"),
                }
            )
        for case in existing_cases:
            selectable_items.append(
                {
                    "label": f"Existing Case | {case.get('review_case_id')} | state={case.get('workflow_state')}",
                    "type": "case",
                    "id": case.get("review_case_id"),
                }
            )

        if not selectable_items:
            st.info("No reviewable items yet. Generate conflict issues or failed validations first.")
        else:
            option_map = {item["label"]: item for item in selectable_items}
            selected_label = st.selectbox("Choose item", list(option_map.keys()), key="governance_selector")
            selected = option_map[selected_label]

            selected_case = None
            if selected["type"] == "case":
                selected_case = backend.get_review_case(selected["id"])
            else:
                if st.button("Open Review Case"):
                    try:
                        if selected["type"] == "issue":
                            selected_case = backend.open_review_for_issue(selected["id"], actor_id="demo-user")
                        else:
                            selected_case = backend.open_review_for_failed_validation(selected["id"], actor_id="demo-user")
                        st.success(f"Opened review case: {selected_case['review_case_id']}")
                    except Exception as exc:
                        st.error(str(exc))

            if not selected_case and selected["type"] != "case":
                st.warning("Open a review case to continue with governance actions.")
            else:
                if not selected_case:
                    selected_case = backend.get_review_case(selected["id"])

                review_case_id = selected_case["review_case_id"]

                # 2) Review case summary
                st.markdown("### 2) Review case summary")
                approval_blocked = backend.is_approval_blocked(review_case_id)
                summary_row = {
                    "review_case_id": selected_case.get("review_case_id"),
                    "originating_change_id": selected_case.get("originating_change_id"),
                    "current_change_id": selected_case.get("current_change_id"),
                    "source_artifact_type": "validation_result" if selected_case.get("source_validation_result_id") else "issue",
                    "linked_issue_id": selected_case.get("linked_issue_id"),
                    "linked_validation_result_id": selected_case.get("source_validation_result_id", ""),
                    "assigned_reviewer": selected_case.get("assigned_reviewer", ""),
                    "workflow_state": selected_case.get("workflow_state"),
                    "final_outcome": selected_case.get("final_decision", ""),
                    "approval_blocked": approval_blocked,
                }
                st.dataframe(normalize_records([summary_row]), use_container_width=True)
                _render_download_buttons(
                    st,
                    [summary_row],
                    base_name=f"governance_case_summary_{review_case_id}",
                    title="Governance Case Summary",
                )

                # 3) Reviewer assignment
                st.markdown("### 3) Reviewer assignment")
                with st.form(f"assign_reviewer_{review_case_id}"):
                    reviewer_id = st.text_input("Reviewer ID", value=selected_case.get("assigned_reviewer") or "reviewer-1")
                    assign_clicked = st.form_submit_button("Assign / Reassign Reviewer")
                if assign_clicked:
                    try:
                        assigned = backend.assign_reviewer(review_case_id, reviewer_id, actor_id="demo-admin")
                        st.success(f"Reviewer assigned: {assigned.get('assigned_reviewer')}")
                    except Exception as exc:
                        st.error(str(exc))

                # 4) Decision actions
                st.markdown("### 4) Decision actions")
                rationale = st.text_area(
                    "Decision rationale",
                    value="",
                    key=f"decision_rationale_{review_case_id}",
                    help="Required for approve/reject/request revision.",
                )
                d1, d2, d3 = st.columns(3)
                with d1:
                    if st.button("Approve", key=f"approve_{review_case_id}"):
                        try:
                            backend.approve_review(review_case_id, selected_case.get("assigned_reviewer") or "", rationale)
                            st.success("Approval recorded.")
                        except Exception as exc:
                            st.error(str(exc))
                with d2:
                    if st.button("Reject", key=f"reject_{review_case_id}"):
                        try:
                            backend.reject_review(review_case_id, selected_case.get("assigned_reviewer") or "", rationale)
                            st.success("Rejection recorded.")
                        except Exception as exc:
                            st.error(str(exc))
                with d3:
                    if st.button("Request Revision", key=f"request_revision_{review_case_id}"):
                        try:
                            backend.request_review_revision(review_case_id, selected_case.get("assigned_reviewer") or "", rationale)
                            st.success("Revision request recorded.")
                        except Exception as exc:
                            st.error(str(exc))

                # 5) Resubmission
                st.markdown("### 5) Resubmission")
                with st.form(f"resubmit_form_{review_case_id}"):
                    c_contributor = st.text_input("Contributor ID", value="demo-user", key=f"resub_contrib_{review_case_id}")
                    c_entity = st.text_input("Affected Entity", value="Disease", key=f"resub_entity_{review_case_id}")
                    c_operation = st.selectbox(
                        "Operation Type",
                        [op.value for op in OperationType],
                        index=1,
                        key=f"resub_op_{review_case_id}",
                    )
                    c_label = st.text_input("Corrected Label", value="Heart Disease", key=f"resub_label_{review_case_id}")
                    c_desc = st.text_area(
                        "Corrected Description",
                        value="Disease affecting the heart.",
                        key=f"resub_desc_{review_case_id}",
                    )
                    c_extra = st.text_area(
                        "Additional proposed_values JSON (optional)",
                        value='{"property":"hasSymptom","domain":"Disease","range":"Symptom"}',
                        key=f"resub_extra_{review_case_id}",
                    )
                    submit_resub = st.form_submit_button("Submit Corrected Change & Link Resubmission")

                if submit_resub:
                    try:
                        revised = backend.create_change(
                            contributor_id=c_contributor,
                            affected_entity=c_entity,
                            operation_type=c_operation,
                            label=c_label or None,
                            description=c_desc or None,
                            proposed_values_extra=_parse_json_input(c_extra),
                        )
                        updated = backend.resubmit_review_case(
                            review_case_id=review_case_id,
                            revised_change_id=revised.change_id,
                            actor_id=c_contributor,
                        )
                        st.success(
                            f"Resubmitted with revised change {revised.change_id}; linked to case {updated['review_case_id']}"
                        )
                        if st.button("Return case to UNDER_REVIEW", key=f"return_under_review_{review_case_id}"):
                            backend.return_case_to_review(review_case_id, actor_id="demo-admin")
                            st.success("Case moved to UNDER_REVIEW.")
                    except Exception as exc:
                        st.error(str(exc))

                # 6) Review history
                st.markdown("### 6) Review history")
                refreshed_case = backend.get_review_case(review_case_id)
                history = backend.get_review_history(review_case_id)
                history_table = _history_rows(review_case_id, refreshed_case, history)
                if history_table:
                    st.dataframe(normalize_records(history_table), use_container_width=True)
                    _render_download_buttons(
                        st,
                        history_table,
                        base_name=f"governance_history_{review_case_id}",
                        title="Governance Review History",
                    )
                else:
                    st.info("No review history available yet.")
                with st.expander("Show full governance case and history details"):
                    st.json({"case": refreshed_case, "history": history})

    with tab_registry:
        st.subheader("Registry / Traceability")
        summary = backend.get_registry_summary()

        st.markdown("### All changes")
        changes_rows = summary["changes"]
        if changes_rows:
            st.dataframe(normalize_records(changes_rows), use_container_width=True)
            _render_download_buttons(st, changes_rows, base_name="registry_changes", title="Registry Changes")
        else:
            st.info("No changes stored yet.")

        st.markdown("### Issues by change")
        issues_rows: List[Dict[str, Any]] = []
        for chg_id, issues in summary["issues_by_change"].items():
            for issue in _issue_rows(issues):
                issue["change_group"] = chg_id
                issues_rows.append(issue)
        if issues_rows:
            st.dataframe(normalize_records(issues_rows), use_container_width=True)
            _render_download_buttons(st, issues_rows, base_name="registry_issues", title="Registry Issues")
        else:
            st.info("No issues stored yet.")

        st.markdown("### Validation results by change")
        validation_rows: List[Dict[str, Any]] = []
        for chg_id, results in summary["validation_by_change"].items():
            for row in _validation_rows(results):
                row["change_group"] = chg_id
                validation_rows.append(row)
        if validation_rows:
            st.dataframe(normalize_records(validation_rows), use_container_width=True)
            _render_download_buttons(st, validation_rows, base_name="registry_validation", title="Registry Validation")
        else:
            st.info("No validation results stored yet.")

        with st.expander("Show raw traceability JSON details"):
            st.json(summary)


if __name__ == "__main__":  # pragma: no cover
    run()
