from argparse import ArgumentParser
from pathlib import Path
from ms_toolbox.tag.core import tag_combos
import sys

def main():
    """
    命令行主函数：解析参数并调用标签组合生成的核心逻辑。
    """
    parser = ArgumentParser(description='读取标签树 CSV，生成所有可能的标签组合')

    parser.add_argument(
        '-i', '--input',
        type=str,
        required=True,
        help='输入标签树 CSV 路径 (e.g., tags.csv)'
    )

    args = parser.parse_args()

    try:
        input_file_path = Path(args.input)
        print("--- 正在启动标签组合生成工具 ---", file=sys.stderr)
        print(f"输入文件：{input_file_path}", file=sys.stderr)

        combos = tag_combos(input_file_path)

        for combo in combos:
            print(combo)

        print(f"共生成 {len(combos)} 个标签组合", file=sys.stderr)
        sys.exit(0)

    except Exception as e:
        print(f"\n发生意外错误：{e}", file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()
