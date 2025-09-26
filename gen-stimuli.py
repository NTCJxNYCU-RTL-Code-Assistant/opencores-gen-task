import openai
import re
import weave
import os
from dotenv import load_dotenv
import random

load_dotenv()
weave.init("opencores-gen-stimuli")

FILTER_CONTROL_STRUCTURES_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
You will be given a Verilog or SystemVerilog code.
1. If a task block does not contain any assignment statements, filter the whole task block.
2. If a function block does not contain any assignment statements, filter the whole function block.
3. If an initial block does not contain any assignment statements, filter the whole initial block.
4. If a loop block does not contain any assignment statements, filter the whole loop block.
5. If a judgement block does not contain any assignment statements, filter the whole judgement block.

Finally, output the filtered Verilog code or SystemVerilog code.

[Instructions]
1. The assignment statements are the statements that assign a value to a variable, or call a function (e.g., `a = b;`, `a <= b;`, `func();`).
2. The loop blocks are the blocks that contain `repeat`, `for`, or `while` statements.
3. The judgement blocks are the blocks that contain `if`, `else`, `case`, or `default` statements.
4. If a block has only one line, it can omit the `begin` and `end` keywords.
5. The other blocks should not be filtered.

[Rules]
1. Only output the filtered Verilog code or SystemVerilog code, DO NOT output anything else, including the ``` ``` block.
"""

EXTRACT_BLOCK_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
You will be given a testbench written in Verilog or SystemVerilog.
Extract whole `initial` blocks, `task`s, and `function`s.

[Rules]
1. Preserve the `module`, `initial`, `task`, and `function` declarations.
2. Only output the Verilog code or SystemVerilog code, DO NOT output anything else, including the ``` ``` block.
"""


@weave.op()
def extract_task(tb_filepath: str) -> str:
    with open(tb_filepath, "r") as f:
        tb_code = f.read()
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACT_BLOCK_PROMPT + "\n\n[Testbench]\n" + tb_code,
            }
        ],
    )
    return response.choices[0].message.content


def extract_spec(spec_filepath: str) -> str:
    with open(spec_filepath, "r", encoding="utf-8") as f:
        spec = f.read()

    # 從 spec 中提取 Introduction 和 Interface 部分
    lines = spec.split("\n")
    filtered_lines = []
    include_section = False

    for line in lines:
        if line.startswith("# Introduction") or line.startswith("# Interface"):
            include_section = True
            filtered_lines.append(line)
        elif line.startswith("# ") and not (
            line.startswith("# Introduction") or line.startswith("# Interface")
        ):
            include_section = False
        elif include_section:
            filtered_lines.append(line)

    spec = "\n".join(filtered_lines)
    return spec


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


def remove_declarations(code: str) -> str:
    """移除宣告"""
    code = re.sub(r"^\s*`[^\n]+", "", code, flags=re.MULTILINE)
    # 移除 module 宣告行
    code = re.sub(r"^\s*module\s+\w+", "", code, flags=re.MULTILINE)
    # 移除 endmodule 行
    code = re.sub(r"^\s*endmodule\s*", "", code, flags=re.MULTILINE)

    return code


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


def extract_initial_blocks(code: str) -> list:
    """提取所有 initial 區塊"""
    blocks = []
    # 先找到所有 initial 關鍵字的位置
    pattern = r"initial\s+"
    matches = re.finditer(pattern, code, re.MULTILINE)

    for match in matches:
        block = match_begin_end_block(code, match.end())
        if block:
            blocks.append(code[match.start() : match.end()] + block)

    return blocks


def extract_task_blocks(code: str) -> dict[str, str]:
    """提取所有 task 定義"""
    blocks = {}
    pattern = r"(task\s+\w+[^;]*;.*?endtask)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        task_text = match.group(1).strip()
        name_match = re.search(r"task\s+(?:\w+\s+)*(\w+)", task_text)
        if name_match:
            task_name = name_match.group(1)
        else:
            task_name = f"unknown_{random.randint(1, 1000000)}"
        blocks[task_name] = task_text

    return blocks


def extract_function_blocks(code: str) -> dict[str, str]:
    """提取所有 function 定義"""
    blocks = {}
    pattern = r"(function\s+[^;]*;.*?endfunction)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        function_text = match.group(1).strip()
        name_match = re.search(r"function\s+(?:\w+\s+)*(\w+)", function_text)
        if name_match:
            function_name = name_match.group(1)
        else:
            function_name = f"unknown_{random.randint(1, 1000000)}"
        blocks[function_name] = function_text

    return blocks


def try_remove_empty_callable(callable_blocks: dict[str, str]) -> dict[str, str]:
    """嘗試移除沒有賦值語句的 callable 區塊"""
    new_callable_blocks = {}
    for callable_name, callable_text in callable_blocks.items():
        if has_assignments(callable_text):
            new_callable_blocks[callable_name] = callable_text
        if has_function_call(callable_text, callable_blocks.keys()):
            new_callable_blocks[callable_name] = callable_text
    return new_callable_blocks


