from preprocess import preprocess_code


if __name__ == "__main__":
    with open("opencores/sha3/high_throughput_core/testbench/test_keccak.v", "r") as f:
        code = f.read()

    lines = preprocess_code(code)

    with open("temp/statements.txt", "w") as f:
        f.write("\n".join(lines))
