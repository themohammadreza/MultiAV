from fastapi import APIRouter

router = APIRouter()

@router.get("/{file_id}")
def get_results(file_id: str):
    # Will be replaced later with DB query
    return {
        "file_id": file_id,
        "status": "pending",
        "results": None
    }

