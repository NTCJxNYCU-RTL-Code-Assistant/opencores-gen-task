import openai
import weave
import os
from dotenv import load_dotenv

WRITE_SEQUENTIAL_TASK_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
You will be given a SystemVerilog testbench, and a circuit specification.
Write a SystemVerilog containg only task blocks for the testbench.

[Example]
Given the following testbench and circuit interface description:
```systemverilog
module testbench;
    mymodule uut (
        .clk(clk),
        .reset(reset),
        .input(input),
        .output(output),
    );

    initial begin
        clk = 0;
        reset = 1;
        input = 0;
        #5; reset = 0;

        #100;

        @ (negedge clk);
        input = 3; #5;

        #100;

        clk = 1; #5; clk = 0; #5;
        input = 4; #5;
        check_out(0);

        #100;

        reset = 1;
        #5; reset = 0;
        set_in(-2); #5;
        check_out(output);

        $finish;
    end

    always #5 clk = ~clk;

    task check_out;
        input [2:0] out;
        begin
            $display("check_out: %b", out);
        end
    endtask

    task set_in;
        input [2:0] in;
        begin
            input = in;
        end
    endtask
endmodule
```

The following is the circuit specification.
```markdown
// ... some introduction ...

| Port name | Width | Direction | Description |
|-----------|-------|-----------|-------------|
| clk       | 1     | In        | Clock       |
| reset     | 1     | In        | Reset       |
| input     | 3     | In        | Input       |
| output    | 1     | Out       | Output      |

// ... some other sections ...
```

Let's think step by step.
1. based on the module instance in the testbench and the circuit interface description, we can know the input and output signals of the circuit:
    - clock signal: clk
    - reset signal: reset
    - input signal: input
    - output signal: output
2. Only focus the initial block in the testbench, we can see batches of input signals, and omit output signals or related logics.
    batch 1:
        clk = 0;
        reset = 1;
        input = 0;
        #5; reset = 0;
    batch 2:
        @ (negedge clk);
        input = 3; #5;
    batch 3:
        clk = 1; #5; clk = 0; #5;
        input = 4; #5;
    batch 4:
        reset = 1; 
        #5; reset = 0;
        set_in(-2); #5;
3. For each batch, we can write a task to wrap the input signals, clock signal, reset signal, and waiting logics.
    ```systemverilog
    task drive_rst;
        begin
            clk = 0;
            reset = 1;
            input = 0;
            #5;
            reset = 0;
        end
    endtask

    task drive_stimuli_1;
        begin
            @ (negedge clk);
            input = 3;
            #5;
        end
    endtask

    task drive_stimuli_2;
        begin
            clk = 1; 
            #5; 
            clk = 0; 
            #5;
            input = 4;
            #5;
        end
    endtask

    task drive_stimuli_3;
        begin
            reset = 1;
            #5;
            reset = 0;
            set_in(-2);
            #5;
        end
    endtask
    ```
4. You have completed the task, only output the SystemVerilog code, DO NOT output anything else, including the ``` ``` block.

[Rules]
1. Only output the Verilog code or SystemVerilog code, DO NOT output anything else, including the ``` ``` block.
2. The first task should be named with `drive_rst`, and the other tasks should be named with `drive_stimuli_i`, where `i` is the batch index after `drive_rst`, start from 1.
3. All the tasks should not contain the output signals, or related logics.
4. All the tasks should not contain the signals that are not defined in the module instance of the testbench.
"""


@weave.op()
def generate(model: str, code: str, spec_filepath: str):
    with open(spec_filepath, "r", encoding="utf-8") as f:
        spec = f.read()
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": WRITE_SEQUENTIAL_TASK_PROMPT
                + "\n\n[Testbench]\n"
                + code
                + "\n\n[Specification]\n"
                + spec,
            }
        ],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not openai.api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        exit(1)

    if not model:
        print("錯誤：請設定 OPENAI_MODEL 環境變數")
        exit(1)

    print(f"Using model: {model}")

    test_input_path = "temp/statements.sv"
    test_output_path = "temp/generate.sv"

    with open(test_input_path, "r") as f:
        code = f.read()
    code = generate(code, model)
    with open(test_output_path, "w") as f:
        f.write(code)
