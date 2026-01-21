# -*- coding: utf-8 -*-
"""RLink Learner."""

import os
from pathlib import Path


class RLinkSyncModel:
    """RLink Sync Model Helper."""

    @staticmethod
    def read():
        """Read the model path if available."""
        status = os.path.exists(os.path.join(str(Path.home()), "save_ckpt_ready.txt"))
        if status:
            with open(
                os.path.join(str(Path.home()), "save_ckpt_ready.txt"), "r"
            ) as fin:
                model_path = fin.read()
            return model_path
        return None

    @staticmethod
    def read_release():
        """Mark the model has been released."""
        with open(os.path.join(str(Path.home()), "sync_ckpt_ready.txt"), "w") as fout:
            fout.write("sync_ckpt_ready")
        if os.path.exists(os.path.join(str(Path.home()), "save_ckpt_ready.txt")):
            Path(os.path.join(str(Path.home()), "save_ckpt_ready.txt")).unlink()

    @staticmethod
    def sync_is_available():
        """Check whether the previous model has been released."""
        return os.path.exists(os.path.join(str(Path.home()), "sync_ckpt_ready.txt"))

    @staticmethod
    def sync(model_path: str):
        """Mark the model is ready for sync."""
        if RLinkSyncModel.sync_is_available():
            print("Syncing new ckpt:", model_path)
            with open(
                os.path.join(str(Path.home()), "save_ckpt_ready.txt"), "w"
            ) as fout:
                fout.write(model_path)
            if os.path.exists(os.path.join(str(Path.home()), "sync_ckpt_ready.txt")):
                Path(os.path.join(str(Path.home()), "sync_ckpt_ready.txt")).unlink()
        else:
            print("[RLink] The previous model has not been released yet.")
