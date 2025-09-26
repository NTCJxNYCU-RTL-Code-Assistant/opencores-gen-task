import re

END_DELIMITERS = [
    "begin",  #
    "end",
    "endmodule",
    "endtask",
    "endfunction",
]


PRESERVED_KEYWORDS = END_DELIMITERS + [
    "module",
    "task",
    "function",
]

### processing with whole code


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

    return code


def remove_comments(code: str) -> str:
    """移除 Verilog/SystemVerilog 的單行和多行註解"""
    # 移除多行註解 /* ... */
    code = re.sub(r"/\*.*?\*/", ";", code, flags=re.DOTALL)
    # 移除單行註解 //
    code = re.sub(r"//.*?$", ";", code, flags=re.MULTILINE)
    return code


def remove_system_call(code: str) -> str:
    """移除 Verilog/SystemVerilog 的 system call"""
    code = re.sub(r"\$[^;]+;", ";", code)
    return code


def remove_declarations(code: str) -> str:
    """移除宣告"""
    code = re.sub(r"^\s*`[^\n]+", ";", code, flags=re.MULTILINE)
    return code


def remove_if_blocks(code: str) -> str:
    """移除 if 區塊"""
    code = re.sub(r"if\s*\([^)]*\)\s*(?!begin)(.*?);", ";", code)
    code = re.sub(r"if\s*\([^)]*\)\s*begin\s*(.*?)\s*end", ";", code, flags=re.DOTALL)
    return code


def remove_case_blocks(code: str) -> str:
    """移除 case 區塊"""
    code = re.sub(r"case[xz]?\s*\([^)]*\)(.*?)\s*endcase", ";", code, flags=re.DOTALL)
    return code


def add_begin_end_block(code: str) -> str:
    """為單行式 for、while 區塊添加 begin 和 end"""
    # 處理 for 迴圈 - 只匹配單行語句，不匹配已有 begin 的區塊
    for_pattern_single = r"(for\s*\([^)]*\))\s*(?!\s*begin\b)([^;{]*;)"
    code = re.sub(for_pattern_single, r"\1 begin \2 end", code)

    # 處理 while 迴圈 - 只匹配單行語句，不匹配已有 begin 的區塊
    while_pattern_single = r"(while\s*\([^)]*\))\s*(?!\s*begin\b)([^;{]*;)"
    code = re.sub(while_pattern_single, r"\1 begin \2 end", code)

    return code


### devide code to lines and trimming


def devide_by_quote(code: str) -> list[str]:
    """處理雙引號內容物，內容需要完全保留"""
    # 匹配未被跳脫的雙引號
    pattern = r'(?<!\\)"'

    # 找出所有符合的雙引號位置
    quote_positions = [m.start() for m in re.finditer(pattern, code)]

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
            result.append(code[idx:])
            break
        if idx == next_quote_pos:
            continue
        if is_start_quote:
            result.append(code[idx:next_quote_pos])
            is_start_quote = False
            idx = next_quote_pos
        else:
            result.append(code[idx : next_quote_pos + 1])
            is_start_quote = True
            idx = next_quote_pos + 1

        try:
            next_quote_pos = next(pos_iter)
        except StopIteration:
            next_quote_pos = None

    return result


def is_end_delimiter(code: str) -> bool:
    """檢查程式碼是否以關鍵字結尾"""
    for delimiter in END_DELIMITERS:
        if code.endswith(delimiter):
            return True
    return False


def calc_unclosed_bracket(code: str) -> int:
    """檢查程式碼中是否有未閉合的()"""
    return len(re.findall(r"[\(]", code)) - len(re.findall(r"[\)]", code))


def regularize_code(blocks: list[str]) -> list[str]:
    """將程式碼中的語句進行標準化處理"""
    words: list[str] = []
    for origin in blocks:
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

    return lines


### extracting blocks


def extract_task_blocks(code: str):
    """提取所有 task 定義"""
    blocks: dict[str, str | None] = {}
    pattern = r"(task\s+[^;]*;.*?endtask)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        task_text = match.group(1)
        name_match = re.search(r"task\s+(?:\w+\s+)*(\w+)", task_text)
        if name_match:
            blocks[name_match.group(1)] = task_text
        else:
            raise ValueError(f"有未命名的 task: {task_text}")

    code = re.sub(pattern, "", code, flags=re.MULTILINE | re.DOTALL)
    return blocks, code


def extract_function_blocks(code: str):
    """提取所有 function 定義"""
    blocks: dict[str, str | None] = {}
    pattern = r"(function\s+[^;]*;.*?endfunction)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        function_text = match.group(1)
        name_match = re.search(r"function\s+(?:\w+\s+)*(\w+)", function_text)
        if name_match:
            blocks[name_match.group(1)] = function_text
        else:
            raise ValueError(f"有未命名的 function: {function_text}")

    code = re.sub(pattern, "", code, flags=re.MULTILINE | re.DOTALL)
    return blocks, code


### recursively removing clauses


