# -*- coding: utf-8 -*-
"""RLink Dataset."""

import torch
from torch.utils.data import Dataset


from rlinks.utils.named_share_mem import NamedShareMemQueue


class RLinkDataset(Dataset):
    """RLink Dataset Base Class."""

    def __init__(self, gpu_id: int = 0):
        """Initialize RLink Dataset."""
        self.gpu_id = gpu_id
        self._share_mem_queue = NamedShareMemQueue(gpu_id=self.gpu_id, create=False)
        self._data_cache = []
        self._data_cache_size = 1000  # cache size
        self._data_cache_index = 0
        self._use_cache_index = 0

    def __len__(self):
        """Return the length of the dataset."""
        return len(self._share_mem_queue)

    def __getitem__(self, idx):
        """Get an item from the dataset."""
        try:
            data = self._share_mem_queue.get(idx, timeout=0.3)
            # cache data
            if len(self._data_cache) < self._data_cache_size:
                self._data_cache.append(data)
            else:
                self._data_cache[self._data_cache_index % self._data_cache_size] = data
            self._data_cache_index += 1
            return data
        except Exception as e:
            if self._data_cache:
                print("[RLink] Using cached data.")
                self._use_cache_index += 1
                return self._data_cache[self._use_cache_index % len(self._data_cache)]
            raise e
