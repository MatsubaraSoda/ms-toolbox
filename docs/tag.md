# Tag 工具

与 ComfyUI 生图提示词（Danbooru Tags）处理相关的命令行工具。

## tag-csv2str — 读取标签树 CSV，生成所有可能的标签组合

```bash
tag-csv2str -i test_tags.csv
```

输入格式见 [`tests/tag/test_data/test_tags.csv`](../tests/tag/test_data/test_tags.csv)。从 `<root>` 开始递归遍历标签树（邻接表存储，深度优先展开）生成所有可能的标签组合；`<root>` 和带 `<hidden>` 前缀的节点仅用于组织树结构，不会进入最终组合。结果逐行输出到 stdout。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-i`, `--input` | 是 | 输入标签树 CSV 文件路径 |

退出码：`0` 成功；`2` 意外错误（如 CSV 文件不存在）。状态信息输出到 stderr，组合结果输出到 stdout。

输入示例（CSV FILE/test_tags.csv）：

```csv
<root>,<hidden>审查,<hidden>发型,long_hair
"<hidden>审查, 1girl, <hidden>发型",safe,short_hair,ponytail
,,short_hair,<hidden>
,,long_hair,
```

```powershell
## -i flag
tag-csv2str -i test_tags.csv | Out-File -FilePath output.jsonl -Encoding utf8
```

输出示例（JSON）：

```jsonl
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, long_hair, ponytail"}
{"tag_string": "safe, 1girl, long_hair"}

```

## tag-tag2nl — 用 TIPO 扩写 tag_string

把每组 Danbooru tags 交给 [TIPO](https://huggingface.co/KBlueLeaf/TIPO-500M-ft) 扩写，每组 tags 的扩写结果作为单行字符串输出到 stdout。运行前需在配置文件 `%LOCALAPPDATA%\ms-toolbox\config.yaml` 中指定 `tipo_worker_python_exe`，指向已装好下列依赖的解释器（版本为实测可用版本，不随本项目安装）：

| 库 | 版本 | 说明 |
| --- | --- | --- |
| `tipo-kgen` | 0.3.1 | 扩写核心 |
| `transformers` | 5.20.2 | 官方依赖限制较旧，5.x 实测可用但需额外安装 protobuf |
| `sentencepiece` | 0.2.2 | 解析 `tokenizer.model` |
| `protobuf` | 7.36.2 | transformers 5.x 加载 tokenizer 所需补丁依赖 |
| `tiktoken` | 0.14.0 | 解析失败时的兜底 |
| `torch` | 2.6.0+cu124 | CUDA 推理依赖 |
| `huggingface_hub` | 1.31.0 | 读取本地模型缓存 |

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-t`, `--tags` | 否；不填时走 stdin | 一个或多个 tag_string。 |

退出码：`0` 成功；`2` 意外错误。

输入示例（JSONL / input.jsonl）：

```jsonl
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, long_hair, ponytail"}
{"tag_string": "safe, 1girl, long_hair"}

```

```powershell
## -t flag
tag-tag2nl -t "safe, 1girl, short_hair" "safe, 1girl, short_hair" "safe, 1girl, long_hair, ponytail" "safe, 1girl, long_hair"

## stdin
Get-Content input.jsonl -Raw | tag-tag2nl | Out-File -FilePath output.jsonl -Encoding utf8

## 输出均为 stdout jsonl
```

输出示例（JSONL / output.jsonl）：

```txt
{"prompt": "1girl, \n\nshort hair, simple background, hair between eyes, fangs, open mouth, looking at viewer, frills, bow, bat wings, red eyes, solo, center frills, blush, grey hair, bowtie, wrist cuffs, shirt, outstretched arms, :d, full body, no headwear, black dress, red bow, white background, smile, white shirt, short sleeves, wings, red bowtie, blush stickers, dress, puffy sleeves, standing, petticoat, red footwear, standing on one leg, puffy short sleeves,\n\na charming illustration by the artist cato (monocatienus), known for their whimsical and detailed style. The central figure is Remilia Scarlet, depicted in a full-body shot with her arms outstretched as if welcoming the viewer into her world. She is dressed in an elegant black dress adorned with frills and puffy short sleeves, complemented by red footwear that matches her eyes. The background is simple and white, allowing Remilia to stand out prominently.\n\nsafe"}
{"prompt": "1girl, \n\nshort hair, blush, short sleeves, bow, looking at viewer, fangs, no headwear, simple background, puffy sleeves, red footwear, full body, wings, frills, standing on one leg, white shirt, red bowtie, grey hair, center frills, solo, white background, wrist cuffs, red eyes, open mouth, dress, petticoat, standing, :d, outstretched arms, red bow, blush stickers, smile, puffy short sleeves, bowtie, hair between eyes, black dress, bat wings, shirt,\n\na character from the Touhou series, illustrated in the distinctive style of artist kame (kamepan44231). The central figure is Remilia Scarlet, depicted with her signature pale skin and striking red eyes. She has short, light purple hair and wears a black dress adorned with white ruffles at the hem. Her most notable feature is the pair of bat-like wings that extend from her back, adding an ethereal quality to her appearance.\n\nsafe"}
{"prompt": "1girl, \n\nlong hair, ponytail, bow, solo, hand up, white socks, blue bowtie, white apron, looking at viewer, blue eyes, apron, socks, open mouth, blue dress, frills, dress, black footwear, frilled apron, short sleeves, blue bow, puffy short sleeves, white headwear, grey hair, standing on one leg, very long hair, blush stickers, wrist cuffs, white background, bowtie, standing, shoes, puffy sleeves, maid headdress, hat, simple background, full body,\n\na charming illustration by the artist saijo1201, known for their whimsical and detailed style. The central figure is a young girl with long, flowing silver hair adorned with blue ribbons. She wears a white apron over her dress and has striking black shoes with bows on them. Her eyes are large and expressive, adding to the overall cuteness of the image.\n\nsafe"}
{"prompt": "1girl, \n\nlong hair, tail ornament, blush, thighhighs, purple eyes, tail raised, closed mouth, very long hair, shirt, frilled skirt, black shirt, breasts, skirt, sleeveless shirt, tail bow, looking at viewer, bow, animal ears, hand up, blue bow, cat girl, hairband, sleeveless, white background, bare shoulders, small breasts, cat ears, pleated skirt, white hair, wrist cuffs, purple skirt, grey thighhighs, frills, simple background, black hairband, animal ear fluff, cat tail, solo,\n\nA young girl with long white hair and purple eyes. she is wearing a black dress with a blue ribbon tied around her waist and a pair of cat ears on her head. the background is white, making the girl and her outfit stand out. the overall style of the illustration is anime-inspired.\n\nsafe"}

```
