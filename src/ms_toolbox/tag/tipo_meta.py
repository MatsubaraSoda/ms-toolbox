# ==============================================================================
# This file is sourced from the TIPO-DEMO project by KBlueLeaf.
# Original source: https://huggingface.co/spaces/KBlueLeaf/TIPO-DEMO/blob/main/meta.py
#
# Original Author: KBlueLeaf (KohakuBlueleaf)
# Licensed under the Apache License, Version 2.0.
# ==============================================================================

DEFAULT_STYLE_LIST = {
    "style 1": "ask (askzy), torino aqua, migolu",
    "style 2": "azuuru, torino aqua, kedama milk, fuzichoco, ask (askzy), chen bin, atdan, hito, mignon",
    "style 3": "nou (nounknown), shikimi (yurakuru), namiki itsuki, lemon89h, satsuki (miicat), chon (chon33v), omutatsu, mochizuki kei",
    "style 4": "ciloranko, maccha (mochancc), lobelia (saclia), migolu, ask (askzy), wanke, jiu ye sang, rumoon, mizumi zumi",
    "style 5": "reoen, alchemaniac, rella, watercolor (medium)",
    "style 6": "ogipote, misu kasumi, fuzichoco, ciloranko, ninjin nouka, ningen mame, ask (askzy), kita (kitairoha), maccha (mochancc)",
    "no style": "",
}

DEFAULT_NEGATIVE_PROMPT = """
low quality, worst quality, normal quality, text, signature, jpeg artifacts, 
bad anatomy, old, early, mini skirt, nsfw, chibi, multiple girls, multiple boys, 
multiple tails, multiple views, copyright name, watermark, artist name, signature
"""

DEFAULT_FORMAT = {
    "tag only (DTG mode)": """
<|special|>, <|characters|>, <|copyrights|>, 
<|artist|>, 

<|general|>,

<|quality|>, <|meta|>, <|rating|>
""".strip(),
    "NL only (Tag to NL)": """<|extended|>.""".strip(),
    "Both, tag first (recommend)": """
<|special|>, <|characters|>, <|copyrights|>, 
<|artist|>, 

<|general|>,

<|extended|>.

<|quality|>, <|meta|>, <|rating|>
""".strip(),
    "Both, NL first (recommend)": """
<|special|>, <|characters|>, <|copyrights|>, 
<|artist|>, 

<|extended|>.

<|general|>,

<|quality|>, <|meta|>, <|rating|>
""".strip(),
    "Both + generated NL": """
<|special|>, <|characters|>, <|copyrights|>, 
<|artist|>, 

<|generated|>.

<|general|>,

<|extended|>.

<|quality|>, <|meta|>, <|rating|>
""".strip(),
}
