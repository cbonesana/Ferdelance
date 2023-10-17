"""Local plans are executed by each node. The objective of a plan is instruct a
node on how to train and evaluate a model."""

__all__ = [
    "LocalPlan",
    "Train",
    "TrainTestSplit",
    "LocalCrossValidation",
]


from .core import LocalPlan
from .train import Train
from .split import TrainTestSplit
from .cross_validation import LocalCrossValidation
