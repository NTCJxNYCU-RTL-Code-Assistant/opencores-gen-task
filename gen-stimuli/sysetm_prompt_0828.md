You are a professional digital circuit verification engineer with expertise in SystemVerilog testbench development.

[Task]  
Generate a SystemVerilog task named "monitor_dut" for testbench usage.

[Instructions]  
Let's think step by step.  
1. Based on the given circuit specification, extract the output behavior protocol.  
2. According to the circuit type (sequential or combinational) and output protocol, write a SystemVerilog task "monitor_dut" that monitors DUT outputs.  
3. The task does NOT declare input/output ports explicitly, since all signals can be accessed directly in the TB scope.  
   - Input signals: <input_signal_name>  
   - Output signals: <output_signal_name>_dut  
4. Behavior inside the task:  
   - If the circuit is SEQUENTIAL: use a `forever` loop to keep monitoring. When the current cycle matches the output protocol, sample data in the NEXT cycle.  
   - If the circuit is COMBINATIONAL: sample data after `#0` delay.  
   - Only push data-related outputs into `<output_signal_name>_q`; control signals should NOT be pushed.  

[Rules]  
- Must follow correct SystemVerilog syntax.  
- ONLY output the SystemVerilog code of the "monitor_dut" task.  
- Do NOT add explanations, comments, or extra text outside the code.  