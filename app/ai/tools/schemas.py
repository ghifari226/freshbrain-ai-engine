from pydantic import BaseModel


class ToolCatalogEntry(BaseModel):
    name: str
    description: str
    status: str
    version: str


class ToolCatalogDomain(BaseModel):
    domain: str
    tools: list[ToolCatalogEntry]


class ToolCatalogResponse(BaseModel):
    domains: list[ToolCatalogDomain]
