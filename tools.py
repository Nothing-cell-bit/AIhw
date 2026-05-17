import ast
import json
import math
import operator
from pathlib import Path
from typing import Any, Dict
from urllib import error, parse, request

from game import GameError
from game_tools import game_ai_move, game_analyze, game_create, game_moves, game_player_move, game_resign


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class ToolError(Exception):
    pass


def calculator(expression: str) -> str:
    """Safely evaluate arithmetic expressions."""
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    allowed_names = {
        "pi": math.pi,
        "e": math.e,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "abs": abs,
        "round": round,
    }

    def eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](eval_node(node.operand))
        if isinstance(node, ast.Name) and node.id in allowed_names:
            return allowed_names[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in allowed_names:
            func = allowed_names[node.func.id]
            args = [eval_node(arg) for arg in node.args]
            return func(*args)
        raise ToolError("表达式包含不允许的语法。")

    try:
        tree = ast.parse(expression, mode="eval")
        result = eval_node(tree)
    except Exception as exc:
        raise ToolError(f"计算失败：{exc}") from exc

    return str(result)


def wikipedia_search(query: str, lang: str = "zh") -> str:
    lang = lang if lang in {"zh", "en"} else "zh"
    base_url = f"https://{lang}.wikipedia.org"

    try:
        params = parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            }
        )
        search_data = _get_json(f"{base_url}/w/api.php?{params}")
        results = search_data.get("query", {}).get("search", [])
        page_title = results[0]["title"] if results else query

        summary_url = f"{base_url}/api/rest_v1/page/summary/{parse.quote(page_title)}"
        data = _get_json(summary_url)
    except error.HTTPError as exc:
        if exc.code == 404 and lang == "zh":
            return wikipedia_search(query, lang="en")
        raise ToolError(f"维基百科搜索失败：HTTP {exc.code}") from exc
    except Exception as exc:
        raise ToolError(f"维基百科搜索失败：{exc}") from exc

    title = data.get("title", query)
    extract = data.get("extract", "")
    if not extract:
        raise ToolError("没有找到可用摘要。")

    return f"{title}: {extract}"


def _get_json(url: str) -> Dict[str, Any]:
    req = request.Request(url, headers={"User-Agent": "MiniReActAgent/1.0"})
    with request.urlopen(req, timeout=10) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def _safe_data_path(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ToolError("文件名非法，只允许 data 目录下的普通文件名。")

    path = (DATA_DIR / filename).resolve()
    if DATA_DIR.resolve() not in path.parents and path != DATA_DIR.resolve():
        raise ToolError("文件路径超出 data 目录。")
    return path


def file_write(filename: str, content: str) -> str:
    path = _safe_data_path(filename)
    path.write_text(content, encoding="utf-8")
    return f"已写入 {path.name}，共 {len(content)} 个字符。"


def file_read(filename: str) -> str:
    path = _safe_data_path(filename)
    if not path.exists():
        raise ToolError(f"{path.name} 不存在。")
    return path.read_text(encoding="utf-8")


TOOLS = {
    "calculator": calculator,
    "wikipedia_search": wikipedia_search,
    "file_write": file_write,
    "file_read": file_read,
    "game_create": game_create,
    "game_player_move": game_player_move,
    "game_ai_move": game_ai_move,
    "game_analyze": game_analyze,
    "game_moves": game_moves,
    "game_resign": game_resign,
}


def run_tool(name: str, action_input: Dict[str, Any]) -> str:
    if name not in TOOLS:
        return f"工具错误：不存在名为 {name} 的工具。"
    if not isinstance(action_input, dict):
        return "工具错误：action_input 必须是 JSON 对象。"

    try:
        return TOOLS[name](**action_input)
    except TypeError as exc:
        return f"工具参数错误：{exc}"
    except GameError as exc:
        return f"工具执行失败：{exc}"
    except ToolError as exc:
        return f"工具执行失败：{exc}"
    except Exception as exc:
        return f"工具执行出现未知错误：{exc}"
