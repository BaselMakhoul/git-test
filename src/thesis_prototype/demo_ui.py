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
from thesis_prototype.permissions import Role


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
    cols = st.columns(4)
    with cols[0]:
        st.download_button("Export CSV", export_csv_bytes(rows), f"{base_name}_{timestamp}.csv", "text/csv")
    with cols[1]:
        try:
            st.download_button(
                "Export Excel",
                export_xlsx_bytes(rows, sheet_name=base_name),
                f"{base_name}_{timestamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except RuntimeError as exc:
            st.caption(str(exc))
    with cols[2]:
        st.download_button("Export JSON", export_json_bytes(rows), f"{base_name}_{timestamp}.json", "application/json")
    with cols[3]:
        try:
            st.download_button("Export PDF", export_pdf_bytes(rows, title=title), f"{base_name}_{timestamp}.pdf", "application/pdf")
        except RuntimeError as exc:
            st.caption(str(exc))


def _issue_rows(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "issue_id": i.get("issue_id"),
            "change_id": i.get("originating_change_id"),
            "category": i.get("issue_category"),
            "severity": i.get("severity"),
            "workflow_state": i.get("current_workflow_state"),
            "summary": i.get("evidence", {}).get("user_readable_description", ""),
            "assigned_reviewer": i.get("assigned_reviewer", ""),
        }
        for i in issues
    ]


def _validation_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "validation_result_id": r.get("validation_result_id"),
            "change_id": r.get("change_id"),
            "rule_id": r.get("rule_id"),
            "rule_type": r.get("rule_type"),
            "status": r.get("status"),
            "target_node": r.get("target_node"),
            "message": r.get("user_readable_message"),
        }
        for r in results
    ]


def _review_case_rows(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "review_case_id": c.get("review_case_id"),
            "originating_change_id": c.get("originating_change_id"),
            "linked_issue_id": c.get("linked_issue_id"),
            "source_validation_result_id": c.get("source_validation_result_id", ""),
            "workflow_state": c.get("workflow_state"),
            "assigned_reviewer": c.get("assigned_reviewer", ""),
            "final_decision": c.get("final_decision", ""),
        }
        for c in cases
    ]


def _history_rows(case: Dict[str, Any], history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "review_case_id": case.get("review_case_id"),
            "linked_change_id": case.get("current_change_id") or case.get("originating_change_id"),
            "linked_issue_id": case.get("linked_issue_id"),
            "event_type": e.get("event_type"),
            "workflow_state": case.get("workflow_state"),
            "reviewer_id": e.get("actor_id"),
            "detail": e.get("detail"),
            "created_at": e.get("timestamp"),
        }
        for e in history
    ]


