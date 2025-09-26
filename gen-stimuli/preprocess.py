import re

END_DELIMITERS = ["begin", "end", "endcase", "endmodule", "endtask", "endfunction"]
PRESERVED_KEYWORDS = END_DELIMITERS + [
    "if",
    "else",
    "while",
    "for",
    "repeat",
    "case",
    "default",
    "module",
    "task",
    "function",
]


def process_defines(code: str) -> str:
    """處理 `define 指令，將定義的巨集替換到程式碼中"""
    defines = {}

    # 找到所有 `define 定義
    define_pattern = r"`define\s+(\w+)\s+(.+?)(?=\n|$)"
    define_matches = re.finditer(define_pattern, code, re.MULTILINE)

    for match in define_matches:
        macro_name = match.group(1)
        macro_value = match.group(2).strip()
        defines[macro_name] = macro_value

    # 替換所有使用巨集的地方
    for macro_name, macro_value in defines.items():
        # 替換 `macro_name 為對應的值
        macro_usage_pattern = r"`" + re.escape(macro_name) + r"\b"
        code = re.sub(macro_usage_pattern, macro_value, code)

    # 移除 `define 和 `undef 行
    code = re.sub(r"`define\s+\w+\s+.+?(?=\n|$)", "", code, flags=re.MULTILINE)
    code = re.sub(r"`undef\s+\w+\s*(?=\n|$)", "", code, flags=re.MULTILINE)

    return code


def remove_comments(code: str) -> str:
    """移除 Verilog/SystemVerilog 的單行和多行註解"""
    # 移除多行註解 /* ... */
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    # 移除單行註解 //
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    return code


def remove_system_call(code: str) -> str:
    """移除 Verilog/SystemVerilog 的 system call"""
    code = re.sub(r"\$[^;]+;", "", code)
    return code


def remove_declarations(code: str) -> str:
    """移除宣告"""
    code = re.sub(r"^\s*`[^\n]+", "", code, flags=re.MULTILINE)
    # 移除 module 宣告行
    code = re.sub(r"^\s*module\s+\w+", "", code, flags=re.MULTILINE)
    # 移除 endmodule 行
    code = re.sub(r"^\s*endmodule\s*", "", code, flags=re.MULTILINE)

    return code


def handle_quote(origin: str) -> list[str]:
    """處理雙引號內容物，內容需要完全保留"""
    # 匹配未被跳脫的雙引號
    pattern = r'(?<!\\)"'

    # 找出所有符合的雙引號位置
    quote_positions = [m.start() for m in re.finditer(pattern, origin)]

    # 如果找到的雙引號數量不是偶數,表示有未閉合的雙引號
    if len(quote_positions) % 2 != 0:
        raise ValueError("有未閉合的雙引號")

    result = []
    idx = 0
    pos_iter = iter(quote_positions)
    next_quote_pos = next(pos_iter)
    is_start_quote = True
    while True:
        if next_quote_pos is None:
            result.append(origin[idx:])
            break
        if idx == next_quote_pos:
            continue
        if is_start_quote:
            result.append(origin[idx:next_quote_pos])
            is_start_quote = False
            idx = next_quote_pos
        else:
            result.append(origin[idx : next_quote_pos + 1])
            is_start_quote = True
            idx = next_quote_pos + 1

        try:
            next_quote_pos = next(pos_iter)
        except StopIteration:
            next_quote_pos = None

    return result


def is_end_delimiter(origin: str) -> bool:
    """檢查程式碼是否以關鍵字結尾"""
    for delimiter in END_DELIMITERS:
        if origin.endswith(delimiter):
            return True
    return False


def calc_unclosed_bracket(origin: str) -> int:
    """檢查程式碼中是否有未閉合的()"""
    return len(re.findall(r"[\(]", origin)) - len(re.findall(r"[\)]", origin))


def regularize_code(origin: str) -> list[str]:
    """將程式碼中的語句進行標準化處理"""
    codes = handle_quote(origin)
    words: list[str] = []
    for origin in codes:
        if origin.startswith('"'):
            words.append(origin)
        else:
            words.extend(origin.split())

    lines: list[str] = []
    line = ""

    bracket_level = 0
    for word in words:
        line += " " + word
        bracket_level += calc_unclosed_bracket(word)
        if is_end_delimiter(word):
            if bracket_level != 0:
                raise ValueError("有未閉合的括號，但是以關鍵字結尾")
            lines.append(line.strip())
            line = ""
        elif word.endswith(";"):
            if bracket_level == 0:
                lines.append(line.strip())
                line = ""

    lines = [line for line in lines if line != ";"]
    return lines


def should_keep_statement(statement: str) -> bool:
    """判斷語句是否應該保留"""

    # 保留賦值語句
    if re.search(r"\w+\s*(=|<=)\s*", statement):  # = 或 <=
        return True

    # 保留函數呼叫
    if re.search(r"\w+\s*\(", statement):
        return True

    # 保留關鍵字語句
    if re.search(
        r"(" + "|".join(PRESERVED_KEYWORDS) + r")\b",
        statement,
    ):
        return True

    return False


def preprocess_code(code: str) -> str:
    """預處理程式碼"""
    code = process_defines(code)
    code = remove_comments(code)
    code = remove_system_call(code)
    code = remove_declarations(code)
    lines = regularize_code(code)
    lines = [line for line in lines if should_keep_statement(line)]
    return lines


if __name__ == "__main__":
    input = ""
    print(preprocess_code(input))
