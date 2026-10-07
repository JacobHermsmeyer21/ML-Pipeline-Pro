"""Serialize tuning child writes with parent ownership changes."""

from datetime import UTC, datetime

from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern


async def tuning_write(database, project_id, job_id, token, write, *, terminal=False):
    """Commit a child mutation only while the caller owns its parent.

    Writing the parent in the same transaction is essential: a read-only check
    under snapshot isolation would still allow a takeover before the child commit.
    Callbacks contain database operations only because MongoDB may retry them.
    A missing owner returns None without calling the child mutation.
    """

    async def commit(session):
        query = {
            "_id": job_id,
            "project_id": project_id,
            "worker_token": token,
            "status": {
                "$in": ["failed", "cancelled"] if terminal else ["running", "cancel_requested"]
            },
        }
        if not terminal:
            query["lease_expires_at"] = {"$gt": datetime.now(UTC)}
        owner = await database.tuning_jobs.update_one(
            query, {"$inc": {"ownership_revision": 1}}, session=session
        )
        if owner.matched_count != 1:
            return None
        return await write(session)

    async with database.client.start_session() as session:
        return await session.with_transaction(
            commit, read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority")
        )
