from ms_toolbox.harness.tools.base import create_base_tools
from ms_toolbox.harness.tools.image import create_image_tools
from ms_toolbox.harness.tools.run_command import create_run_command_tool
from ms_toolbox.harness.tools.utils import function_to_tool
from ms_toolbox.harness.tools.web import create_web_tools


def build_tools(
    tool_names: list[str],
    session_id: str,
    workspace_dir: str,
    docker_image: str = "",
) -> tuple[list[dict], dict]:
    funcs = []
    for name in tool_names:
        if name == "base":
            funcs.extend(create_base_tools(workspace_dir))
        elif name == "run_command":
            funcs.append(create_run_command_tool(session_id, workspace_dir, docker_image))
        elif name == "web":
            funcs.extend(create_web_tools())
        elif name == "image":
            funcs.extend(create_image_tools(session_id, workspace_dir))

    tools = [function_to_tool(f) for f in funcs]
    tool_map = {f.__name__: f for f in funcs}
    return tools, tool_map
