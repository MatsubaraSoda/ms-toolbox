from argparse import ArgumentParser
from pathlib import Path
from ms_toolbox.pdf.core import extract_and_save_pages
import sys

def main():
    """
    命令行主函数：解析参数并调用 PDF 提取的核心逻辑。
    """
    parser = ArgumentParser()

    parser.add_argument(
        '-i', '--input',
        type=str,
        required=True,
        help='输入 PDF 路径 (e.g., input.pdf)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        required=True,
        help='输出 PDF 路径(e.g., output.pdf)'
    )
    parser.add_argument(
        '--start', 
        type=int, 
        required=True, 
        help='开始页码 (1-indexed)'
    )
    parser.add_argument(
        '--end', 
        type=int, 
        required=True, 
        help='结束页码 (1-indexed)'
    )

    args = parser.parse_args()

    try:
        input_file_path = Path(args.input)
        output_file_path = Path(args.output)
        print(f"--- 正在启动 PDF 提取工具 ---")
        print(f"输入文件：{input_file_path}")
        print(f"输出文件：{output_file_path}")
        print(f"页码范围：{args.start} 到 {args.end}")

        result = extract_and_save_pages(
            input_file_path=input_file_path, 
            output_file_path=output_file_path, 
            start_page=args.start, 
            end_page=args.end
        )

        if result is True:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n发生意外错误：{e}", file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()