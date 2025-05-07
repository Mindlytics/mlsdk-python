import aiohttp
import os


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
