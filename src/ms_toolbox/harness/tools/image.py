import base64
import mimetypes
import uuid
from pathlib import Path

import requests

from ms_toolbox.harness.config import SESSIONS_DIR, get_harness_config
from ms_toolbox.harness.tools.utils import ToolResult, to_image_url

model_map = {
    "auto": "qwen/qwen-image-2.1-turbo",
}


def generate(api_key: str, model: str, prompt: str, aspect_ratio: str, n: int) -> list[dict] | str:
    """返回格式契约: [{"bytes": bytes, "media_type": str}, ...] 或错误信息字符串"""
    if model not in model_map:
        return f"错误：不支持的 model 挡位 '{model}'，可选值：{list(model_map.keys())}"

    payload = {
        "model": model_map[model],
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
    }
    if n > 1:
        payload["n"] = n

    response = requests.post(
        "https://openrouter.ai/api/v1/images",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/MatsubaraSoda/ms-toolbox",
            "X-OpenRouter-Title": "ms-toolbox"
        },
        json=payload,
    )
    data = response.json()
    if "error" in data:
        return f"错误：{data['error']}"

    return [
        {
            "bytes": base64.b64decode(item["b64_json"]),
            "media_type": item.get("media_type", "image/png"),
        }
        for item in data.get("data", [])
    ]


def resolve_image_path(target: str, assets_dir: Path, workspace_dir: str) -> Path | None:
    """依次在当前会话 assets/ 与工作区 workspace_dir/ 中查找目标图片"""
    if assets_dir.exists():
        p1 = (assets_dir / target).resolve()
        if p1.parent == assets_dir.resolve() and p1.is_file():
            return p1

    if workspace_dir:
        ws = Path(workspace_dir).resolve()
        p2 = (ws / target).resolve()
        if p2.is_relative_to(ws) and p2.is_file():
            return p2

    return None


def create_image_tools(session_id: str, workspace_dir: str) -> list:
    assets_dir = SESSIONS_DIR / session_id / "assets"

    def generate_image(
        prompt: str,
        aspect_ratio: str = "1:1",
        n: int = 1,
        model: str = "auto",
    ) -> ToolResult | str:
        """根据文字提示词生成图片，返回保存后的图片文件名（如需检查画面内容，可随后调用 view_image 查看）。

        Args:
            prompt (str): 画面的详细描述提示词。
            aspect_ratio (str, optional): 宽高比，可选 "1:1"、"16:9"、"9:16"、"4:3"、"3:4"，默认为 "1:1"。
            n (int, optional): 生成图片的数量，默认为 1。
            model (str, optional): 生图模型挡位，目前支持 "auto"，默认为 "auto"。
        """
        cfg = get_harness_config()
        items = generate(cfg["api_key"], model, prompt, aspect_ratio, n)
        if isinstance(items, str):
            return items

        assets_dir.mkdir(parents=True, exist_ok=True)
        filenames = []
        for item in items:
            ext = mimetypes.guess_extension(item["media_type"]) or ".png"
            filename = f"{uuid.uuid4()}{ext}"
            (assets_dir / filename).write_bytes(item["bytes"])
            filenames.append(filename)

        return ToolResult(
            result=f"已生成图片: {', '.join(filenames)}",
            details_extra=filenames,
        )

    def view_image(path: str) -> ToolResult | str:
        """读取并查看指定图片的内容（支持当前会话生成的图片文件名，或工作区内的相对路径）。

        Args:
            path (str): 会话图片文件名（例如 "xxx.png"）或工作区相对路径（例如 "./docs/demo.png"）。
        """
        img_file = resolve_image_path(path, assets_dir, workspace_dir)
        if img_file is None:
            return f"错误：未找到图片 '{path}'。"

        return ToolResult(
            result=f"图片 '{path}' 已加载，附在随后的用户消息中供你查看。",
            pending_user_content=[
                {
                    "type": "image_url",
                    "image_url": {"url": to_image_url(img_file.as_posix()), "detail": "auto"},
                }
            ],
        )

    return [generate_image, view_image]