def _login_view(st, backend: DemoBackend) -> None:
    st.subheader("Login")
    st.caption("Demo credentials: admin/admin123, reviewer/review123, contributor/contrib123")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        clicked = st.form_submit_button("Login")
    if clicked:
        try:
            user = backend.login(username, password)
            st.session_state.current_user = user
            st.success(f"Logged in as {user['display_name']} ({user['role']})")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_admin_dashboard(st, backend: DemoBackend, current_user: Dict[str, Any]) -> None:
    st.header("Admin Dashboard")
    summary = backend.get_registry_summary(actor_user_id=current_user["user_id"])
    cases = backend.list_review_cases(actor_user_id=current_user["user_id"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", len(backend.list_users(current_user["user_id"])))
    c2.metric("Changes", len(summary["changes"]))
    c3.metric("Issues", sum(len(v) for v in summary["issues_by_change"].values()))
    c4.metric("Review Cases", len(cases))

    tab_users, tab_roles, tab_requests, tab_trace = st.tabs(
        ["Users", "Roles & Permissions", "All Requests/Reviews", "Registry / Traceability"]
    )

    with tab_users:
        st.subheader("Create User")
        with st.form("create_user_form"):
            username = st.text_input("Username")
            display_name = st.text_input("Display Name")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", [r.value for r in Role])
            active = st.checkbox("Active", value=True)
            create_btn = st.form_submit_button("Create User")
        if create_btn:
            try:
                backend.create_user(current_user["user_id"], username, password, display_name, role, active)
                st.success("User created")
            except Exception as exc:
                st.error(str(exc))

        users = backend.list_users(current_user["user_id"])
        user_rows = [
            {
                "user_id": u["user_id"],
                "username": u["username"],
                "display_name": u["display_name"],
                "role": u["role"],
                "active": u["active"],
                "created_at": u["created_at"],
            }
            for u in users
        ]
        st.dataframe(normalize_records(user_rows), use_container_width=True)
        _render_download_buttons(st, user_rows, "admin_users", "Admin Users")

        with st.form("manage_user_form"):
            user_options = {f"{u['username']} ({u['role']})": u for u in users}
            selected = st.selectbox("Select user", list(user_options.keys()))
            new_role = st.selectbox("Assign role", [r.value for r in Role], key="admin_assign_role")
            new_active = st.checkbox("Active", value=user_options[selected]["active"])
            apply_btn = st.form_submit_button("Apply Updates")
        if apply_btn:
            target = user_options[selected]
            try:
                backend.assign_user_role(current_user["user_id"], target["user_id"], new_role)
                backend.set_user_active(current_user["user_id"], target["user_id"], new_active)
                st.success("User updated")
            except Exception as exc:
                st.error(str(exc))

    with tab_roles:
        overview = backend.permissions_overview()
        rows = [{"role": role, "permissions": ", ".join(perms)} for role, perms in overview.items()]
        st.dataframe(normalize_records(rows), use_container_width=True)

    with tab_requests:
        st.markdown("**All Changes**")
        st.dataframe(normalize_records(summary["changes"]))
        st.markdown("**All Review Cases**")
        case_rows = _review_case_rows(cases)
        st.dataframe(normalize_records(case_rows), use_container_width=True)
        _render_download_buttons(st, case_rows, "admin_review_cases", "Admin Review Cases")

    with tab_trace:
        issue_rows = []
        validation_rows = []
        for _, issues in summary["issues_by_change"].items():
            issue_rows.extend(_issue_rows(issues))
        for _, vals in summary["validation_by_change"].items():
            validation_rows.extend(_validation_rows(vals))
        st.markdown("**Issues**")
        st.dataframe(normalize_records(issue_rows), use_container_width=True)
        st.markdown("**Validation Results**")
        st.dataframe(normalize_records(validation_rows), use_container_width=True)


def _render_reviewer_dashboard(st, backend: DemoBackend, current_user: Dict[str, Any]) -> None:
    st.header("Reviewer Dashboard")
    user_id = current_user["user_id"]
    cases = backend.list_review_cases(actor_user_id=user_id)
    case_rows = _review_case_rows(cases)

    st.markdown("### Assigned Reviews")
    st.dataframe(normalize_records(case_rows), use_container_width=True)
    _render_download_buttons(st, case_rows, "reviewer_assigned_cases", "Assigned Review Cases")

    if not cases:
        st.info("No cases assigned.")
        return

    options = {f"{c['review_case_id']} | {c['workflow_state']}": c for c in cases}
    selected_label = st.selectbox("Select case", list(options.keys()))
    case = options[selected_label]
    review_case_id = case["review_case_id"]

    st.markdown("### Case Detail / Action")
    summary_row = {
        "review_case_id": case.get("review_case_id"),
        "originating_change_id": case.get("originating_change_id"),
        "linked_issue_id": case.get("linked_issue_id"),
        "workflow_state": case.get("workflow_state"),
        "assigned_reviewer": case.get("assigned_reviewer"),
        "approval_blocked": backend.is_approval_blocked(review_case_id),
    }
    st.dataframe(normalize_records([summary_row]), use_container_width=True)

    rationale = st.text_area("Rationale", key=f"reviewer_rationale_{review_case_id}")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve", key=f"reviewer_approve_{review_case_id}"):
            try:
                backend.approve_review(review_case_id, current_user["user_id"], rationale, actor_user_id=current_user["user_id"])
                st.success("Approved")
            except Exception as exc:
                st.error(str(exc))
    with c2:
        if st.button("Reject", key=f"reviewer_reject_{review_case_id}"):
            try:
                backend.reject_review(review_case_id, current_user["user_id"], rationale, actor_user_id=current_user["user_id"])
                st.success("Rejected")
            except Exception as exc:
                st.error(str(exc))
    with c3:
        if st.button("Request Revision", key=f"reviewer_revision_{review_case_id}"):
            try:
                backend.request_review_revision(
                    review_case_id, current_user["user_id"], rationale, actor_user_id=current_user["user_id"]
                )
                st.success("Revision requested")
            except Exception as exc:
                st.error(str(exc))

    st.markdown("### Review History")
    history = backend.get_review_history(review_case_id)
    history_rows = _history_rows(case, history)
    st.dataframe(normalize_records(history_rows), use_container_width=True)
    _render_download_buttons(st, history_rows, f"reviewer_history_{review_case_id}", "Reviewer History")


def _render_contributor_dashboard(st, backend: DemoBackend, current_user: Dict[str, Any]) -> None:
    st.header("Contributor Dashboard")
    user_id = current_user["user_id"]

    tab_my, tab_submit, tab_resubmit, tab_trace = st.tabs(
        ["My Contributions", "Submit Change", "Correction / Resubmission", "Registry / Traceability"]
    )

    my_changes = [to for to in backend.get_registry_summary(actor_user_id=user_id)["changes"]]

    with tab_my:
        st.dataframe(normalize_records(my_changes), use_container_width=True)
        _render_download_buttons(st, my_changes, "contributor_changes", "Contributor Changes")

        if my_changes:
            options = {f"{c['change_id']} | {c['affected_entity']}": c for c in my_changes}
            selected = st.selectbox("Recall eligible change", list(options.keys()))
            if st.button("Recall Request"):
                try:
                    result = backend.recall_change(options[selected]["change_id"], actor_user_id=user_id)
                    st.success(f"Request recalled: {result['change_id']}")
                except Exception as exc:
                    st.warning(str(exc))

    with tab_submit:
        with st.form("contributor_submit_form"):
            affected_entity = st.text_input("Affected Entity", value="Disease")
            op = st.selectbox("Operation Type", [o.value for o in OperationType], index=1)
            label = st.text_input("Label", value="Heart Disease")
            description = st.text_area("Description", value="Disease affecting the heart")
            extra = st.text_area("Additional proposed_values JSON", value="{}")
            submit = st.form_submit_button("Submit Change")
        if submit:
            try:
                change = backend.create_change(
                    contributor_id=current_user["user_id"],
                    affected_entity=affected_entity,
                    operation_type=op,
                    label=label,
                    description=description,
                    proposed_values_extra=_parse_json_input(extra),
                    actor_user_id=current_user["user_id"],
                )
                st.success(f"Submitted change {change.change_id}")
            except Exception as exc:
                st.error(str(exc))

    with tab_resubmit:
        cases = backend.list_review_cases(actor_user_id=user_id)
        rev_cases = [c for c in cases if c.get("workflow_state") == "revision_requested"]
        if not rev_cases:
            st.info("No revision-requested cases available.")
        else:
            options = {f"{c['review_case_id']} | {c['originating_change_id']}": c for c in rev_cases}
            chosen = st.selectbox("Select review case", list(options.keys()))
            case = options[chosen]
            with st.form(f"contrib_resubmit_{case['review_case_id']}"):
                label = st.text_input("Corrected Label", value="Heart Disease")
                desc = st.text_area("Corrected Description", value="Disease of heart")
                submit_resub = st.form_submit_button("Submit Correction")
            if submit_resub:
                try:
                    revised = backend.create_change(
                        contributor_id=current_user["user_id"],
                        affected_entity="Disease",
                        operation_type="update",
                        label=label,
                        description=desc,
                        actor_user_id=current_user["user_id"],
                    )
                    backend.resubmit_review_case(
                        case["review_case_id"],
                        revised.change_id,
                        actor_id=current_user["user_id"],
                        actor_user_id=current_user["user_id"],
                    )
                    st.success(f"Resubmitted revised change {revised.change_id}")
                except Exception as exc:
                    st.error(str(exc))

    with tab_trace:
        summary = backend.get_registry_summary(actor_user_id=user_id)
        rows = []
        for _, issues in summary["issues_by_change"].items():
            rows.extend(_issue_rows(issues))
        st.markdown("**My Issues**")
        st.dataframe(normalize_records(rows), use_container_width=True)


def run() -> None:
    try:
        import streamlit as st
    except Exception as exc:  # pragma: no cover
        raise ImportError("Streamlit is required. Install with: pip install streamlit") from exc

    if "backend" not in st.session_state:
        st.session_state.backend = DemoBackend()
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    backend: DemoBackend = st.session_state.backend

    st.set_page_config(page_title="Thesis Prototype Demo", layout="wide")
    st.title("Thesis Prototype Demo UI")

    if not st.session_state.current_user:
        _login_view(st, backend)
        return

    current_user = st.session_state.current_user
    top1, top2, top3 = st.columns([2, 2, 1])
    top1.info(f"Logged in as: **{current_user['display_name']}**")
    top2.info(f"Role: **{current_user['role']}**")
    if top3.button("Logout"):
        st.session_state.current_user = None
        st.rerun()

    role = current_user["role"]
    if role == Role.ADMIN.value:
        _render_admin_dashboard(st, backend, current_user)
    elif role == Role.REVIEWER.value:
        _render_reviewer_dashboard(st, backend, current_user)
    else:
        _render_contributor_dashboard(st, backend, current_user)


if __name__ == "__main__":  # pragma: no cover
    run()