def extract_module_instances(code: str) -> list:
    """提取所有模組實例化宣告(如 UUT)"""
    blocks = []
    # 匹配模組實例化：module_name [#(parameters)] instance_name (port_connections);
    pattern = r"(\w+\s+(?:#\([^)]*\)\s+)?\w+\s*\([^;]*\);)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        instance_text = match.group(1).strip()
        # 檢查是否包含埠連接（避免誤判其他語句）
        if "." in instance_text and ("(" in instance_text and ")" in instance_text):
            blocks.append(instance_text)

    return blocks


def extract_block(tb_filepath: str) -> str:
    """
    使用基於規則的方式從 Verilog/SystemVerilog 測試檔案中提取 module、initial、task 和 function 區塊
    """
    with open(tb_filepath, "r") as f:
        tb_code = f.read()

    # 處理 `define 指令替換
    tb_code = process_defines(tb_code)

    # 移除宣告
    tb_code = remove_declarations(tb_code)

    # 移除註解
    tb_code = remove_comments(tb_code)

    # 移除 system call
    tb_code = remove_system_call(tb_code)

    # 移除非賦值語句，不包含函數呼叫、if、while、for
    tb_code = filter_non_assignments(tb_code)

    return tb_code

    # # 找到所有需要提取的區塊
    # extracted_blocks = []

    # # 提取模組實例化宣告
    # instance_blocks = extract_module_instances(tb_code)

    # # 提取 task 定義
    # callable_blocks = extract_task_blocks(tb_code)

    # # 提取 function 定義
    # callable_blocks.update(extract_function_blocks(tb_code))

    # # 循環嘗試移除沒有賦值語句的 callable 區塊
    # while True:
    #     new_callable_blocks = try_remove_empty_callable(callable_blocks)
    #     if new_callable_blocks == callable_blocks:
    #         break
    #     callable_blocks = new_callable_blocks

    # # 提取 initial 區塊
    # initial_blocks = extract_initial_blocks(tb_code)

    # extracted_blocks.extend(instance_blocks)
    # extracted_blocks.extend(initial_blocks)
    # extracted_blocks.extend(callable_blocks.values())

    # return "\n\n".join(extracted_blocks)


def has_assignments(block_content: str) -> bool:
    """檢查區塊是否包含賦值語句"""
    # 檢查各種賦值模式
    assignment_patterns = [
        r"\w+\s*=\s*[^=]",  # 阻塞賦值 (a = b)
        r"\w+\s*<=\s*",  # 非阻塞賦值 (a <= b)
    ]

    for pattern in assignment_patterns:
        if re.search(pattern, block_content):
            return True
    return False


def has_function_call(block_content: str, callable_names: list[str] = []) -> bool:
    """檢查區塊是否包含函數呼叫"""
    # 函數呼叫 (func(), task_name() 等)，排除 if、while、for
    pattern = r"(?!if\s*\(|while\s*\(|for\s*\()" + "|".join(callable_names) + r"\s*\("
    if re.search(pattern, block_content):
        return True
    return False


def filter_control_structures(code: str) -> str:
    """過濾掉沒有賦值語句的 for、while、if 控制結構"""

    def remove_empty_control_blocks(text: str) -> str:
        """遞歸移除空的控制區塊"""
        # 處理 for 迴圈 - begin/end 形式
        for_pattern_begin = r"for\s*\([^)]*\)\s*begin\s*(.*?)\s*end"

        def filter_for_begin(match):
            content = match.group(1)
            if has_assignments(content):
                return match.group(0)
            return ""

        text = re.sub(for_pattern_begin, filter_for_begin, text, flags=re.DOTALL)

        # 處理 for 迴圈 - 單行形式（確保不是 begin/end 形式）
        for_pattern_single = r"for\s*\([^)]*\)\s*(?!begin)([^;]*;)"

        def filter_for_single(match):
            statement = match.group(1)
            if has_assignments(statement):
                return match.group(0)
            return ""

        text = re.sub(for_pattern_single, filter_for_single, text)

        # 處理 while 迴圈 - begin/end 形式
        while_pattern_begin = r"while\s*\([^)]*\)\s*begin\s*(.*?)\s*end"

        def filter_while_begin(match):
            content = match.group(1)
            if has_assignments(content):
                return match.group(0)
            return ""

        text = re.sub(while_pattern_begin, filter_while_begin, text, flags=re.DOTALL)

        # 處理 while 迴圈 - 單行形式（確保不是 begin/end 形式）
        while_pattern_single = r"while\s*\([^)]*\)\s*(?!begin)([^;]*;)"

        def filter_while_single(match):
            statement = match.group(1)
            if has_assignments(statement):
                return match.group(0)
            return ""

        text = re.sub(while_pattern_single, filter_while_single, text)

        # 處理 if 語句 - begin/end 形式
        if_pattern_begin = r"if\s*\([^)]*\)\s*begin\s*(.*?)\s*end"

        def filter_if_begin(match):
            content = match.group(1)
            if has_assignments(content):
                return match.group(0)
            return ""

        text = re.sub(if_pattern_begin, filter_if_begin, text, flags=re.DOTALL)

        # 處理 if 語句 - 單行形式（確保不是 begin/end 形式）
        if_pattern_single = r"if\s*\([^)]*\)\s*(?!begin)([^;]*;)"

        def filter_if_single(match):
            statement = match.group(1)
            if has_assignments(statement):
                return match.group(0)
            return ""

        text = re.sub(if_pattern_single, filter_if_single, text)

        return text

    # 多次處理以處理嵌套結構
    prev_code = ""
    current_code = code
    while prev_code != current_code:
        prev_code = current_code
        current_code = remove_empty_control_blocks(current_code)

    # 清理多餘的空行
    current_code = re.sub(r"\n\s*\n\s*\n", "\n\n", current_code)

    return current_code


