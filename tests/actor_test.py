# -*- coding: utf-8 -*-
"""RLink Actor Tests."""

import time

import numpy as np

from rlinks.actor import RLinkActor


def test_actor():
    """Test Actor Initialization."""
    actor = RLinkActor("http://172.17.0.2:8443")
    assert actor is not None
    data = {
        "top_image": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "top_image1": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "top_image2": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "action": np.random.randint((50, 14)).astype(np.float32),
        "index": 0,
    }
    for i in range(4):
        s = time.perf_counter()
        data["index"] = i
        actor.put(data)
        e = time.perf_counter()
        print(f"Sent data {i+1}/5, time taken: {(e-s)*1000:.4f} ms")
    models = actor.get_remote_model()
    print(f"Received model path: {models}")


if __name__ == "__main__":
    test_actor()
    print("All tests passed.")
