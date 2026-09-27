"""Load SWE-bench rows while preventing gold-data leakage."""

import re
from collections.abc import Callable, Iterable, Mapping

from pydantic import ValidationError

from benchmarks.swebench.config import BenchmarkConfig
from benchmarks.swebench.models import BenchmarkInstance, DatasetSelection

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_INSTANCE = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class DatasetError(ValueError):
    """The benchmark dataset or requested selection is invalid."""


def _default_loader(name: str, *, split: str, revision: str | None):
    from datasets import load_dataset

    return load_dataset(name, split=split, revision=revision)


def _default_revision(name: str, revision: str | None) -> str:
    from huggingface_hub import HfApi

    sha = HfApi().dataset_info(name, revision=revision).sha
    if not sha:
        raise DatasetError("Hugging Face did not return a dataset revision.")
    return sha


def _project(row: Mapping[str, object]) -> BenchmarkInstance:
    allowed = {
        key: row.get(key)
        for key in ("instance_id", "repo", "base_commit", "problem_statement")
    }
    try:
        instance = BenchmarkInstance.model_validate(allowed)
    except ValidationError as exc:
        raise DatasetError("Dataset row is missing a required public field.") from exc
    if not _INSTANCE.fullmatch(instance.instance_id):
        raise DatasetError(f"Invalid instance_id: {instance.instance_id}")
    if not _REPO.fullmatch(instance.repo):
        raise DatasetError(f"Invalid repository name: {instance.repo}")
    if not _COMMIT.fullmatch(instance.base_commit):
        raise DatasetError(f"Invalid base commit for {instance.instance_id}.")
    return instance


def load_instances(
    config: BenchmarkConfig,
    *,
    load_dataset_fn: Callable[..., Iterable[Mapping[str, object]]] | None = None,
    dataset_info_fn: Callable[[str, str | None], str] | None = None,
) -> DatasetSelection:
    """Load, project, pin, and filter benchmark instances."""
    loader = load_dataset_fn or _default_loader
    revision_lookup = dataset_info_fn or _default_revision
    try:
        resolved_revision = revision_lookup(
            config.dataset_name, config.dataset_revision
        )
        if not isinstance(resolved_revision, str) or not _COMMIT.fullmatch(
            resolved_revision
        ):
            raise DatasetError(
                "Resolved dataset revision must be an immutable commit SHA."
            )
        rows = loader(
            config.dataset_name,
            split=config.split,
            revision=resolved_revision,
        )
        projected = tuple(_project(row) for row in rows)
    except DatasetError:
        raise
    except Exception as exc:
        raise DatasetError("Unable to load the SWE-bench dataset.") from exc

    by_id: dict[str, BenchmarkInstance] = {}
    for instance in projected:
        if instance.instance_id in by_id:
            raise DatasetError(f"Duplicate instance_id: {instance.instance_id}")
        by_id[instance.instance_id] = instance

    if config.all_instances:
        selected = projected
    else:
        missing = [item for item in config.instance_ids if item not in by_id]
        if missing:
            raise DatasetError(f"Requested instances not found: {', '.join(missing)}")
        selected = tuple(by_id[item] for item in config.instance_ids)

    return DatasetSelection(
        dataset_name=config.dataset_name,
        split=config.split,
        requested_revision=config.dataset_revision,
        resolved_revision=resolved_revision,
        instances=selected,
    )
