import openai
import weave
import os
from dotenv import load_dotenv
from typing import TypedDict

# from preprocess import preprocess_code
from generate import generate


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

    weave.init("opencores-gen-stimuli")

    root = "generated"

    class Todo(TypedDict):
        project: str
        spec_filepath: str
        tb_filepaths: list[str]

    todolist: list[Todo] = [
        {
            "project": "bubble_sort",
            "spec_filepath": "generated/bubble_sort/output.md",
            "tb_filepaths": [
                "opencores/bubble_sort_module/sim/rtl_sim/src/testbench.v",
            ],
        },
        {
            "project": "sha3",
            "spec_filepath": "generated/sha3/output.md",
            "tb_filepaths": [
                "opencores/sha3/high_throughput_core/testbench/test_keccak.v",
                "opencores/sha3/low_throughput_core/testbench/test_keccak.v",
            ],
        },
        {
            "project": "tate_bilinear_pairing",
            "spec_filepath": "generated/tate_bilinear_pairing/output.md",
            "tb_filepaths": [
                "opencores/tate_bilinear_pairing/testbench/test_tate_pairing.v",
            ],
        },
        {
            "project": "sdram_controller",
            "spec_filepath": "generated/sdram_controller/output.md",
            "tb_filepaths": [
                "opencores/sdram_controller/verif/tb/tb_top.sv",
            ],
        },
    ]

    for todo in todolist:
        tb_project = todo["project"]
        spec_filepath = todo["spec_filepath"]
        tb_filepaths = todo["tb_filepaths"]

        os.makedirs(f"{root}/{tb_project}", exist_ok=True)

        for i, tb_filepath in enumerate(tb_filepaths):
            try:
                print(f"Preprocessing {tb_filepath}...")
                with open(tb_filepath, "r") as f:
                    code = f.read()
                # code = preprocess_code(code)
                # with open(f"{root}/{tb_project}/preprocess_{i}.sv", "w") as f:
                #     f.write(f"// {tb_filepath}\n{code}")

                # print(f"Generating {tb_filepath}...")
                code = generate(model, code, spec_filepath)
                with open(f"{root}/{tb_project}/task_{i}.sv", "w") as f:
                    f.write(f"// {tb_filepath}\n{code}")
            except Exception as e:
                print(f"錯誤：{e}")
                continue
