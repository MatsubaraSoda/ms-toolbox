import json
import os
import re
import sys
import logging
import pathlib

from contextlib import contextmanager, redirect_stdout, redirect_stderr
from huggingface_hub import hf_hub_download

import kgen.models as models
import kgen.executor.tipo as tipo
from kgen.formatter import seperate_tags, apply_format
from tipo_meta import DEFAULT_FORMAT

logging.disable(logging.CRITICAL)


@contextmanager
def suppress_output():
    with open(os.devnull, "w") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            yield


def _expansion(params):
    with suppress_output():
        default_format = DEFAULT_FORMAT[params["output_format"]]
        tipo.BAN_TAGS = [t.strip() for t in params["black_list"].split(",") if t.strip()]

        meta, operations, general, nl_prompt = tipo.parse_tipo_request(
            seperate_tags(params["tags"].split(",")),
            params["nl_prompt"],
            tag_length_target=params["target_length"],
            generate_extra_nl_prompt="<|generated|>" in default_format or not params["nl_prompt"],
        )

        for result, _ in tipo.tipo_runner_generator(
            meta, operations, general, nl_prompt,
            seed=params["seed"],
            temperature=params["temp"],
            top_p=params["top_p"],
            min_p=params["min_p"],
            top_k=params["top_k"],
        ):
            pass

        result = apply_format(result, default_format)
        if params["escape_brackets"]:
            result = re.sub(r"([()\[\]])", r"\\\1", result)

    return result

def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")\

    # 读取输出
    payload = [json.loads(line) for line in sys.stdin if line.strip()]

    # 初始化并加载模型（仅一次）
    with suppress_output():
        gguf_path = pathlib.Path(
            hf_hub_download(
                repo_id="KBlueLeaf/TIPO-500M-ft",
                filename="TIPO-500M-ft-F16.gguf",
                local_files_only=True,
            )
        )
        models.model_dir = gguf_path.parent
        models.load_model(gguf_path.name, gguf=True, device="cuda")

    # 执行扩写
    result = [_expansion(params) for params in payload]

    # 输出结果
    for item in result:
        print(json.dumps({"prompt": item}, ensure_ascii=False))

if __name__ == "__main__":
    main()

