import base64
from io import BytesIO

from docstring_parser import parse
from PIL import Image


class ToolResult:
    """统一封装工具执行结果：基础文本、前端 <details> 附加内容、借道 user 的多模态内容"""

    def __init__(self, result: str, details_extra=None, pending_user_content: list = None):
        self.result = result
        self.details_extra = details_extra
        self.pending_user_content = pending_user_content or []


def convert_image_file_to_base64_data_url(image_file_path: str) -> str:
    """将图片等比压缩并转换为 WebP 格式的 Base64 Data URL"""
    with Image.open(image_file_path) as img:
        img.thumbnail((1568, 1568))
        buffer = BytesIO()
        img.save(buffer, format="WEBP")

    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/webp;base64,{b64}"

def to_image_url(image_source: str) -> str:
    """将图片转换为 `chat/completions` 要求的 `image_url` 格式"""
    if image_source.startswith(("http://", "https://")):
        return image_source
    return convert_image_file_to_base64_data_url(image_source)

def function_to_tool(func) -> dict:
    doc = parse(func.__doc__)

    type_map = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}

    properties = {}
    required = []
    for p in doc.params:
        properties[p.arg_name] = {
            "type": type_map[p.type_name],
            "description": p.description
        }
        if not p.is_optional:
            required.append(p.arg_name)

    tool = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc.short_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
    }

    return tool