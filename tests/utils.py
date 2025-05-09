import aiohttp
import os
import json


async def get_api_key(organization_id: str) -> str:
    """Retrieve the API key for a given organization ID from environment variables.

    Args:
        organization_id (str): The organization ID.

    Returns:
        str: The API key associated with the organization ID.
    """
    server = os.getenv("SERVER_BASE")
    super = os.getenv("SUPER_API_KEY")
    async with aiohttp.ClientSession() as session:
        async with session.request(
            "POST",
            f"{server}/bc/v1/orgkeys",
            headers={"Authorization": f"Bearer {super}"},
            json={"organization_id": organization_id},
        ) as response:
            if response.status != 200:
                raise Exception(f"Error: {response.status} - {await response.text()}")
            data = await response.json()
            return data["apikey"]


async def fetch(
    *,
    api_key: str,
    app_id: str,
    collection: str,
    op: str = "find",
    filter: dict | None = None,
    projection: dict | None = None,
    sort: dict | None = None,
    limit: int = 0,
    skip: int = 0,
    include: list | None = None,
) -> dict:
    """Fetch data from a MongoDB collection.

    Args:
        api_key (str): The API key for authentication.
        app_id (str): The application ID.
        collection (str): The name of the collection to fetch data from.
        op (str): The operation to perform (default is 'find').
        filter (dict): The filter criteria for the query (default is an empty dictionary).
        projection (dict): The fields to include or exclude in the result (default is an empty dictionary).
        sort (dict): The sorting criteria for the result (default is an empty dictionary).
        limit (int): The maximum number of documents to return (default is 0, which means no limit).
        skip (int): The number of documents to skip before returning results (default is 0).
        include (list): Additional fields to include in the result.

    Returns:
        dict: The fetched data.
    """
    server = os.getenv("SERVER_BASE")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-App-Id": app_id,
    }
    params = {
        "limit": limit,
        "skip": skip,
    }
    if filter is not None:
        params["filter"] = json.dumps(filter)  # type: ignore
    if projection is not None:
        params["projection"] = json.dumps(projection)  # type: ignore
    if sort is not None:
        params["sort"] = json.dumps(sort)  # type: ignore
    if include is not None:
        params["include"] = json.dumps(include)  # type: ignore

    async with aiohttp.ClientSession() as session:
        async with session.request(
            "GET",
            f"{server}/bc/v1/db/{collection}/{op}",
            headers=headers,
            params=params,
        ) as response:
            if response.status != 200:
                raise Exception(f"Error: {response.status} - {await response.text()}")
            return await response.json()
