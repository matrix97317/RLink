# -*- coding: utf-8 -*-
"""RLink Learner Tests."""

from typing import Any, Dict
from rlinks.learner import RLinkLearner
from rlinks.learner import RLinkSyncModel


def test_learner():
    """Test Learner Initialization."""
    learner = RLinkLearner(data_callback=None, port=8443)
    RLinkSyncModel.sync("/root/workspace/RLink/TTT.txt")
    assert learner is not None
    learner.serve_forever()


if __name__ == "__main__":
    test_learner()
    print("All tests passed.")
