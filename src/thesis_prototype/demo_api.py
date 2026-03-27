from __future__ import annotations

from typing import Any, Dict, Optional

from .demo_backend import DemoBackend, to_jsonable


def create_demo_backend() -> DemoBackend:
    return DemoBackend()


def create_fastapi_app() -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise ImportError(
            "FastAPI demo dependencies are not installed. Install with: pip install fastapi uvicorn"
        ) from exc

    backend = create_demo_backend()
    app = FastAPI(title="Thesis Prototype Demo API", version="0.1.0")

    class ChangeCreateRequest(BaseModel):
        contributor_id: str
        affected_entity: str
        operation_type: str
        label: Optional[str] = None
        description: Optional[str] = None
        optional_note: Optional[str] = None
        scenario_id: Optional[str] = None
        revision_reference: Optional[str] = None
        proposed_values_extra: Dict[str, Any] = Field(default_factory=dict)

    class ConflictRequest(BaseModel):
        mode: str = "all"

    @app.post("/changes")
    def create_change(payload: ChangeCreateRequest):
        try:
            change = backend.create_change(**payload.model_dump())
            return to_jsonable(change)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/changes")
    def list_changes():
        return [to_jsonable(change) for change in backend.list_changes()]

    @app.get("/changes/{change_id}")
    def get_change(change_id: str):
        try:
            return to_jsonable(backend.get_change(change_id))
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/changes/{change_id}/detect-conflicts")
    def detect_conflicts(change_id: str, payload: ConflictRequest):
        try:
            return backend.detect_conflicts(change_id, mode=payload.mode)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/changes/{change_id}/validate")
    def validate_change(change_id: str):
        try:
            return backend.validate_change(change_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/changes/{change_id}/issues")
    def get_issues(change_id: str):
        try:
            return backend.get_issues_for_change(change_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/changes/{change_id}/validation-results")
    def get_validation_results(change_id: str):
        try:
            return backend.get_validation_results_for_change(change_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/registry/summary")
    def get_registry_summary():
        return backend.get_registry_summary()

    return app


app = None
try:  # pragma: no cover - import side effect only
    app = create_fastapi_app()
except ImportError:
    pass
