"""Pipeline execution abstractions for MEDIMG.

Provides a simple pipeline interface that future modules can extend
for chaining processing steps.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PipelineStep:
    """A single named step in a processing pipeline."""

    def __init__(self, name: str, func: Callable[..., Any], **kwargs: Any) -> None:
        self.name = name
        self.func = func
        self.kwargs = kwargs

    def execute(self, *args: Any) -> Any:
        logger.info("Executing pipeline step: %s", self.name)
        return self.func(*args, **self.kwargs)


class Pipeline:
    """Simple sequential pipeline for composing processing steps.

    Example usage::

        pipeline = Pipeline("anonymize-workflow")
        pipeline.add_step("scan_phi", scan_phi_func, dataset=ds)
        pipeline.add_step("anonymize", anonymize_func, config=cfg)
        pipeline.add_step("verify", verify_func)
        results = pipeline.run(input_data)
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.steps: list[PipelineStep] = []

    def add_step(self, name: str, func: Callable[..., Any], **kwargs: Any) -> Pipeline:
        """Add a step to the pipeline. Returns self for chaining."""
        self.steps.append(PipelineStep(name, func, **kwargs))
        return self

    def run(self, initial_input: Any = None) -> Any:
        """Execute all steps sequentially, passing each output to the next."""
        logger.info("Running pipeline: %s (%d steps)", self.name, len(self.steps))
        result = initial_input
        for step in self.steps:
            result = step.execute(result)
        logger.info("Pipeline '%s' completed.", self.name)
        return result