def filter_non_assignments(code: str) -> str:
    """過濾掉非賦值語句，不包含函數呼叫、if、while、for"""

    def should_keep_statement(statement: str) -> bool:
        """判斷語句是否應該保留"""
        statement = statement.strip()
        if not statement:
            return False

        # 保留賦值語句
        if re.search(r"\w+\s*[=<]=\s*", statement):  # = 或 <=
            return True

        # 保留函數呼叫（包含括號的語句，但排除控制結構）
        if re.search(r"\w+\s*\(", statement) and not re.search(
            r"^\s*(if|else|while|for|repeat|case)\s*\(", statement
        ):
            return True

        # 保留控制語句關鍵字
        if re.search(
            r"^\s*(if|else|while|for|repeat|case|default|begin|end|endmodule|endtask|endfunction)\b",
            statement,
        ):
            return True

        return False

    # 按語句分割程式碼，將分隔符附加到語句尾端
    # 使用正則表達式分割，但保持分隔符在語句尾端
    delimiter_pattern = (
        r"(;|\bbegin\b|\bend\b|\bendmodule\b|\bendtask\b|\bendfunction\b)"
    )
    parts = re.split(delimiter_pattern, code)

    statements = []
    i = 0
    while i < len(parts):
        statement_part = parts[i].strip()

        # 檢查下一個元素是否為分隔符
        if i + 1 < len(parts) and re.match(delimiter_pattern, parts[i + 1]):
            delimiter = parts[i + 1]
            if statement_part:  # 只有當語句部分不為空時才組合
                full_statement = statement_part + (
                    delimiter if delimiter == ";" else " " + delimiter
                )
                # 對語句進行標準化處理
                normalized_statement = re.sub(r"\s+", " ", full_statement).strip()
                if normalized_statement:
                    statements.append(normalized_statement)
            i += 2  # 跳過分隔符
        else:
            # 沒有分隔符的部分
            if statement_part:
                normalized_statement = re.sub(r"\s+", " ", statement_part).strip()
                if normalized_statement:
                    statements.append(normalized_statement)
            i += 1

    with open("temp/statements.txt", "w") as f:
        f.write("\n".join(statements))

    filtered_statements = []
    for statement in statements:
        if should_keep_statement(statement):
            filtered_statements.append(statement)

    # 重新組合程式碼
    result = "\n".join(filtered_statements)

    return result


if __name__ == "__main__":
    openai.api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not openai.api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        exit(1)

    if not model:
        print("錯誤：請設定 OPENAI_MODEL 環境變數")
        exit(1)

    print(f"Using model: {model}")

    # tb_project = "bubble_sort"
    # tb_filepaths = [
    #     "opencores/bubble_sort_module/sim/rtl_sim/src/testbench.v",
    # ]

    tb_project = "sha3"
    tb_filepaths = [
        "opencores/sha3/high_throughput_core/testbench/test_keccak.v",
        # "opencores/sha3/low_throughput_core/testbench/test_keccak.v",
    ]

    # tb_project = "tate_bilinear_pairing"
    # tb_filepaths = [
    #     "opencores/tate_bilinear_pairing/testbench/test_tate_pairing.v",
    # ]

    # tb_project = "sdram_controller"
    # tb_filepaths = [
    #     "opencores/sdram_controller/verif/tb/tb_top.sv",
    # ]

    task_map = {}

    for tb_filepath in tb_filepaths:
        if not os.path.exists(tb_filepath):
            print(f"錯誤：{tb_filepath} 不存在")
            continue
        print(f"Processing {tb_filepath}...")
        try:
            code = extract_block(tb_filepath)
            # code = filter_control_structures(code)
            task_map[tb_filepath] = code
        except Exception as e:
            print(f"錯誤：{e}")
            continue

    os.makedirs(f"temp/{tb_project}", exist_ok=True)

    for i, (tb_filepath, task_code) in enumerate(task_map.items()):
        with open(f"temp/{tb_project}/temp_{i}.sv", "w") as f:
            f.write(f"// {tb_filepath}\n{task_code}")

    # for i, (tb_filepath, task_code) in enumerate(task_map.items()):
    #     print(f"Filtering {tb_filepath}...")
    #     filtered_task_code = filter_control_structures(task_code)
    #     with open(f"temp/{tb_project}/filtered_{i}.sv", "w") as f:
    #         f.write(filtered_task_code)
