from ferdelance.config import config_manager
from ferdelance.database.tables import Job as JobDB, JobLock as JobLockDB
from ferdelance.database.repositories.core import AsyncSession, Repository
from ferdelance.logging import get_logger
from ferdelance.schemas.jobs import Job, JobLock
from ferdelance.shared.status import JobStatus

from sqlalchemy import func, select, update
from sqlalchemy.exc import NoResultFound

from datetime import datetime
from uuid import uuid4

import aiofiles.os as aos
import os

LOGGER = get_logger(__name__)


def view(job: JobDB) -> Job:
    return Job(
        id=job.id,
        artifact_id=job.artifact_id,
        component_id=job.component_id,
        status=job.status,
        path=job.path,
        creation_time=job.creation_time,
        execution_time=job.execution_time,
        termination_time=job.termination_time,
        iteration=job.iteration,
    )


def view_lock(lock: JobLockDB):
    return JobLock(
        id=lock.id,
        job_id=lock.job_id,
        next_id=lock.next_id,
        locked=lock.locked,
    )


class JobRepository(Repository):
    """A repository used to manage and store jobs.

    Jobs are an alternate term for Task. Everything that is submitted and need
    to be processed is a job. When a client ask for update it can receive a new
    job to execute."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # TODO: maybe replace arguments with job object?
    async def create_job(
        self,
        artifact_id: str,
        component_id: str,
        path: str,
        iteration: int = 0,
        counter: int = 0,
        status=JobStatus.WAITING,
        job_id: str | None = None,
    ) -> Job:
        """Starts a job by inserting it into the database. The insertion works
        as a scheduling the new work to do. The initial state of the job will
        be JobStatus.SCHEDULED.

        Args:
            artifact_id (str):
                Id of the artifact to schedule.
            component_id (str):
                Id of the client that will have to execute the job.

            TODO: add missing arguments

        Returns:
            Job:
                An handler to the scheduled job.
        """
        LOGGER.info(f"component={component_id}: scheduling new job for artifact={artifact_id} iteration={iteration}")

        # TODO: what happen if we submit again the same artifact?

        if job_id is None:
            job_id = str(uuid4())

        path = await self.store(job_id)

        job = JobDB(
            id=job_id,
            artifact_id=artifact_id,
            component_id=component_id,
            path=path,
            status=status.name,
            iteration=iteration,
            lock_counter=counter,
        )

        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)

        LOGGER.info(
            f"component={component_id}: scheduled job={job.id} for artifact={artifact_id} "
            f"iteration={iteration} component={component_id}"
        )

        return view(job)

    async def store(self, job_id: str) -> str:
        path = config_manager.get().storage_artifact(job_id)
        await aos.makedirs(path, exist_ok=True)
        path = os.path.join(path, f"{job_id}.json")
        return path

    async def add_locks(self, job: Job, locked_jobs: list[Job]) -> None:
        """Adds constraint between the current job and the jobs that depends on
        the successful completion of it. Locked jobs need to have the same
        artifact_id. Jobs from different artifact will be ignored.

        Args:
            job (Job):
                Handler of the current job.
            locks (list[Job]):
                List of handlers to all jobs that are locked by this job.
        """
        for locked_job in locked_jobs:
            if locked_job.artifact_id != job.artifact_id:
                LOGGER.warn(f"job={job.id}: cannot lock locked_job={locked_job.id}, different artifacts!")
                continue

            lock: JobLockDB = JobLockDB(
                artifact_id=job.artifact_id,
                job_id=job.id,
                next_id=locked_job.id,
            )
            self.session.add(lock)

        await self.session.commit()

    async def unlock_job(self, job: Job) -> None:
        """Removes constraints that are locked by the given job.

        Args:
            job (Job):
                Handler to the job that has completed successfully.
        """
        await self.session.execute(update(JobLockDB).where(JobLockDB.job_id == job.id).values(locked=False))
        await self.session.commit()

    async def check_job_is_locked(self, job: Job) -> bool:
        """Checks if the given job is still locked or not.

        Args:
            job (Job):
                Handler to the job to check.

        Returns:
            bool:
                True if the job is still locked and cannot be scheduled,
                otherwise False.
        """
        res = await self.session.scalars(select(JobLockDB.locked).where(JobLockDB.job_id == job.id))

        return any(res.all())

    async def schedule_job(self, job: Job) -> Job:
        """Change the state of a job from WAITING to SCHEDULED.

        Args:
            job (Job):
                Handler to the job to update.

        Returns:
            Job:
                The updated handler.
        """
        LOGGER.info(f"component={job.component_id}: scheduled execution of job={job.id} artifact={job.artifact_id}")
        return await self.update_job_status(job, JobStatus.WAITING, JobStatus.SCHEDULED)

    async def start_execution(self, job: Job) -> Job:
        """Change the state of a job from SCHEDULED to RUNNING.

        Args:
            job (Job):
                Handler to the job to update.

        Returns:
            Job:
                The updated handler.
        """
        LOGGER.info(f"component={job.component_id}: started execution of job={job.id} artifact={job.artifact_id}")
        return await self.update_job_status(job, JobStatus.SCHEDULED, JobStatus.RUNNING)

    async def complete_execution(self, job: Job) -> Job:
        """Change the state of a job from RUNNING to COMPLETED.

        Args:
            job (Job):
                Handler to the job to update.

        Returns:
            Job:
                The updated handler.
        """
        LOGGER.info(f"component={job.component_id}: completed execution of job={job.id} artifact={job.artifact_id}")
        return await self.update_job_status(job, JobStatus.RUNNING, JobStatus.COMPLETED)

    async def failed_execution(self, job: Job) -> Job:
        """Change the state of a job from RUNNING to ERROR.

        Args:
            job (Job):
                Handler to the job to update.

        Returns:
            Job:
                The updated handler.
        """
        LOGGER.error(f"component={job.component_id}: failed execution of job={job.id} artifact={job.artifact_id}")
        return await self.update_job_status(job, JobStatus.RUNNING, JobStatus.ERROR)

    async def update_job_status(self, job: Job, previous_status: JobStatus, next_status: JobStatus) -> Job:
        """Changes the state of the given job to JobStatus.RUNNING. An exception
        is raised if the job is not in JobStatus.SCHEDULED state, or if the job
        does not exists.

        Args:
            job (Job):
                Handler of the job to start.

        Raises:
            ValueError:
                If the job does not exists in the SCHEDULED state.

        Returns:
            Job:
                Updated handler of the started job.
        """

        job_id: str = job.id
        artifact_id: str = job.artifact_id
        component_id: str = job.component_id

        try:
            res = await self.session.scalars(
                select(JobDB).where(
                    JobDB.id == job.id,
                    JobDB.status == previous_status.name,
                    JobDB.component_id == component_id,
                )
            )
            job_db: JobDB = res.one()

            job_db.status = next_status.name
            now = datetime.now(tz=job.creation_time.tzinfo)

            if next_status == JobStatus.SCHEDULED:
                job_db.scheduling_time = now
            if next_status == JobStatus.RUNNING:
                job_db.execution_time = now
            if next_status == JobStatus.COMPLETED or next_status == JobStatus.ERROR:
                job_db.termination_time = now

            await self.session.commit()
            await self.session.refresh(job_db)

            LOGGER.info(
                f"component={job_db.component_id}: changed state from={previous_status} to={next_status} "
                f"for artifact={artifact_id} job={job_id}"
            )

            return view(job_db)

        except NoResultFound:
            message = (
                f"component={component_id}: artifact={artifact_id} with job={job_id} in status "
                f"{previous_status} not found"
            )
            LOGGER.error(message)
            raise ValueError(message)

    async def get_by_id(self, job_id: str) -> Job:
        """Gets an handler to the job associated with the given job_id.

        Args:
            job_id (str):
                Id of the job to retrieve.

        Raises:
            NoResultsFound:
                If the job does not exists.

        Returns:
            Job:
                The handler of the job.
        """
        res = await self.session.scalars(select(JobDB).where(JobDB.id == job_id))
        return view(res.one())

    async def get_by_artifact(self, artifact_id: str, component_id: str, iteration: int) -> Job:
        """Gets an handler to the job associated with the given job_id.

        Args:
            job_id (str):
                Id of the job to retrieve.

        Raises:
            NoResultsFound:
                If the job does not exists.

        Returns:
            Job:
                The handler of the job.
        """
        # TODO: since we don't have the unique constraint anymore, this can be removed?

        res = await self.session.scalars(
            select(JobDB).where(
                JobDB.artifact_id == artifact_id,
                JobDB.component_id == component_id,
                JobDB.iteration == iteration,
            )
        )
        return view(res.one())

    async def get(self, job: Job) -> Job:
        """Gets an updated version of the given job.

        Args:
            job (Job):
                Handler of the job.

        Raises:
            NoResultsFound:
                If the job does not exists.

        Returns:
            Job:
                Updated handler of the job.
        """
        res = await self.session.scalars(select(JobDB).where(JobDB.id == job.id))
        return view(res.one())

    async def list_jobs_locked(self, job: Job) -> list[JobLock]:
        """Returns a list of all the jobs locked by the given job.

        Args:
            job (Job):
                Handler to the current job.

        Returns:
            list[JobLock]:
                A list of locks that are the constraint on the execution
                of the next jobs.
        """
        locks = await self.session.scalars(select(JobLockDB).where(JobLockDB.job_id == job.id))

        return [view_lock(lock) for lock in locks.all()]

    async def list_job_locks_for(self, job: Job) -> list[JobLock]:
        """Lists all the jobs that are locking (not completed successfully) the
        given job.

        Args:
            job (Job):
                An handler to the jobs that is still locked.

        Returns:
            list[JobLock]:

        """
        locks = await self.session.scalars(select(JobLockDB).where(JobLockDB.next_id == job.id))

        return [view_lock(lock) for lock in locks.all()]

    async def list_unlocked_jobs(self, artifact_id: str) -> list[Job]:
        """Lists all jobs that are not locked by any constraint for the given
        artifact_id. Jobs can be in different states.

        Args:
            artifact_id (str):
                Id of the artifact to get the jobs for.

        Returns:
            list[Job]:
                A list of jobs that are not locked by any constraint.
        """
        jobs = await self.session.scalars(
            select(JobDB).where(
                JobDB.artifact_id == artifact_id,
                JobDB.id.not_in(
                    select(JobLockDB.next_id)
                    .where(
                        JobLockDB.locked.is_(True),
                        JobLockDB.artifact_id == artifact_id,
                    )
                    .distinct()
                ),
            )
        )

        return [view(j) for j in jobs.all()]

    async def list_jobs_by_component_id(self, component_id: str) -> list[Job]:
        """Returns a list of jobs assigned to the given component_id.

        Args:
            component_id (str):
                Id of the component to list for.

        Returns:
            list[Job]:
                A list of job handlers assigned to the given component. Note
                that this list can be an empty list.
        """
        res = await self.session.scalars(select(JobDB).where(JobDB.component_id == component_id))
        return [view(j) for j in res.all()]

    async def list_jobs_by_status(self, status: JobStatus) -> list[Job]:
        """Returns a list of all jobs with the given status.

        Args:
            status (JobStatus):
                The status to search for.

        Returns:
            list[Job]:
                A list of job handlers with the given status. Note that this list
                can be an empty list.
        """
        res = await self.session.scalars(select(JobDB).where(JobDB.status == status.name))
        return [view(j) for j in res.all()]

    async def list_jobs(self) -> list[Job]:
        """Returns all jobs in the database.

        Returns:
            list[Job]:
                A list of job handlers. Note that this list can be an empty list.
        """
        res = await self.session.scalars(select(JobDB))
        job_list = [view(j) for j in res.all()]
        return job_list

    async def list_jobs_by_artifact_id(self, artifact_id: str) -> list[Job]:
        """Returns a list of jobs created for the given artifact_id.

        Args:
            artifact_id (str):
                Id of the artifact to list for.

        Returns:
            list[Job]:
                A list of job handlers created by the given artifact. Note that
                this list can be an empty list.
        """
        res = await self.session.scalars(select(JobDB).where(JobDB.artifact_id == artifact_id))
        return [view(j) for j in res.all()]

    async def count_jobs_by_artifact_id(self, artifact_id: str, iteration: int = -1) -> int:
        """Counts the number of jobs created for the given artifact_id.

        Args:
            artifact_id (str):
                Id of the artifact to count for.
            iteration (int):
                If greater than -1, count only for the given iteration.

        Returns:
            int:
                The number, greater than zero, of jobs created.
        """
        conditions = [JobDB.artifact_id == artifact_id]
        if iteration > -1:
            conditions.append(JobDB.iteration == iteration)

        res = await self.session.scalars(select(func.count()).select_from(JobDB).where(*conditions))
        return res.one()

    async def count_jobs_by_artifact_status(self, artifact_id: str, status: JobStatus, iteration: int = -1) -> int:
        """Counts the number of jobs created for the given artifact_id and in
        the given status.

        Args:
            artifact_id (str):
                Id of the artifact to count for.
            status (JobStatus):
                Desired status of the jobs.

        Returns:
            int:
                The number, greater than zero, of jobs in the given state.
        """
        conditions = [JobDB.artifact_id == artifact_id, JobDB.status == status.name]
        if iteration > -1:
            conditions.append(JobDB.iteration == iteration)

        res = await self.session.scalars(select(func.count()).select_from(JobDB).where(*conditions))
        return res.one()

    async def next_job_for_component(self, component_id: str) -> Job:
        """Check the database for the next job for the given component. The
        next job is the oldest job in the SCHEDULED state.

        Args:
            component_id (str):
                Id of the component to search for.

        Raises:
            NoResultFound:
                If there are no more jobs for the component.

        Returns:
            Job:
                The next available job.
        """
        ret = await self.session.scalars(
            select(JobDB)
            .where(JobDB.component_id == component_id, JobDB.status == JobStatus.SCHEDULED.name)
            .order_by(JobDB.creation_time.asc())
            .limit(1)
        )
        return view(ret.one())
