from typing import Dict, List, Optional
from comfy.sd import load_checkpoint_guess_config

class Example:
    """
    A example node

    Class methods
    -------------
    INPUT_TYPES (dict): 
        Tell the main program input parameters of nodes.

    Attributes
    ----------
    RETURN_TYPES (`tuple`): 
        The type of each element in the output tulple.
    RETURN_NAMES (`tuple`):
        Optional: The name of each output in the output tulple.
    FUNCTION (`str`):
        The name of the entry-point method. For example, if `FUNCTION = "execute"` then it will run Example().execute()
    OUTPUT_NODE ([`bool`]):
        If this node is an output node that outputs a result/image from the graph. The SaveImage node is an example.
        The backend iterates on these output nodes and tries to execute all their parents if their parent graph is properly connected.
        Assumed to be False if not present.
    CATEGORY (`str`):
        The category the node should appear in the UI.
    execute(s) -> tuple || None:
        The entry point method. The name of this method must be the same as the value of property `FUNCTION`.
        For example, if `FUNCTION = "execute"` then this method's name must be `execute`, if `FUNCTION = "foo"` then it must be `foo`.
    """
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        """
            Return a dictionary which contains config for all input fields.
            Some types (string): "MODEL", "VAE", "CLIP", "CONDITIONING", "LATENT", "IMAGE", "INT", "STRING", "FLOAT".
            Input types "INT", "STRING" or "FLOAT" are special values for fields on the node.
            The type can be a list for selection.

            Returns: `dict`:
                - Key input_fields_group (`string`): Can be either required, hidden or optional. A node class must have property `required`
                - Value input_fields (`dict`): Contains input fields config:
                    * Key field_name (`string`): Name of a entry-point method's argument
                    * Value field_config (`tuple`):
                        + First value is a string indicate the type of field or a list for selection.
                        + Secound value is a config for type "INT", "STRING" or "FLOAT".
        """
        return {
            "required": {
                "image": ("IMAGE",),
                "int_field": ("INT", {
                    "default": 0, 
                    "min": 0, #Minimum value
                    "max": 4096, #Maximum value
                    "step": 64, #Slider's step
                    "display": "number" # Cosmetic only: display as "number" or "slider"
                }),
                "float_field": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 10.0,
                    "step": 0.01,
                    "round": 0.001, #The value represeting the precision to round to, will be set to the step value by default. Can be set to False to disable rounding.
                    "display": "number"}),
                "print_to_screen": (["enable", "disable"],),
                "string_field": ("STRING", {
                    "multiline": False, #True if you want the field to look like the one on the ClipTextEncode node
                    "default": "Hello World!"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    #RETURN_NAMES = ("image_output_name",)

    FUNCTION = "test"

    #OUTPUT_NODE = False

    CATEGORY = "Example"

    def test(self, image, string_field, int_field, float_field, print_to_screen):
        if print_to_screen == "enable":
            print(f"""Your input contains:
                string_field aka input text: {string_field}
                int_field: {int_field}
                float_field: {float_field}
            """)
        #do some processing on the image, in this example I just invert it
        image = 1.0 - image
        return (image,)

from pathlib import Path
import requests
import tempfile
import os
from comfy.utils import ProgressBar
from functools import lru_cache
import comfy.utils
import comfy.sd
import comfy.controlnet
from PIL import Image, ImageOps
import base64
from io import BytesIO
from dataclasses import dataclass

cache = Path.home() / ".cache" / "comfy-civitai"
checkpoints = cache / "checkpoints"
loras = cache / "loras"
thumbnails = cache / "thumbnails"

ses = requests.Session()
ses.headers["Authorization"] = f"Bearer {os.environ.get('CIVITAI_API_KEY')}"


class CivitaiGalleryMixin:
    cache_dir: Path

    preferred_download_format = {
        "fp": "fp16",
        "size": "pruned",
        "format": "SafeTensor",
    }

    @classmethod
    def download_if_not_exist(cls, model_version_id: str, type: str) -> Path:
        target_dir = cls.cache_dir / model_version_id
        try:
            matches = [x for x in target_dir.iterdir() if x.suffix != ".part"]
            if matches:
                return matches[0]
        except FileNotFoundError:
            pass
        target_dir.mkdir(parents=True, exist_ok=True)
        cls.validate_type(model_version_id, type)
        download_url = cls.get_download_url(model_version_id)
        params = cls.get_download_params(model_version_id)
        target_file = cls.download_file(download_url, params, target_dir)
        return target_file
    
    @classmethod
    @lru_cache(maxsize=1024)
    def get_model_version(cls, model_version_id: str):
        model_info_url = f"https://civitai.com/api/v1/model-versions/{model_version_id}"
        model_info_resp = ses.get(model_info_url)
        model_info_resp.raise_for_status()
        model_info = model_info_resp.json()
        return model_info
    
    @classmethod
    def get_download_params(cls, model_version_id: str):
        model_info = cls.get_model_version(model_version_id)
        files = model_info["files"]
        prefs = cls.preferred_download_format
        params = {
            "fp": prefs["fp"],
            "size": prefs["size"],
            "format": prefs["format"],
        }
        for f in files:
            meta = f['metadata']
            if meta['fp'] == prefs["fp"] and meta['size'] == prefs["size"] and meta['format'] == prefs["format"]:
                return params
            if meta['fp'] == prefs["fp"] and meta['size'] == prefs["size"]:
                params["format"] = meta['format']
                return params
            if meta['size'] == prefs["size"] and meta['format'] == prefs["format"]:
                params["fp"] = meta['fp']
                return params
            if meta['size'] == prefs["size"]:
                params["fp"] = meta['fp']
                params["format"] = meta['format']
                return params

        return {}
    
    @classmethod
    def get_download_url(cls, model_version_id: str):
        model_info = cls.get_model_version(model_version_id)
        return model_info["downloadUrl"]
    
    @classmethod
    def validate_type(cls, model_version_id: str, type: str):
        model_type = cls.get_model_version(model_version_id)["model"]["type"]
        if model_type != type:
            raise ValueError(f"Model {model_version_id} is not a {type} model")

    @classmethod
    def download_file(cls, url: str, params: Dict[str, str], target_dir: Path, filename: Optional[str] = None, progress_bar: Optional[ProgressBar] = None):
        target_dir.mkdir(parents=True, exist_ok=True)
        download_resp = ses.get(url, params=params, stream=True)
        download_resp.raise_for_status()
        size = int(download_resp.headers["Content-Length"])
        if filename is None:
            disposition = download_resp.headers["Content-Disposition"]
            parsed_parts = [x.strip() for x in disposition.split(";")]
            filename = parsed_parts[1].split("=")[1].strip('"')
            
        target_file = target_dir / filename
        if not target_file.resolve().parent == target_dir.resolve():
            # server is not allowed to escape the target directory
            raise ValueError(f"Invalid filename {filename}")
        
        tmp_dl = target_file.with_suffix(".part")
        if progress_bar:
            progress_bar.update_absolute(0, size)
            
        with tmp_dl.open("wb") as f:
            for chunk in download_resp.iter_content(chunk_size=1<<22):
                f.write(chunk)
                if progress_bar:
                    progress_bar.update(len(chunk))
        tmp_dl.rename(target_file)
        return target_file

    @classmethod
    def get_model_thumbnail_path(cls, model_version_id: str) -> Optional[Path]:
        thumbnail_path = thumbnails / f"{model_version_id}.png"
        if thumbnail_path.exists():
            return thumbnail_path
        model_info = cls.get_model_version(model_version_id)
        images = model_info["images"]
        if not images:
            return None
        url = images[0]["url"]
        cls.download_file(url, {}, thumbnails, filename=f"{model_version_id}.png")

    @classmethod
    def get_model_thumbnail(cls, model_version_id: str) -> Optional[str]:
        image_path = cls.get_model_thumbnail_path(model_version_id)
        if image_path is None:
            return None
        i = Image.open(str(image_path.resolve()))
        i.thumbnail((256, 256))
        i = i.convert("RGB")
        png = BytesIO()
        i.save(png, format="PNG")
        b64url = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode("ascii")
        return b64url


class CivitaiGalleryCheckpointLoader(CivitaiGalleryMixin):
    cache_dir = checkpoints
    
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "exact_version_id": ("STRING", {"default": ""}), "model_version_id": ("CIVITAI_CHECKPOINT", {"default": ""} )}}
    RETURN_TYPES = ("MODEL", "CLIP", "VAE")
    FUNCTION = "load_checkpoint"

    CATEGORY = "CivitAI"

    def load_checkpoint(self, exact_version_id=None, model_version_id=None):
        if exact_version_id:
            model_version_id = exact_version_id
        if not model_version_id:
            raise ValueError("model_version_id is required")
        ckpt_path = self.download_if_not_exist(model_version_id, "Checkpoint")
        ckpt_path_str = str(ckpt_path.resolve())
        out = load_checkpoint_guess_config(ckpt_path_str, output_vae=True, output_clip=True)
        ui = {"thumbnails": (self.get_model_thumbnail(model_version_id), )}
        return {"result": out[:3], "ui": ui}


