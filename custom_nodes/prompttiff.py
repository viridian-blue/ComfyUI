import torch
import folder_paths
import os
import hashlib
from PIL import Image, ImageSequence
import numpy as np
from typing import List, Tuple


def get_prompts_and_masks(im: Image.Image):
    for layer in ImageSequence.Iterator(im):
        tags = layer.tag.named()
        prompt = tags.get('PageName', ())
        if prompt:
            yield (prompt[0], np.array(layer.convert(mode='LA'), dtype=np.float32)[:, :,-1] / 255.0)


def get_tiff_pages(tiff_file: str) -> List[Tuple[str, np.ndarray]]:
    im = Image.open(tiff_file)
    return list(get_prompts_and_masks(im))
    

class LoadPromptTiff:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f)) if f.lower().endswith((".tiff", ".tif"))]
        return {"required": {"image": (sorted(files), {"image_upload": True}),
                             "clip": ("CLIP", ),
                            }}
    RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "load_tiff"

    CATEGORY = "conditioning"

    def load_tiff(self, image, clip):
        image_path = folder_paths.get_annotated_filepath(image)
        positives = []
        negatives = []
        for page in get_tiff_pages(image_path):
            prompt = page[0]
            is_positive = True
            if prompt.startswith("-"):
                prompt = prompt[1:]
                is_positive = False
            mask_array = page[1]
            mask = torch.from_numpy(mask_array).unsqueeze(0)
            tokens = clip.tokenize(prompt)
            base_cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
            masked_cond = [base_cond, {"pooled_output": pooled, "mask": mask, "original_prompt": prompt}]
            print(f"Appending masked (shape: {mask_array.shape}) prompt from TIFF:", prompt)
            if is_positive:
                positives.append(masked_cond)
            else:
                negatives.append(masked_cond)
        return (positives, negatives)
    

    @classmethod
    def IS_CHANGED(cls, image, clip):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image, clip):
        try:
            for page in get_tiff_pages(folder_paths.get_annotated_filepath(image)):
                pass
        except Exception as e:
            return str(e)
        
        return True
    


NODE_CLASS_MAPPINGS = {
    "LoadPromptTiff": LoadPromptTiff,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadPromptTiff": "Load PromptTIFF",
}