def is_empty_task(code: str) -> bool:
    """檢查 task 是否為空"""
    # 提取 task 名稱後的內容，直到 endtask
    content_match = re.search(r"task\s+\w+\s*;(.*?)endtask", code, re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()
        return content == ""
    else:
        raise ValueError(f"非 task 區塊: {code}")


def is_empty_function(code: str) -> bool:
    """檢查 function 是否為空"""
    # 提取 function 名稱後的內容，直到 endfunction
    content_match = re.search(r"function\s+\w+\s*;(.*?)endfunction", code, re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()
        return content == ""
    else:
        raise ValueError(f"非 function 區塊: {code}")


def is_empty_callable(code: str) -> bool:
    """檢查 callable 是否為空"""
    try:
        empty_task = is_empty_task(code)
    except ValueError:
        empty_task = False
    try:
        empty_function = is_empty_function(code)
    except ValueError:
        empty_function = False
    return empty_task or empty_function


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


def remove_unknown_calling(code: str, removed_callable_names: list[str]):
    """移除已刪除的函數呼叫"""
    lines = code.split("\n")

    # 匹配 function_name(...); 的格式
    function_call_pattern = r"(\w+)\s*\([^)]*\)\s*;"

    def replace_function_call(match: re.Match[str]):
        function_name = match.group(1)
        if function_name in removed_callable_names:
            return ";"
        return match.group(0)

    new_lines = []
    for line in lines:
        line = re.sub(function_call_pattern, replace_function_call, line)
        new_lines.append(line)

    return "\n".join(new_lines)


def remove_empty_blocks(code: str):
    """移除空的區塊"""
    code = re.sub(r"for\s*\([^)]*\)\s*begin\s*end", ";", code, flags=re.DOTALL)
    code = re.sub(r"while\s*\([^)]*\)\s*begin\s*end", ";", code, flags=re.DOTALL)
    code = re.sub(r"begin\s*end", ";", code, flags=re.DOTALL)
    return code


def removing(code: str, removed_callable_names: list[str]):
    """移除流程"""

    lines = code.split("\n")
    lines = [line for line in lines if should_keep_statement(line)]
    new_code = "\n".join(lines)
    new_code = remove_unknown_calling(new_code, removed_callable_names)
    new_code = remove_empty_blocks(new_code)
    return new_code


### final processing


def extract_module_instances(code: str) -> list[str]:
    """提取所有模組實例化宣告(如 UUT)"""
    blocks: list[str] = []
    # 匹配模組實例化：module_name [#(parameters)] instance_name (port_connections);
    pattern = r"(\w+\s+(?:#\([^)]*\)\s+)?\w+\s*\([^;]*\);)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        instance_text = match.group(1).strip()
        # 檢查是否包含埠連接（避免誤判其他語句）
        if "." in instance_text and ("(" in instance_text and ")" in instance_text):
            blocks.append(instance_text)

    return blocks


def extract_initial_blocks(code: str) -> list[str]:
    """提取所有 initial 區塊"""
    blocks: list[str] = []
    # 先找到所有 initial 關鍵字的位置
    pattern = r"initial\s+"
    matches = re.finditer(pattern, code, re.MULTILINE)

    def match_begin_end_block(code: str, start_pos: int) -> str:
        """從指定位置開始匹配完整的 begin/end 區塊"""

        # 從 begin 後開始尋找
        pos = start_pos

        # 跳過空白字元
        while pos < len(code) and code[pos].isspace():
            pos += 1

        # 檢查是否是 begin
        if pos >= len(code) or code[pos : pos + 5] != "begin":
            return ""

        begin_count = 0

        i = pos
        while i < len(code):
            # 使用正則表達式來更精確地匹配關鍵字邊界
            if re.match(r"\bbegin\b", code[i:]):
                begin_count += 1
                i += 5
            elif re.match(r"\bend\b", code[i:]):
                begin_count -= 1
                if begin_count == 0:
                    # 找到匹配的 end，包含整個單字
                    end_pos = i + 3
                    return code[start_pos:end_pos].strip()
                i += 3
            else:
                i += 1

        return ""

    for match in matches:
        block = match_begin_end_block(code, match.end())
        if block:
            blocks.append(code[match.start() : match.end()] + block)

    return blocks


def preprocess_code(code: str) -> str:
    """預處理程式碼"""
    code = process_defines(code)
    code = remove_comments(code)
    code = remove_system_call(code)
    code = remove_declarations(code)
    code = remove_if_blocks(code)
    code = remove_case_blocks(code)
    code = add_begin_end_block(code)

    blocks = devide_by_quote(code)
    lines = regularize_code(blocks)

    code = "\n".join(lines)
    task_blocks, code = extract_task_blocks(code)
    function_blocks, code = extract_function_blocks(code)
    blocks = {**task_blocks, **function_blocks}

    while True:
        removed_callable_names = [k for k, v in blocks.items() if v is None]

        new_code = removing(code, removed_callable_names)
        new_blocks: dict[str, str | None] = {}

        for k in blocks.keys():
            if k in removed_callable_names:
                new_blocks[k] = None
                continue
            new_blocks[k] = removing(blocks[k], removed_callable_names)

        for k in blocks.keys():
            if k in removed_callable_names:
                continue
            if is_empty_callable(new_blocks[k]):
                new_blocks[k] = None

        if new_code == code and new_blocks == blocks:
            break
        code = new_code
        blocks = new_blocks

    result = "module testbench;\n"
    result += "\n".join(extract_module_instances(code)) + "\n"
    result += "\n".join(extract_initial_blocks(code)) + "\n"
    result += (
        "\n".join([block for block in blocks.values() if block is not None]) + "\n"
    )
    result += "endmodule"

    return result


if __name__ == "__main__":
    test_input_path = "opencores/sha3/high_throughput_core/testbench/test_keccak.v"
    test_output_path = "temp/statements.sv"

    with open(test_input_path, "r") as f:
        code = f.read()
    code = preprocess_code(code)
    with open(test_output_path, "w") as f:
        f.write(code)
