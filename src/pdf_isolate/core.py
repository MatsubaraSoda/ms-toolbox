from pathlib import Path # 使用 pathlib 处理路径，确保跨平台兼容性；能够自动处理 `/` 和 `\` 的差异。
from pypdf import PdfReader, PdfWriter 
from typing import Optional

# =================================================
# 核心业务模块
# 以函数方式提供各种功能
# =================================================

def get_total_pages(file_path: Path) -> Optional[int]:
    """
    获取指定 PDF 文件的总页数。

    Args:
        file_path: PDF 文件的路径，必须是 pathlib.Path 对象。

    Returns:
        成功时返回 PDF 的总页数（int）；读取失败时返回 None。
    """
    try:        
        reader = PdfReader(file_path)   # PdfReader 负责打开和读取 PDF 文件
        total_pages = len(reader.pages) # 返回 PDF 的总页数
        return total_pages

    except Exception as e:        
        print(f"处理 PDF 文件 '{file_path.name}' 时发生错误：{e}")  # 捕获文件损坏、非 PDF 格式等运行时错误
        return None
    
def extract_and_save_pages(input_file_path: Path, output_file_path: Path, start_page: int, end_page: int) -> bool:
    """
    提取 PDF 的指定范围，从开始页码到结束页码（包含首尾）。

    Args:
        input_file_path: 目标 PDF
        output_file_path: 提取后的 PDF
        start_page: 开始页码（1-indexed）
        end_page: 结束页码（1-indexed）
    
    Returns:
        如果成功返回 True，否则返回 False。
    """
    try:
        reader = PdfReader(input_file_path)
        writer = PdfWriter()

        for page_num in range(start_page - 1, end_page):
            writer.add_page(reader.pages[page_num])

        with open(output_file_path, "wb") as output_pdf:
            writer.write(output_pdf)

        print(f"成功提取第 {start_page} 页到第 {end_page} 页，并保存到 '{output_file_path}'。")
        return True

    except Exception as e:
        print(f"处理 PDF 文件 '{input_file_path.name}' 时发生错误：{e}")
        return False