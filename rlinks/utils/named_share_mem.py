# -*- coding: utf-8 -*-
"""RLink Named Shared Memory."""

import struct
import mmap
import threading
from typing import Optional, Any

import posix_ipc

from rlinks.utils.exception import ValueWithExitError
from rlinks.utils.msgpack_numpy import unpackb


class NamedShareMemQueue:
    """Named Shared Memory Queue for Inter-Process Communication."""

    def __init__(
        self,
        gpu_id: int,
        slot_size: int = 20 * 1024 * 1024,
        num_slots: int = 128,
        create: bool = False,
    ):
        """
        A named shared memory queue for inter-process communication.

        Args:
            gpu_id: GPU identifier used for naming shared resources
            slot_size: Size of each data slot in bytes (default: 1MB)
            num_slots: Number of slots in the circular buffer
            create: If True, create new shared resources; if False, open existing
        """
        self.gpu_id = gpu_id
        self.data_slot_size = slot_size
        self.data_size_slot_size = 4  # 4 bytes for uint32 size
        self.num_slots = num_slots
        self.data_total_size = self.data_slot_size * num_slots
        self.data_size_total_size = self.data_size_slot_size * num_slots

        # Thread safety for write operations
        self._write_lock = threading.Lock()
        self._write_index = 0

        # Track created resources for cleanup
        self._created_resources = []
        self._opened = False

        # Resource names
        self._data_shm_name = f"/gpu_{gpu_id}_data"
        self._size_shm_name = f"/gpu_{gpu_id}_data_size"
        self._empty_sem_name = f"/gpu_{gpu_id}_empty"
        self._full_sem_name = f"/gpu_{gpu_id}_full"

        try:
            self._initialize_resources(create)
            self._opened = True
        except Exception as e:
            self._cleanup_on_failure()
            raise ValueWithExitError(
                f"Failed to initialize shared memory queue: {str(e)}"
            )

    def _initialize_resources(self, create: bool):
        """Initialize shared memory and semaphores."""
        flags = posix_ipc.O_CREAT if create else 0

        # Create or open data shared memory
        try:
            self.shm_data = posix_ipc.SharedMemory(
                self._data_shm_name,
                flags=flags,
                size=self.data_total_size,
                mode=0o600,  # More restrictive permissions
            )
            if create:
                self._created_resources.append(("shm", self._data_shm_name))
        except posix_ipc.ExistentialError:
            raise ValueWithExitError(
                f"Shared memory {self._data_shm_name} does not exist"
            )

        # Create or open size shared memory
        try:
            self.shm_data_size = posix_ipc.SharedMemory(
                self._size_shm_name,
                flags=flags,
                size=self.data_size_total_size,
                mode=0o600,
            )
            if create:
                self._created_resources.append(("shm", self._size_shm_name))
        except posix_ipc.ExistentialError:
            self.shm_data.unlink()
            raise ValueWithExitError(
                f"Size shared memory {self._size_shm_name} does not exist"
            )

        # Map shared memory
        try:
            self.mapped_data = mmap.mmap(
                self.shm_data.fd,
                self.shm_data.size,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE,
            )
            self.shm_data.close_fd()

            self.mapped_data_size = mmap.mmap(
                self.shm_data_size.fd,
                self.shm_data_size.size,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE,
            )
            self.shm_data_size.close_fd()
        except Exception as e:
            self._cleanup_mappings()
            raise e

        # Create or open semaphores
        try:
            self.empty = posix_ipc.Semaphore(
                self._empty_sem_name, flags=flags, initial_value=self.num_slots
            )
            if create:
                self._created_resources.append(("sem", self._empty_sem_name))
        except posix_ipc.ExistentialError:
            self._cleanup_mappings()
            raise ValueWithExitError(
                f"Empty semaphore {self._empty_sem_name} does not exist"
            )

        try:
            self.full = posix_ipc.Semaphore(
                self._full_sem_name, flags=flags, initial_value=0
            )
            if create:
                self._created_resources.append(("sem", self._full_sem_name))
        except posix_ipc.ExistentialError:
            self._cleanup_mappings()
            self.empty.close()
            raise ValueWithExitError(
                f"Full semaphore {self._full_sem_name} does not exist"
            )

    def _cleanup_on_failure(self):
        """Cleanup resources if initialization fails."""
        if hasattr(self, "mapped_data"):
            self.mapped_data.close()
        if hasattr(self, "mapped_data_size"):
            self.mapped_data_size.close()
        if hasattr(self, "empty"):
            self.empty.close()
        if hasattr(self, "full"):
            self.full.close()

    def _cleanup_mappings(self):
        """Close memory mappings."""
        if hasattr(self, "mapped_data"):
            self.mapped_data.close()
        if hasattr(self, "mapped_data_size"):
            self.mapped_data_size.close()

    def put(self, data: Any, timeout: Optional[float] = None) -> bool:
        """Put data into the queue.

        Args:
            data: Data to be serialized and stored
            timeout: Maximum time to wait for an empty slot (seconds)

        Returns:
            bool: True if data was successfully put

        Raises:
            TimeoutError: If timeout occurs
            ValueError: If data exceeds slot size
            RuntimeError: If queue operation fails
        """
        # Serialize data
        serialized_data = data

        if len(serialized_data) > self.data_slot_size:
            raise ValueWithExitError(
                f"Data size {len(serialized_data)} exceeds slot size {self.data_slot_size} bytes"
            )

        # Acquire empty slot
        try:
            if timeout is not None:
                self.empty.acquire(timeout=timeout)
            else:
                self.empty.acquire()
        except posix_ipc.BusyError:
            raise TimeoutError("Queue is full - semaphore busy")

        try:
            with self._write_lock:
                # Calculate offsets
                slot_idx = self._write_index % self.num_slots
                print("================> slot_idx:", slot_idx)
                offset_data = slot_idx * self.data_slot_size
                offset_size = slot_idx * self.data_size_slot_size

                # Write data and size
                self.mapped_data.seek(offset_data)
                self.mapped_data.write(serialized_data)

                # Ensure we write exactly the data size
                self.mapped_data_size[offset_size : offset_size + 4] = struct.pack(
                    "I", len(serialized_data)
                )

                # Increment write index
                self._write_index += 1

            # Signal that a slot is now full
            self.full.release()
            return True

        except Exception as e:
            # Release the empty slot on failure
            self.empty.release()
            raise RuntimeError(f"Failed to put data to the queue: {str(e)}")

    def get(
        self, slot_idx: Optional[int] = None, timeout: Optional[float] = None
    ) -> Any:
        """Get data from the queue.

        Args:
            slot_idx: Specific slot index to read from (optional).
                     If None, reads from the next available slot.
            timeout: Maximum time to wait for a full slot (seconds)

        Returns:
            Any: Deserialized data

        Raises:
            TimeoutError: If timeout occurs
            RuntimeError: If queue operation fails
        """
        # Acquire full slot
        try:
            if timeout is not None:
                self.full.acquire(timeout=timeout)
            else:
                self.full.acquire()
        except posix_ipc.BusyError:
            raise TimeoutError("Queue is empty - semaphore busy")

        try:
            actual_idx = slot_idx % self.num_slots

            # 2. Read data size
            offset_size = actual_idx * self.data_size_slot_size
            size_data = self.mapped_data_size[offset_size : offset_size + 4]
            data_size = struct.unpack("I", size_data)[0]
            # 3. Read data
            offset_data = actual_idx * self.data_slot_size
            self.mapped_data.seek(offset_data)
            data = self.mapped_data.read(data_size)
            data = unpackb(data)
            # 4. Release empty slot
            self.empty.release()
            return data

        except Exception as e:
            # Release the full slot on failure
            self.full.release()
            raise RuntimeError(f"Failed to get data from the queue: {str(e)}")

    def close(self) -> None:
        """Close all opened resources."""
        if not self._opened:
            return

        try:
            self._cleanup_mappings()
            if hasattr(self, "empty"):
                self.empty.close()
            if hasattr(self, "full"):
                self.full.close()
            self._opened = False
        except Exception as e:
            # Log but don't raise during cleanup
            print(f"Warning: Error during queue close: {str(e)}")

    def unlink(self) -> None:
        """Unlink shared resources (only if created by this instance)."""
        for resource_type, name in self._created_resources:
            try:
                if resource_type == "shm":
                    posix_ipc.unlink_shared_memory(name)
                elif resource_type == "sem":
                    posix_ipc.unlink_semaphore(name)
            except Exception as e:
                # Log but don't raise during cleanup
                print(f"Warning: Failed to unlink {resource_type} {name}: {str(e)}")
        self._created_resources.clear()

    def __len__(self):
        """Return the number of slots in the queue."""
        return self.num_slots

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        # Only unlink if we're the creator and no exception occurred
        if exc_type is None:
            self.unlink()

    def __del__(self):
        """Destructor - only closes resources, never unlinks."""
        try:
            self.close()
        except BaseException:
            pass  # Ignore errors during destruction
