# -*- coding: utf-8 -*-
"""RLink torch loader Tests."""

import mmap
import time

import posix_ipc

from torch.utils.data import Dataset
from torch.utils.data import DataLoader

from rlinks.dataset import RLinkDataset


def test_torch_loader():
    """Test RLink Torch DataLoader."""
    dataset = RLinkDataset(gpu_id=0)
    # dataloader = DataLoader(dataset, batch_size=2, shuffle=True)
    for i in range(16):
        s = time.perf_counter()
        data = dataset.__getitem__(i)
        e = time.perf_counter()
        print(f"index {i} Data fetch time: {(e - s) * 1000} ms")
        print(type(data))
        print(data.keys())
        print(data["top_image"].shape)
        print("value", data["index"])


if __name__ == "__main__":
    test_torch_loader()
    print("All tests passed.")
