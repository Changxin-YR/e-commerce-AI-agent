"""Local cross-process locks, released by the OS after crashes."""
import os
from pathlib import Path


class WriterLease:
    """OS lock released even after a process crash; lifetime belongs to one service."""
    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def acquire(self) -> bool:
        # Windows can lock beyond EOF. Initialize only after acquiring the byte
        # lock: two contenders must never write the first byte before locking.
        stream = self.path.open("a+b", buffering=0)
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.stat().st_size == 0:
                stream.write(b"0")
        except OSError:
            stream.close()
            return False
        self.stream = stream
        return True

    def close(self):
        if self.stream:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
            self.stream = None
