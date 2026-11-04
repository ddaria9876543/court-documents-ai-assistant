
import sys
import time
import threading
from datetime import timedelta
from pathlib import Path

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_history import DocumentHistory
from app.models.processing_job import ProcessingJob
from app.services.document_service import apply_processing_result
from app.services.storage_service import storage_service


# --------------------------------------------------
# Existing OCR / XML / LLM pipeline
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCUMENT_PROCESSING_SRC = PROJECT_ROOT / "document_processing" / "src"

if str(DOCUMENT_PROCESSING_SRC) not in sys.path:
    sys.path.append(str(DOCUMENT_PROCESSING_SRC))

from api_adapter import build_api_result


# --------------------------------------------------
# Worker configuration
# --------------------------------------------------

POLL_INTERVAL_SECONDS = 2
HEARTBEAT_INTERVAL_SECONDS = 20
STALE_AFTER = timedelta(minutes=30)


# --------------------------------------------------
# Document processing
# --------------------------------------------------

def process_message(payload: dict) -> None:
    """Run MinIO -> OCR/XML/LLM -> PostgreSQL pipeline."""

    document_id = int(payload["document_id"])
    object_name = payload["object_name"]
    file_format = payload.get("file_format", "")

    db = SessionLocal()
    temp_path = None

    try:
        document = db.get(Document, document_id)

        if document is None:
            raise RuntimeError(
                f"Document {document_id} not found"
            )

        suffix = f".{file_format}" if file_format else ""

        print(
            f"[worker] document_id={document_id}: "
            "downloading from MinIO",
            flush=True,
        )

        temp_path = storage_service.download_to_temp(
            object_name=object_name,
            suffix=suffix,
        )

        print(
            f"[worker] document_id={document_id}: "
            "starting OCR/LLM",
            flush=True,
        )

        result = build_api_result(temp_path)

        document = apply_processing_result(
            db=db,
            document=document,
            result=result,
        )

        db.commit()

        print(
            f"[worker] document_id={document_id}: "
            f"finished; status={document.status}",
            flush=True,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

        if temp_path is not None:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass


# --------------------------------------------------
# Claim job from PostgreSQL
# --------------------------------------------------

def claim_job() -> tuple[int, dict, int] | None:
    """Atomically claim one available job."""

    db = SessionLocal()

    try:
        stale_before = func.now() - STALE_AFTER

        eligible = or_(
            and_(
                ProcessingJob.status == "pending",
                ProcessingJob.available_at <= func.now(),
            ),
            and_(
                ProcessingJob.status == "processing",
                ProcessingJob.locked_at < stale_before,
            ),
        )

        job = db.scalar(
            select(ProcessingJob)
            .where(
                eligible,
                ProcessingJob.attempts < ProcessingJob.max_attempts,
            )
            .order_by(
                ProcessingJob.available_at,
                ProcessingJob.id,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        if job is None:
            db.rollback()
            return None

        job.status = "processing"
        job.attempts += 1
        job.locked_at = func.now()
        job.last_error = None
        job.updated_at = func.now()

        job_id = job.id
        payload = dict(job.payload)
        attempt = job.attempts

        db.commit()

        return job_id, payload, attempt

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# --------------------------------------------------
# Heartbeat
# --------------------------------------------------

def heartbeat_loop(
    job_id: int,
    attempt: int,
    stop_event: threading.Event,
) -> None:
    """Keep the job lease alive during long OCR/LLM processing."""

    while not stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
        db = SessionLocal()

        try:
            job = db.get(ProcessingJob, job_id)

            if (
                job is None
                or job.status != "processing"
                or job.attempts != attempt
            ):
                return

            job.locked_at = func.now()
            job.updated_at = func.now()
            db.commit()

        except Exception as exc:
            db.rollback()
            print(
                f"[worker] heartbeat error for job={job_id}: {exc}",
                flush=True,
            )

        finally:
            db.close()


# --------------------------------------------------
# Complete successful job
# --------------------------------------------------

def complete_job(
    job_id: int,
    attempt: int,
) -> None:
    db = SessionLocal()

    try:
        job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .with_for_update()
        )

        if (
            job is None
            or job.status != "processing"
            or job.attempts != attempt
        ):
            raise RuntimeError(
                f"Job {job_id} is no longer owned by "
                f"attempt {attempt}"
            )

        job.status = "completed"
        job.locked_at = None
        job.updated_at = func.now()
        job.last_error = None

        db.commit()

        print(
            f"[worker] job={job_id}: completed",
            flush=True,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# --------------------------------------------------
# Retry / failed job
# --------------------------------------------------

def fail_job(
    job_id: int,
    attempt: int,
    error: Exception,
) -> None:

    db = SessionLocal()

    try:
        job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .with_for_update()
        )

        if (
            job is None
            or job.status != "processing"
            or job.attempts != attempt
        ):
            print(
                f"[worker] job={job_id}: ownership changed, "
                "skipping error update",
                flush=True,
            )
            db.rollback()
            return

        error_message = str(error)[:4000]
        job.last_error = error_message
        job.locked_at = None
        job.updated_at = func.now()

        if job.attempts < job.max_attempts:

            delay_seconds = job.attempts * 2

            job.status = "pending"
            job.available_at = (
                func.now() + timedelta(seconds=delay_seconds)
            )

            db.add(
                DocumentHistory(
                    document_id=job.document_id,
                    event_type="processing_retry",
                    message=(
                        f"Attempt {job.attempts}/"
                        f"{job.max_attempts} failed: "
                        f"{error_message}"
                    ),
                )
            )

            db.commit()

            print(
                f"[worker] job={job_id}: retry in "
                f"{delay_seconds}s",
                flush=True,
            )

        else:
            job.status = "failed"

            document = db.get(Document, job.document_id)

            if document is not None:
                document.status = "error"

            db.add(
                DocumentHistory(
                    document_id=job.document_id,
                    event_type="processing_error",
                    message=(
                        f"Processing failed after "
                        f"{job.attempts} attempts: "
                        f"{error_message}"
                    ),
                )
            )

            db.commit()

            print(
                f"[worker] job={job_id}: permanently failed",
                flush=True,
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# --------------------------------------------------
# Recover expired jobs without remaining attempts
# --------------------------------------------------

def recover_exhausted_jobs() -> None:
    """Mark abandoned jobs with exhausted attempts as failed."""

    db = SessionLocal()

    try:
        stale_before = func.now() - STALE_AFTER

        jobs = db.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "processing",
                ProcessingJob.locked_at < stale_before,
                ProcessingJob.attempts >= ProcessingJob.max_attempts,
            )
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()

        for job in jobs:
            job.status = "failed"
            job.locked_at = None
            job.last_error = (
                job.last_error
                or "Worker stopped or lost heartbeat"
            )
            job.updated_at = func.now()

            document = db.get(Document, job.document_id)

            if document is not None:
                document.status = "error"

            db.add(
                DocumentHistory(
                    document_id=job.document_id,
                    event_type="processing_error",
                    message=(
                        "Processing stopped after maximum "
                        "attempts; worker lease expired"
                    ),
                )
            )

        db.commit()

        if jobs:
            print(
                f"[worker] recovered {len(jobs)} "
                "exhausted jobs",
                flush=True,
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# --------------------------------------------------
# Worker main loop
# --------------------------------------------------

def main() -> None:

    print(
        "[worker] PostgreSQL processing worker started",
        flush=True,
    )

    print(
        f"[worker] polling interval: "
        f"{POLL_INTERVAL_SECONDS}s",
        flush=True,
    )

    last_recovery = 0.0

    try:
        while True:

            try:
                now = time.monotonic()

                if now - last_recovery >= 30:
                    recover_exhausted_jobs()
                    last_recovery = now

                claimed = claim_job()

                if claimed is None:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                job_id, payload, attempt = claimed

                print(
                    f"[worker] claimed job={job_id}, "
                    f"attempt={attempt}",
                    flush=True,
                )

                stop_event = threading.Event()

                heartbeat_thread = threading.Thread(
                    target=heartbeat_loop,
                    args=(job_id, attempt, stop_event),
                    daemon=True,
                )

                heartbeat_thread.start()

                processing_error = None

                try:
                    process_message(payload)

                except Exception as exc:
                    processing_error = exc

                finally:
                    stop_event.set()
                    heartbeat_thread.join()

                if processing_error is None:
                    complete_job(job_id, attempt)
                else:
                    print(
                        f"[worker] job={job_id}: "
                        f"{processing_error}",
                        flush=True,
                    )

                    fail_job(
                        job_id=job_id,
                        attempt=attempt,
                        error=processing_error,
                    )

            except Exception as exc:
                print(
                    f"[worker] loop error: {exc}",
                    flush=True,
                )
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print(
            "\n[worker] stopping...",
            flush=True,
        )


if __name__ == "__main__":
    main()
