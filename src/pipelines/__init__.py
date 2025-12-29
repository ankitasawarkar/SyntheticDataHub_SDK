from typing import Dict, Any

from .base import Pipeline

_PIPELINES: Dict[str, Pipeline] = {}


def register_pipeline(pipeline: Pipeline) -> None:
    """Register a concrete pipeline implementation under its name."""
    _PIPELINES[pipeline.name] = pipeline


def get_pipeline_names() -> list[str]:
    """Return sorted list of registered pipeline names."""
    return sorted(_PIPELINES.keys())


def run_pipeline(name: str, **kwargs: Any) -> None:
    """Run the named pipeline with the provided keyword arguments."""
    try:
        pipeline = _PIPELINES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline '{name}'") from exc
    pipeline.run(**kwargs)
