import pytest

from thesis_prototype.auth_service import AuthService
from thesis_prototype.demo_backend import DemoBackend
from thesis_prototype.permissions import Role


def test_user_creation_and_password_hashing_verification() -> None:
    auth = AuthService()
    user = auth.create_user("alice", "pass1234", "Alice", Role.CONTRIBUTOR)
    assert "pass1234" not in user.password_hash
    assert auth.verify_password("pass1234", user.password_hash)


def test_login_success_and_failure() -> None:
    backend = DemoBackend()
    ok = backend.login("admin", "admin123")
    assert ok["role"] == "admin"

    with pytest.raises(PermissionError):
        backend.login("admin", "wrong")


def test_role_assignment_and_permission_enforcement() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    reviewer = backend.login("reviewer", "review123")

    created = backend.create_user(admin["user_id"], "temp", "temp1234", "Temp", "contributor")
    backend.assign_user_role(admin["user_id"], created["user_id"], "reviewer")

    with pytest.raises(PermissionError):
        backend.list_users(reviewer["user_id"])


def test_contributor_sees_only_own_requests_and_reviewer_only_assigned() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    contributor = backend.login("contributor", "contrib123")
    reviewer = backend.login("reviewer", "review123")

    c_change = backend.create_change(
        contributor_id=contributor["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="heart_disease",
        description="",
        actor_user_id=contributor["user_id"],
    )
    backend.validate_change(c_change.change_id)
    failed = next(r for r in backend.get_validation_results_for_change(c_change.change_id) if r["status"] == "fail")
    case = backend.open_review_for_failed_validation(failed["validation_result_id"])
    backend.assign_reviewer(case["review_case_id"], reviewer["user_id"], actor_id=admin["user_id"])

    contributor_changes = backend.list_changes(actor_user_id=contributor["user_id"])
    assert all(ch.contributor_id == contributor["user_id"] for ch in contributor_changes)

    reviewer_cases = backend.list_review_cases(actor_user_id=reviewer["user_id"])
    assert all(c["assigned_reviewer"] == reviewer["user_id"] for c in reviewer_cases)


def test_admin_can_view_all_users_and_cases() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    users = backend.list_users(admin["user_id"])
    cases = backend.list_review_cases(actor_user_id=admin["user_id"])
    assert len(users) >= 3
    assert isinstance(cases, list)


def test_unauthorized_case_action_fails() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    contributor = backend.login("contributor", "contrib123")
    reviewer = backend.login("reviewer", "review123")

    change = backend.create_change(
        contributor_id=contributor["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="heart_disease",
        description="",
        actor_user_id=contributor["user_id"],
    )
    backend.validate_change(change.change_id)
    failed = next(r for r in backend.get_validation_results_for_change(change.change_id) if r["status"] == "fail")
    case = backend.open_review_for_failed_validation(failed["validation_result_id"])
    backend.assign_reviewer(case["review_case_id"], reviewer["user_id"], actor_id=admin["user_id"])

    with pytest.raises(PermissionError):
        backend.approve_review(
            case["review_case_id"],
            reviewer_id=reviewer["user_id"],
            rationale="x",
            actor_user_id=contributor["user_id"],
        )


def test_recall_and_resubmit_permissions() -> None:
    backend = DemoBackend()
    contributor = backend.login("contributor", "contrib123")
    reviewer = backend.login("reviewer", "review123")

    change = backend.create_change(
        contributor_id=contributor["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="Heart Disease",
        description="Disease of heart",
        actor_user_id=contributor["user_id"],
    )

    backend.recall_change(change.change_id, actor_user_id=contributor["user_id"])
    assert all(c.change_id != change.change_id for c in backend.list_changes(actor_user_id=contributor["user_id"]))

    with pytest.raises(PermissionError):
        backend.recall_change(change.change_id, actor_user_id=reviewer["user_id"])


def test_reviewer_cannot_act_on_unassigned_case() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    contributor = backend.login("contributor", "contrib123")
    assigned_reviewer = backend.login("reviewer", "review123")
    other = backend.create_user(admin["user_id"], "rev2", "review1234", "Reviewer Two", "reviewer")

    change = backend.create_change(
        contributor_id=contributor["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="heart_disease",
        description="",
        actor_user_id=contributor["user_id"],
    )
    backend.validate_change(change.change_id)
    failed = next(r for r in backend.get_validation_results_for_change(change.change_id) if r["status"] == "fail")
    case = backend.open_review_for_failed_validation(failed["validation_result_id"])
    backend.assign_reviewer(case["review_case_id"], assigned_reviewer["user_id"], actor_id=admin["user_id"])

    with pytest.raises(PermissionError):
        backend.approve_review(
            case["review_case_id"],
            reviewer_id=other["user_id"],
            rationale="not assigned",
            actor_user_id=other["user_id"],
        )


def test_contributor_resubmit_only_on_own_revision_requested_case() -> None:
    backend = DemoBackend()
    admin = backend.login("admin", "admin123")
    contributor = backend.login("contributor", "contrib123")
    reviewer = backend.login("reviewer", "review123")
    other = backend.create_user(admin["user_id"], "alice", "alice1234", "Alice", "contributor")

    change = backend.create_change(
        contributor_id=contributor["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="heart_disease",
        description="",
        actor_user_id=contributor["user_id"],
    )
    backend.validate_change(change.change_id)
    failed = next(r for r in backend.get_validation_results_for_change(change.change_id) if r["status"] == "fail")
    case = backend.open_review_for_failed_validation(failed["validation_result_id"])
    backend.assign_reviewer(case["review_case_id"], reviewer["user_id"], actor_id=admin["user_id"])
    backend.request_review_revision(
        case["review_case_id"],
        reviewer_id=reviewer["user_id"],
        rationale="needs revision",
        actor_user_id=reviewer["user_id"],
    )

    revised = backend.create_change(
        contributor_id=other["user_id"],
        affected_entity="Disease",
        operation_type="update",
        label="new_label",
        description="new desc",
        actor_user_id=other["user_id"],
    )
    with pytest.raises(PermissionError):
        backend.resubmit_review_case(
            case["review_case_id"],
            revised.change_id,
            actor_id=other["user_id"],
            actor_user_id=other["user_id"],
        )
