from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.ai.tools.catalog import catalog_for_scopes
from app.ai.tools.schemas import ToolCatalogDomain, ToolCatalogEntry, ToolCatalogResponse
from app.core.security import TokenClaims, get_current_claims

# Endpoint katalog menunjukkan tool aktif tanpa membuka cara eksekusinya.
router = APIRouter(tags=["tools"])
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.get("/tools", response_model=ToolCatalogResponse)
async def list_tools(
    claims: Claims,
    domain: Annotated[str | None, Query()] = None,
) -> ToolCatalogResponse:
    entries = catalog_for_scopes(claims.allowed_scopes)
    if domain is not None:
        entries = [entry for entry in entries if entry["domain"] == domain]

    grouped: dict[str, list[ToolCatalogEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry["domain"], []).append(
            ToolCatalogEntry(
                name=entry["name"],
                description=entry["description"],
                status=entry["status"],
                version=entry["version"],
            )
        )

    return ToolCatalogResponse(
        domains=[
            ToolCatalogDomain(domain=domain_name, tools=tools)
            for domain_name, tools in sorted(grouped.items())
        ]
    )
