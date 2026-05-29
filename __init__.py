from .nodes.nanaix_image import NanaixImageNode
from .nodes.nanaix_text import NanaixTextNode
from .plugin_info import PLUGIN_VERSION

WEB_DIRECTORY = "./web"
__version__ = PLUGIN_VERSION

NODE_CLASS_MAPPINGS = {
    "Nanaix_Text": NanaixTextNode,
    "Nanaix_Image": NanaixImageNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Nanaix_Text": "Nanaix_Text",
    "Nanaix_Image": "Nanaix_Image",
}
