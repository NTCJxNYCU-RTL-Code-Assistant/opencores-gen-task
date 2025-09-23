import openai
import re
import weave
import os
from dotenv import load_dotenv

load_dotenv()
weave.init("opencores-gen-stimuli")

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

EXTRACT_TASK_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
Extract stimuli signal from given testbench, and generate a SystemVerilog task named "drive_stimuli" for testbench usage.

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
Your output should be in SystemVerilog code of the "drive_stimuli" task.
```verilog
task drive_stimuli();
    @(posedge clk);
    data_in_1 = 8'h0;
    data_in_2 = 8'h1;
    
    @(posedge clk);
    data_in_1 = 8'h1;
    data_in_2 = 8'h2;
endtask
```

[Rules]
1. Only output the stimuli signal in the `initial` block.
2. Do NOT add explanations, comments, or extra text outside the verilog code, including the ``` ``` block.
"""

WRITE_TB_PROMPT = """
You are a professional digital circuit verification engineer with expertise in SystemVerilog testbench development.

[Task]  
Generate a SystemVerilog task named "tb" for testbench usage.

[Instructions]  
Let's think step by step.  
1. Based on the given circuit specification, extract the output behavior protocol.  
2. According to the circuit type (sequential or combinational) and output protocol, write a SystemVerilog task "monitor_dut" that monitors DUT outputs.  
3. The task does NOT declare input/output ports explicitly, since all signals can be accessed directly in the TB scope.  
   - Input signals: <input_signal_name>  
   - Output signals for DUT: <output_signal_name>_dut  
   - Output signals for Reference: <output_signal_name>_ref  
4. Behavior inside the task:  
   - If the circuit is SEQUENTIAL: use a `forever` loop to keep monitoring. When the current cycle matches the output protocol, sample data in the NEXT cycle.  
   - If the circuit is COMBINATIONAL: sample data after `#0` delay.  
   - Only push data-related outputs into `<output_signal_name>_q`; control signals should NOT be pushed.
5. I will give you the stimuli signal in JSON format, you need to drive the DUT based on the stimuli signal.

[Example]
Here is a specificaton of a sequential circuit.

```
## Introduction
This is a sequential circuit, output the sum of two input signals.

## Interface
| Signal       | Direction | Comments                                                                                            |
|--------------|-----------|-----------------------------------------------------------------------------------------------------|
| clk          | input     | No comments                                                                                         |
| rst          | input     | Active high                                                                                         |
| data_in_1    | input     | input signal                                                                                        |
| data_in_2    | input     | input signal                                                                                        |
| data_out     | output    | output signal                                                                                       |
```

And here is the stimuli signal.
```json
{
    "data_in_1": ["8'h0", "8'h1"],
    "data_in_2": ["8'h1", "8'h2"]
}
```

Your output should be in SystemVerilog code of the "tb" module.
```systemverilog
module tb;
    // Inputs
    reg clk;
    reg rst;
    reg [7:0] data_in_1;
    reg [7:0] data_in_2;
    
    // Outputs for DUT
    wire [7:0] data_out_dut;

    // Outputs for Reference
    wire [7:0] data_out_ref;

    // Check mismatch
    wire mismatch;
    assign mismatch = data_out_dut !== data_out_ref;

    // Instantiate the Unit Under Test
    TopModule #(8,7)
    dut (
        .clk(clk),
        .rst(rst),
        .data_in_1(data_in_1),
        .data_in_2(data_in_2),
        .data_out_dut(data_out_dut)
    );

    // Instantiate the Reference Module
    TopModule #(8,7)
    ref (
        .clk(clk),
        .rst(rst),
        .data_in_1(data_in_1),
        .data_in_2(data_in_2),
        .data_out_ref(data_out_ref)
    );

    initial begin
        // Initialize Inputs
        clk = 0;
        rst = 1;
        data_in_1 = 0;
        data_in_2 = 0;

        #10;
        rst = 0;

        // Stimuli 1st cycle
        @(posedge clk);
        data_in_1 <= 8'h0;
        data_in_2 <= 8'h1;
        if (mismatch) begin
            $display("Mismatch at %0d", $time);
            $finish;
        end

        // Stimuli 2nd cycle
        @(posedge clk);
        data_in_1 <= 8'h1;
        data_in_2 <= 8'h2;
        if (mismatch) begin
            $display("Mismatch at %0d", $time);
            $finish;
        end

        $finish;
    end
endmodule
```

[Rules]  
1. Must follow correct SystemVerilog syntax.  
2. ONLY output the SystemVerilog code of the "tb" module.
3. Do NOT add explanations, comments, or extra text outside the verilog code, including the ``` ``` block.
"""


@weave.op()
def extract_stimuli(tb_filepath: str) -> str:
    with open(tb_filepath, "r") as f:
        tb_code = f.read()
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": EXTRACT_PROMPT + "\n\n[Testbench]\n" + tb_code}
        ],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


@weave.op()
def extract_task(tb_filepath: str) -> str:
    with open(tb_filepath, "r") as f:
        tb_code = f.read()
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACT_TASK_PROMPT + "\n\n[Testbench]\n" + tb_code,
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


@weave.op()
def write_testbench(stimuli_filepath: str, spec_filepath: str) -> str:
    with open(stimuli_filepath, "r") as f:
        stimuli_json = f.read()
    spec = extract_spec(spec_filepath)

    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": WRITE_TB_PROMPT
                + "\n\n[Specification]\n"
                + spec
                + "\n\n[Stimuli]\n"
                + stimuli_json,
            }
        ],
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

    tb_project = "bubble_sort"
    tb_filepaths = [
        "opencores/bubble_sort_module/sim/rtl_sim/src/testbench.v",
    ]

    task_map = {}

    for tb_filepath in tb_filepaths:
        if not os.path.exists(tb_filepath):
            print(f"錯誤：{tb_filepath} 不存在")
            continue
        print(f"Processing {tb_filepath}...")
        try:
            task_map[tb_filepath] = extract_task(tb_filepath)
        except Exception as e:
            print(f"錯誤：{e}")
            continue

    # 寫入 json 檔案
    os.makedirs(f"generated/{tb_project}", exist_ok=True)

    for i, (tb_filepath, task_code) in enumerate(task_map.items()):
        with open(f"generated/{tb_project}/task_{i}.sv", "w") as f:
            f.write(f"// {tb_filepath}\n{task_code}")

    # spec_filepath = f"generated/{tb_project}/spec.md"
    # tb_code = write_testbench(stimuli_filepath, spec_filepath)
    # with open(f"generated/{tb_project}/tb.sv", "w") as f:
    #     f.write(tb_code)
