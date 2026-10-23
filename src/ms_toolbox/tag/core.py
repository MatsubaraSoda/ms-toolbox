import csv
from pathlib import Path

# 以 <root> / <hidden> 开头的节点只在树中起组织作用，其名字本身不进入最终组合
def is_hidden(node: str) -> bool:
    if node.startswith('<root>') or node.startswith('<hidden>'):
        return True
    else:
        return False

# 递归算法
def expand(tree: dict[str, list[str]], node: str) -> list[list[str]]:
    if node not in tree:
        if is_hidden(node):
            return [[]]
        else:
            return [[node]]

    result = []
    for child in tree[node]:
        tags = child.split(',')
        combinations = [[]]
        for tag in tags:
            options = expand(tree, tag)
            combinations = [
                combo + opt
                for combo in combinations
                for opt in options
            ]
        result.extend(combinations)

    if is_hidden(node):
        return [[] + res for res in result]
    else:
        return [[node] + res for res in result]

def tag_combos(csv_file_path: Path) -> list[str]:
    # 读取 csv 文件
    with open(csv_file_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        columns = [list(column) for column in zip(*rows)]

    # 构建标签树：列头（节点名）-> 该节点下的子节点取值列表
    tag_tree = {
        header: [''.join(value.split()) for value in values if ''.join(value.split())]
        for header, *values in columns
        if header
    }


    result = expand(tag_tree, '<root>')
    # 转化为字符串数组
    tag_combos = []
    for res in result:
        tag_combos.append(', '.join(res))

    return tag_combos