class CivitaiGalleryLoraLoader(CivitaiGalleryMixin):
    cache_dir = loras

    def __init__(self):
        self.loaded_lora = None

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "model": ("MODEL",),
                              "clip": ("CLIP", ),
                              "exact_version_id": ("STRING", {"default": ""}),
                              "model_version_id": ("CIVITAI_LORA", {"default": "123"}),
                              "strength_model": ("FLOAT", {"default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01}),
                              "strength_clip": ("FLOAT", {"default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01}),
                              }}
    RETURN_TYPES = ("MODEL", "CLIP")
    FUNCTION = "load_lora"

    CATEGORY = "CivitAI"

    def load_lora(self, model, clip, model_version_id, strength_model, strength_clip, exact_version_id=None):
        if exact_version_id:
            model_version_id = exact_version_id
        if strength_model == 0 and strength_clip == 0:
            return (model, clip)

        lora_path = self.download_if_not_exist(model_version_id, "LORA")
        lora_path_str = str(lora_path.resolve())
        lora = None
        if self.loaded_lora is not None:
            if self.loaded_lora[0] == lora_path_str:
                lora = self.loaded_lora[1]
            else:
                temp = self.loaded_lora
                self.loaded_lora = None
                del temp

        if lora is None:
            lora = comfy.utils.load_torch_file(lora_path_str, safe_load=True)
            self.loaded_lora = (lora_path_str, lora)

        model_lora, clip_lora = comfy.sd.load_lora_for_models(model, clip, lora, strength_model, strength_clip)
        ui = {"thumbnails": (self.get_model_thumbnail(model_version_id), )}
        return {"result": (model_lora, clip_lora), "ui": ui}



class CivitaiGalleryControlNetLoader(CivitaiGalleryMixin):
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "exact_version_id": ("STRING", {"default": ""}), "model_version_id": ("CIVITAI_CONTROLNET", {"default": ""} )}}

    RETURN_TYPES = ("CONTROL_NET",)
    FUNCTION = "load_controlnet"

    CATEGORY = "loaders"

    def load_controlnet(self, model_version_id, exact_version_id=None):
        if exact_version_id:
            model_version_id = exact_version_id

        controlnet_path = self.download_if_not_exist(model_version_id, "LORA")
        controlnet_path_str = str(controlnet_path.resolve())
        controlnet = comfy.controlnet.load_controlnet(controlnet_path_str)
        return (controlnet,)
