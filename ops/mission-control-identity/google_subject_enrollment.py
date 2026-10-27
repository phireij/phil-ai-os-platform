"""One-time, default-off enrollment of a hashed Google subject.

The enrollment target must be a pre-created, tightly permissioned host bind
file containing only ``pending``.  Successful enrollment replaces it with a
SHA-256 digest, never the raw Google subject.  The temporary enrollment
container is discarded immediately after the host seals the result.
"""

from __future__ import annotations

import hashlib
import os
import stat
import threading
from pathlib import Path


PENDING_MARKER = "pending\n"


class GoogleSubjectEnrollmentError(ValueError):
    """A safe-to-log enrollment failure."""


class GoogleSubjectEnrollment:
    def __init__(self, target: Path) -> None:
        self._target = target
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls) -> "GoogleSubjectEnrollment":
        if os.environ.get("MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_ENABLED") != "true":
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_inactive")
        raw = os.environ.get("MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_FILE", "")
        if not raw or not Path(raw).is_absolute():
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_file_invalid")
        path = Path(raw)
        try:
            details = path.lstat()
        except OSError as error:
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_file_unavailable") from error
        # The service group needs read access to validate the one-time pending
        # marker and write access to replace it. The host seals the completed
        # digest to root-only mode before any R3 handoff can use it.
        if not stat.S_ISREG(details.st_mode) or (details.st_uid, details.st_gid, stat.S_IMODE(details.st_mode)) != (0, 10002, 0o660):
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_file_permissions")
        if path.read_text(encoding="ascii") != PENDING_MARKER:
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_not_pending")
        return cls(path)

    def enroll(self, verified_subject: str) -> None:
        if not isinstance(verified_subject, str) or not verified_subject or len(verified_subject) > 255:
            raise GoogleSubjectEnrollmentError("google_subject_enrollment_subject_invalid")
        value = "sha256:" + hashlib.sha256(verified_subject.encode("utf-8")).hexdigest() + "\n"
        with self._lock:
            try:
                if self._target.read_text(encoding="ascii") != PENDING_MARKER:
                    raise GoogleSubjectEnrollmentError("google_subject_enrollment_already_completed")
                with self._target.open("r+", encoding="ascii") as handle:
                    handle.write(value)
                    handle.truncate()
                    handle.flush()
                    os.fsync(handle.fileno())
            except GoogleSubjectEnrollmentError:
                raise
            except OSError as error:
                raise GoogleSubjectEnrollmentError("google_subject_enrollment_write_failed") from error
