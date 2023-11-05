from civitai.my_node import *


NODE_CLASS_MAPPINGS = {
    "CivitaiGalleryCheckpointLoader": CivitaiGalleryCheckpointLoader,
    "CivitaiGalleryLoraLoader": CivitaiGalleryLoraLoader,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "CivitaiGalleryCheckpointLoader": "CivitAI Checkpoint Gallery",
    "CivitaiGalleryLoraLoader": "CivitAI Lora Gallery",
}

WEB_DIRECTORY = "web"

import aiohttp
from aiohttp import web


ses = aiohttp.ClientSession()
ses.headers["Authorization"] = f"Bearer {os.environ.get('CIVITAI_API_KEY')}"



ROUTES = web.RouteTableDef()
 
@ROUTES.get("/hello")
async def hello(request):
    return web.Response(text=f"Hello World, from '{request.path}'!")


# Wildcard route to serve api requests
@ROUTES.get("/api/{tail:.*}")
async def api(request):
    params = request.rel_url.query
    path = request.match_info["tail"]
    url = f"https://civitai.com/api/{path}"
    async with ses.get(url, params=params) as resp:
        data = await resp.read()
        if resp.status != 200:
            print(f"Error: {resp.status} {resp.reason} for GET {url}: {data[:100]}...")
        return web.Response(
            body=data,
            content_type=resp.content_type,
            status=resp.status,
        )