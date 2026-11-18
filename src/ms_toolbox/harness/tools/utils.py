from docstring_parser import parse
import mimetypes
import base64

def convert_image_file_to_base64_data_url(image_file_path: str) -> str:
    """将图片转换为 Base64"""
    mime_type, _ = mimetypes.guess_type(image_file_path)
    if not mime_type:
        mime_type = "image/jpeg"

    with open(image_file_path, "rb") as image_file:
        b64 = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64}"

def to_image_url(image_source: str) -> str:
    """将图片转换为 `chat/completions` 要求的 `image_url` 格式"""
    if image_source.startswith(("http://", "https://", "data:")):
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