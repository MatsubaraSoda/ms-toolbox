from pathlib import Path # 使用 pathlib 处理路径，确保跨平台兼容性；能够自动处理 `/` 和 `\` 的差异。
from pypdf import PdfReader
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