"""统一 config 列解析器 — 支持旧格式（dict literal）和新格式（Atlas2 风格空格分隔 token）。

用法:
    from app.utils.config_parser import parse_config
    cfg = parse_config("('hex_cmd':'055A...','regex':'pat','group':'1')")  # 旧格式
    cfg = parse_config("hex_cmd 055A02000c800D0A")                       # 新格式：hex_cmd + hex值
    cfg = parse_config("hex_cmd 055A... hw_id 1 1")                      # 新格式：hex_cmd + hex + regex + group + delay
    cfg = parse_config("connect")                                         # 新格式：无参数动作
"""

import ast
import json
import re

from app.utils.logger import get_logger

logger = get_logger("ConfigParser")


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════

def parse_config(text) -> dict:
    """解析 config 列文本为 dict。支持旧/新两种格式。

    - 旧格式: ('key':'val', ...) 或 {'key':'val', ...}
    - 新格式: action arg1 arg2 ...

    解析规则（新格式）：
    - 第一个 token = 操作名（如 hex_cmd、connect）
    - 后续 token = 位置参数，按顺序由 run_read_cmd 消费
    - 返回 {"action": "hex_cmd", "args": ["055A...", "regex_pat", "1", "1"]}

    返回解析后的 dict；空/None 返回 {}。
    """
    if not text:
        return {}

    # 已解析好的 dict，原样返回
    if isinstance(text, dict):
        return text

    text = str(text).strip()
    if not text:
        return {}

    # ── 旧格式检测 ──
    if text.startswith(("(", "{")):
        result = _try_legacy(text)
        if result:
            return result

    # ── 新格式（Atlas2 风格）─
    return _parse_atlas2_style(text)


# ═══════════════════════════════════════════════════════════════════════════
#  旧格式解析（保留原逻辑）
# ═══════════════════════════════════════════════════════════════════════════

def _try_legacy(text: str) -> dict:
    """旧格式三板斧：JSON → ast → regex fallback。"""

    # 1. JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. 括号替换 + ast.literal_eval
    t = text
    if t.startswith("(") and t.endswith(")"):
        t = "{" + t[1:-1] + "}"
    try:
        return ast.literal_eval(t)
    except Exception:
        pass

    # 3. 手动正则兜底（处理缺括号等破损格式）
    t2 = text
    if t2.startswith("(") and t2.endswith(")"):
        t2 = t2[1:-1]
    elif t2.startswith("("):
        t2 = t2[1:]
    elif t2.endswith(")"):
        t2 = t2[:-1]

    result = {}
    if t2:
        # 双引号 key:value（JSON 风格，处理缺括号的破损格式）
        for m in re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', t2):
            result[m[0]] = m[1]
        # 单引号 key:value（Python/dict 风格）
        for m in re.findall(r"'([^']+)'\s*:\s*'([^']*)'", t2):
            result[m[0]] = m[1]

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  新格式解析（Atlas2 风格：操作名 + 空格分隔参数）
# ═══════════════════════════════════════════════════════════════════════════

_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')


def _tokenize(text: str) -> list[str]:
    """按空格分词，支持单/双引号包裹的 token，保留反斜杠（兼容 regex 转义符）。"""
    raw = _TOKEN_RE.findall(text)
    result = []
    for t in raw:
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            result.append(t[1:-1])
        else:
            result.append(t)
    return result


def _parse_atlas2_style(text: str) -> dict:
    """Atlas2 风格解析：第一个 token = 操作名，其余 = 位置参数列表。

    例如:
        "hex_cmd 055A..."             → {"action": "hex_cmd", "args": ["055A..."]}
        "hex_cmd 055A... pat 1 1"     → {"action": "hex_cmd", "args": ["055A...", "pat", "1", "1"]}
        "connect"                      → {"action": "connect", "args": []}
    """
    tokens = _tokenize(text)

    if not tokens:
        return {}

    action = tokens[0]
    args = tokens[1:]
    return {"action": action, "args": args}
