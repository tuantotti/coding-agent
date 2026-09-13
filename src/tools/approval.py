"""Argument schemas for the built-in tools that require human approval."""

from deepagents.middleware.filesystem import (
    DeleteSchema,
    EditFileSchema,
    ExecuteSchema,
    WriteFileSchema,
)

from src.models.runs import PendingApproval

_TOOL_SCHEMAS = {
    "write_file": WriteFileSchema,
    "edit_file": EditFileSchema,
    "delete": DeleteSchema,
    "execute": ExecuteSchema,
}


def include_argument_schemas(approval: PendingApproval) -> PendingApproval:
    """Fill schemas omitted by the pinned LangChain HITL middleware."""
    for config in approval.review_configs:
        if config.args_schema is None:
            schema = _TOOL_SCHEMAS.get(config.action_name)
            if schema is not None:
                config.args_schema = schema.model_json_schema()
            else:
                # Unknown tool arguments cannot be validated, so fail closed.
                config.allowed_decisions = [
                    item for item in config.allowed_decisions if item != "edit"
                ]
    return approval
