from fastapi import APIRouter

from app.schemas.validation import ValidationRequest, ValidationResult
from app.services.flowsheet_validator import validate_flowsheet

router = APIRouter()


@router.post("/validate", response_model=ValidationResult)
async def validate(body: ValidationRequest):
    result = validate_flowsheet(body.nodes, body.edges)
    return result
