from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.chat.tools import catalog_for_scopes
from app.core.security import TokenClaims, get_current_claims
from app.tools.schemas import ToolCatalogDomain, ToolCatalogEntry, ToolCatalogResponse

router = APIRouter(tags=["tools"])
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


@router.get("/tools", response_model=ToolCatalogResponse)
async def list_tools(
    claims: Claims,
    domain: Annotated[str | None, Query()] = None,
) -> ToolCatalogResponse:
    # Read-only reflection of the deployed tool registry (app/chat/tools.py)
    # — no DB table backs this, see catalog_for_scopes' docstring-equivalent
    # comment. Scope-filtered the same way Claude's own tool visibility is.
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
