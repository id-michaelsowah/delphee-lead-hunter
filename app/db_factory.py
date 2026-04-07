from app.config import settings


def get_repository():
    """Return the appropriate repository backend based on DB_BACKEND env var."""
    if settings.db_backend == "firestore":
        from app.db_firestore import FirestoreRepository
        return FirestoreRepository()
    else:
        from app.db_sql import SQLRepository
        return SQLRepository()
