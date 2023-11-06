

print("Preinstalling...")

import requests
import pathlib
import hashlib

import os

cache = pathlib.Path.home() / ".cache" / "comfy-civitai"

animatediff_models = [
    "69ED0F5FEF82B110ACA51BCAB73B21104242BC65D6AB4B8B2A2A94D31CAD1BF0"
]

url = "https://civitai.com/api/v1/model-versions/by-hash/{hash}"


def parse_content_disposition(content_disposition):
    if not content_disposition:
        return None
    parts = content_disposition.split(";")
    for part in parts:
        if part.strip().startswith("filename="):
            return part.strip()[len("filename="):].strip('"')
    
def validate(file, sha256):
    with file.open("rb") as f:
        h = hashlib.sha256()
        while True:
            chunk = f.read(1<<20)
            if not chunk:
                break
            h.update(chunk)

    digest = h.hexdigest()
    if digest.upper() != sha256:
        raise ValueError(f"Downloaded file {file.basename()} {digest} does not match expected SHA256 {sha256}")

def get_model_info(url):
    with requests.get(url) as r:
        r.raise_for_status()
        return r.json()

def download(url, target_file, sha256=None):
    model_info = get_model_info(url)
    download_url = model_info["downloadUrl"]

    if target_file.exists():
        validate(target_file, sha256)
        return
    
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    partfile = target_file.with_suffix(".part")
    
    print(f"Downloading {url} to {partfile} [{' ' * 20}]", end="")
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        filename = parse_content_disposition(r.headers.get("content-disposition"))
        progress = 0
        with partfile.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1<<22):
                progress += len(chunk)
                progress_str = '.' * int(20 * progress / total) + ' ' * (20 - int(20 * progress / total))
                print(f"\rDownloading {url} to {partfile} [{progress_str}]", end="")
                f.write(chunk)

    if sha256:
        validate(partfile, sha256)

    partfile.rename(target_file)
    print(f"\rDownloading {url} to {target_file} [Done] {' ' * 20}")
    return filename

def preinstall():
    animatediff = pathlib.Path(__file__).parent / "ComfyUI-AnimateDiff-Evolved" 
    if not animatediff.exists():
        print("Nothing to preinstall.")
        return

    for model in animatediff_models:
        target_file = cache / f"animatediff-{model}"
        
        filename = download(url.format(hash=model), target_file, sha256=model)

        if filename:
            softlink = animatediff / "models" / filename
            if softlink.exists():
                softlink.unlink()
            softlink.symlink_to(target_file)

preinstall()

NODE_CLASS_MAPPINGS = {} # no nodes to register

print("Preinstall done.")