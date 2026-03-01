from pydantic import BaseModel


class ImportResult(BaseModel):
    nodes_imported: int
    edges_imported: int
    warnings: list[str] = []
    skipped_types: list[str] = []
