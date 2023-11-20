import strawberry
from strawberry import relay
from strawberry.scalars import JSON
from strawberry.extensions import ParserCache
from strawberry.fastapi import GraphQLRouter
from strawberry.types.info import Info
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings
import httpx
from httpx._models import Response
import semver

import logging
from typing import Optional


class Settings(BaseSettings):
    api_base_host: str = "https://api.tailscale.com/api/v2/tailnet/"
    tailnet_domain: str
    api_key: str
    timeout: int = 2


logger = logging.getLogger(__name__)
settings = Settings()
app = FastAPI()


async def _tailscale_req(method: str, uri: str) -> Response:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                settings.api_base_host + settings.tailnet_domain + uri,
                headers={"Authorization": "Bearer " + settings.api_key},
                timeout=settings.timeout,
            )
            response.raise_for_status()
            return response
    except httpx.HTTPError as e:
        logging.critical("HTTP Request Error: {}".format(e))
        raise HTTPException(status_code=500, detail="Unexpected error")


def _comp_version(comp, a, b):
    _ = {
        "<": lambda a, b: semver.compare(a, b) == -1,
        "<=": lambda a, b: semver.compare(a, b) in (0, -1),
        "=": lambda a, b: semver.compare(a, b) == 0,
        ">": lambda a, b: semver.compare(a, b) == 1,
        ">=": lambda a, b: semver.compare(a, b) in (0, 1),
    }
    if comp not in _.keys():
        raise ValueError("{} is not valid option")
    return _[comp](a, b)


@strawberry.type
class ClientConnectivity:
    endpoints: list[str]
    mappingVariesByDestIP: bool
    latency: JSON
    clientSupports: JSON


@strawberry.type
class DNSPreferences:
    magicDNS: bool


@strawberry.type
class Key:
    id: strawberry.ID
    description: str


@strawberry.type
class DNS:
    @strawberry.field
    async def nameservers(self) -> list[str]:  # type: ignore[misc]
        response = await _tailscale_req("GET", "/dns/nameservers")
        for ns in response.json()["dns"]:
            yield ns

    @strawberry.field
    async def preferences(self) -> DNSPreferences:
        response = await _tailscale_req("GET", "/dns/preferences")
        return DNSPreferences(
            magicDNS=response.json()["magicDNS"]
        )  # type: ignore[call-arg]

    @strawberry.field
    async def searchPaths(self) -> list[str]:  # type: ignore[misc]
        response = await _tailscale_req("GET", "/dns/searchpaths")
        for search_path in response.json()["searchPaths"]:
            yield search_path


@strawberry.type
class Device:
    addresses: list[str]
    id: strawberry.ID
    nodeId: str
    user: str
    name: str
    hostname: str
    clientVersion: str
    updateAvailable: bool
    os: str
    created: str
    lastSeen: str
    keyExpiryDisabled: bool
    expires: str
    authorized: bool
    isExternal: bool
    machineKey: str
    nodeKey: str
    blocksIncomingConnections: bool
    enabledRoutes: list[str]
    advertisedRoutes: list[str]
    clientConnectivity: ClientConnectivity
    tags: list[str] | None
    tailnetLockError: str
    tailnetLockKey: str | None


@strawberry.type
class Query:
    @strawberry.field
    async def dns(self) -> DNS:
        return DNS()

    @strawberry.field
    async def keys(self) -> list[Key]:  # type: ignore[misc]
        response = await _tailscale_req("GET", "/keys")
        for key in response.json()["keys"]:
            yield Key(
                id=key["id"], description=key["description"]
            )  # type: ignore[call-arg]

    @relay.connection(relay.ListConnection[Device])
    async def devices(  # type: ignore[misc]
        self,
        info: Info,
        tags: Optional[list[str]] = None,
        client_version: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> list[Device]:
        response = await _tailscale_req("GET", "/devices?fields=all")
        devices = response.json()["devices"]

        if tags is not None:
            devices = list(
                filter(
                    lambda device: any(  # type: ignore[arg-type]
                        tag in device.get("tags", []) for tag in tags
                    ),
                    devices,
                )
            )

        if client_version is not None:
            comp, version = client_version.split(" ")
            devices = list(
                filter(
                    lambda device: _comp_version(
                        comp, device["clientVersion"], version
                    ),
                    devices,
                )
            )

        if sort is not None:
            sort_desc = False
            if sort.startswith("-"):
                sort_desc = True
                sort = sort[1:]
            try:
                devices = sorted(
                    devices, key=lambda device: device[sort], reverse=sort_desc
                )
            except KeyError:
                pass

        for device in devices:
            yield Device(
                addresses=device["addresses"],
                id=device["id"],
                nodeId=device["nodeId"],
                user=device["user"],
                name=device["name"],
                hostname=device["hostname"],
                clientVersion=device["clientVersion"],
                updateAvailable=device["updateAvailable"],
                os=device["os"],
                created=device["created"],
                lastSeen=device["lastSeen"],
                keyExpiryDisabled=device["keyExpiryDisabled"],
                expires=device["expires"],
                authorized=device["authorized"],
                isExternal=device["isExternal"],
                machineKey=device["machineKey"],
                nodeKey=device["nodeKey"],
                blocksIncomingConnections=device["blocksIncomingConnections"],
                enabledRoutes=device["enabledRoutes"],
                advertisedRoutes=device["advertisedRoutes"],
                clientConnectivity=ClientConnectivity(
                    endpoints=device["clientConnectivity"]["endpoints"],
                    mappingVariesByDestIP=device["clientConnectivity"][
                        "mappingVariesByDestIP"
                    ],
                    latency=device["clientConnectivity"]["latency"],
                    clientSupports=device["clientConnectivity"][
                        "clientSupports"
                    ],
                ),  # type: ignore[call-arg]
                tags=device.get("tags"),
                tailnetLockError=device.get("tailnetLockError"),
                tailnetLockKey=device["tailnetLockKey"],
            )  # type: ignore[call-arg]


schema = strawberry.Schema(Query, extensions=[ParserCache()])
graphql_router = GraphQLRouter(schema)
app.include_router(graphql_router, prefix="/graphql")
