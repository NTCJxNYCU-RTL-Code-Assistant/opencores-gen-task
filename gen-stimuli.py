import openai
import re
import weave
import os
from dotenv import load_dotenv

load_dotenv()
weave.init("opencores-gen-stimuli")

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


def extract_module_declaration(code: str) -> str:
    """提取 module 宣告"""
    # 匹配 module 宣告，包括參數和連接埠
    pattern = r"(module\s+\w+[^;]*;)"
    match = re.search(pattern, code, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def extract_initial_blocks(code: str) -> list:
    """提取所有 initial 區塊"""
    blocks = []
    # 先找到所有 initial 關鍵字的位置
    pattern = r"initial\s+"
    matches = re.finditer(pattern, code, re.MULTILINE)

    for match in matches:
        # 從每個 initial 位置開始匹配完整區塊
        block = match_begin_end_block(code, match.start())
        if block:
            blocks.append(block)

    return blocks


def extract_task_blocks(code: str) -> list:
    """提取所有 task 定義"""
    blocks = []
    pattern = r"(task\s+\w+[^;]*;.*?endtask)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        blocks.append(match.group(1).strip())

    return blocks


def extract_function_blocks(code: str) -> list:
    """提取所有 function 定義"""
    blocks = []
    pattern = r"(function\s+[^;]*;.*?endfunction)"
    matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

    for match in matches:
        blocks.append(match.group(1).strip())

    return blocks


def extract_module_instances(code: str) -> list:
    """提取所有模組實例化宣告（如 UUT）"""
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


def match_begin_end_block(code: str, start_pos: int) -> str:
    """從指定位置開始匹配完整的 initial begin/end 區塊"""
    # 找到 initial 關鍵字的位置
    initial_match = re.search(r"initial\s+", code[start_pos:])
    if not initial_match:
        return ""

    # 從 initial 後開始尋找
    pos = start_pos + initial_match.end()

    # 跳過空白字元
    while pos < len(code) and code[pos].isspace():
        pos += 1

    # 檢查是否是 begin
    if pos >= len(code) or code[pos : pos + 5] != "begin":
        return ""

    begin_count = 0
    block_start = start_pos

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
                return code[block_start:end_pos].strip()
            i += 3
        else:
            i += 1

    return ""


def extract_block(tb_filepath: str) -> str:
    """
    使用基於規則的方式從 Verilog/SystemVerilog 測試檔案中提取 module、initial、task 和 function 區塊
    """
    with open(tb_filepath, "r") as f:
        tb_code = f.read()

    # 處理 `define 指令替換
    tb_code = process_defines(tb_code)

    # 移除註解
    tb_code = remove_comments(tb_code)

    # 找到所有需要提取的區塊
    extracted_blocks = []

    # 提取 module 宣告
    module_match = extract_module_declaration(tb_code)
    if module_match:
        extracted_blocks.append(module_match)

    # 提取模組實例化宣告
    instance_blocks = extract_module_instances(tb_code)
    extracted_blocks.extend(instance_blocks)

    # 提取 initial 區塊
    initial_blocks = extract_initial_blocks(tb_code)
    extracted_blocks.extend(initial_blocks)

    # 提取 task 定義
    task_blocks = extract_task_blocks(tb_code)
    extracted_blocks.extend(task_blocks)

    # 提取 function 定義
    function_blocks = extract_function_blocks(tb_code)
    extracted_blocks.extend(function_blocks)

    # 加上 endmodule
    if module_match:
        extracted_blocks.append("endmodule")

    return "\n\n".join(extracted_blocks)


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
        "opencores/sha3/low_throughput_core/testbench/test_keccak.v",
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
            task_map[tb_filepath] = extract_block(tb_filepath)
        except Exception as e:
            print(f"錯誤：{e}")
            continue

    os.makedirs(f"temp/{tb_project}", exist_ok=True)

    for i, (tb_filepath, task_code) in enumerate(task_map.items()):
        with open(f"temp/{tb_project}/temp_{i}.sv", "w") as f:
            f.write(f"// {tb_filepath}\n{task_code}")
