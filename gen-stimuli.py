import openai
import re
import weave
import os
from dotenv import load_dotenv

load_dotenv()
weave.init('opencores-gen-stimuli')

EXTRACT_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
Extract stimuli signal from given testbench.

[Instructions]
1. The stimuli signal will show in `initial` block.
2. Omit the clock signal (`clk`) and reset signal (`rst`).

[Example]
Here is a testbench for sequential circuit.
```verilog
module testbench;
    reg clk;
    reg rst;
    reg [7:0] data_in_1;
    reg [7:0] data_in_2;
    reg [7:0] data_out;
    wire valid;

    initial begin
        clk = 0;
        rst = 1;
        data_in_1 = 8'h0;
        data_in_2 = 8'h1;
        data_out = 8'h0;
        valid = 0;

        #10;

        clk = 1; #1;
        data_in_1 = 8'h1;
        data_in_2 = 8'h2;
        #4; clk = 0; #5;
    end
endmodule
```
Your output should be in JSON format:
{
    "data_in_1": ["8'h0", "8'h1"],
    "data_in_2": ["8'h1", "8'h2"]
}

[Rules]
1. Only output the stimuli signal in the `initial` block.
2. Only output the signal name and the values.
3. Do NOT add explanations, comments, or extra text outside the json, including the ``` ``` block.
"""

@weave.op()
def extract_stimuli(tb_filepath: str) -> str:
    with open(tb_filepath, "r") as f:
        tb_code = f.read()
    response = openai.chat.completions.create(
        model=model,
        messages=[{
            "role": "user", 
            "content": EXTRACT_PROMPT + "\n\n[Testbench]\n" + tb_code
        }],
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

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

    tb_project = "bubble_sort_module"
    tb_filepaths = [
        "opencores/bubble_sort_module/sim/rtl_sim/src/testbench.v",
    ]

    stimuli_map = {}

    for tb_filepath in tb_filepaths:
        if not os.path.exists(tb_filepath):
            print(f"錯誤：{tb_filepath} 不存在")
            continue
        print(f"Processing {tb_filepath}...")
        try:
            stimuli_map[tb_filepath] = extract_stimuli(tb_filepath)
        except Exception as e:
            print(f"錯誤：{e}")
            continue

    # 寫入 markdown 檔案
    os.makedirs("generated", exist_ok=True)
    
    with open(f"generated/{tb_project}_stimuli.md", "w") as f:
        f.write(f"# {tb_project} Stimuli\n\n")
        for tb_path, stimuli in stimuli_map.items():
            f.write(f"## {tb_path}\n\n")
            f.write("```json\n")
            f.write(stimuli)
            f.write("\n```\n\n")
