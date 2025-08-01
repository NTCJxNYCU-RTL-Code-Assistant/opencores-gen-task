Bubble Sort

IP Core Specification

_Author: avram ionut_

_avramionut@opencores.org_

**Rev. 0.1**

**March 28, 2014**_This page has been intentionally left blank._

**Revision History**

## Chapter 1 IntroductionIntroduction

_This is an extreme useful and clear specifications document wannabe._

_It describes the interface, internal structure and functionality of Probably the Best Sorting Module in the World. I am aware that there are people that may not agree to that so I decided to call it: Bubble Sort. This is in part due to the fact that it implements the bubble sorting algorithm._

_The module is written in Verilog; no VHDL version planned._

_Probably the Best Sorting Module in the World in intended to be independent of any bus so there is no code to ensure the data transfers. It is left to the user of the module to attach it to the preferred bus._

_The internal structure is very simple. It resembles a chain and it is designed for fast clk._

_Simple structure brings simple functionality: standard bubble sort algorithm is in place, no fancy optimizations, only limitations: the module is capable of sorting only unsigned words of N_BITS bits._

_The code is released under LGPL as recommended by opencores.org._

## Chapter 2 Interface

_The interface of the module is:_

\begin{tabular}{|p{142.3pt}|p{142.3pt}|p{142.3pt}|} \hline _Signal_ & _Direction_ & _Comments_ \\ \hline _clk_ & _input_ & _No comments_ \\ \hline _rst_ & _input_ & _Active high_ \\ \hline _load_i_ & _input_ & _Array_. Active high. Control the load of new data inside the sorting module._ \\ \hline _writedata_i_ & _input_ & _Array_. Provides new data to the sorting module._ \\ \hline _start_i_ & _input_ & _Active high. Triggers the sorting process._ \\ \hline _abort_i_ & _input_ & _Not used._ \\ \hline _readdata_o_ & _output_ & _Array_. Expose sorted data outside the sorting module._ \\ \hline _done_o_ & _output_ & _Active high. Indicates the end of sorting process._ \\ \hline _interrupt_o_ & _output_ & _Active high. Indicates the validity of the output data._ \\ \hline \end{tabular}

_The user should make sure there are no additional start_i pulses from the start of sorting process until the end of sorting indicated by a pulse on interrupt_o._

_The user is advised to not read readdata_o until the end of process indicated by a pulse on interrupt_o. Information on readdata_o wires is garbage during the sorting process as it reflects the content of registers during shifting process.__The user should consider the ending of sorting process indicated by a pulse of interrupt_o signal. The signal done_o is exposed to provide an early indication of the process end._

_The user can tie the done_o signal to the interrupt controller and use it to launch the data reading procedure on a slow system or for systems that have significant latency._

_Please see below an imaginary use case of the sorting module:_

1. _bring valid data to the writedata_i;_
2. _load data with a positive pulse on load_i;_
3. _start sorting with a positive pulse on start_i;_
4. _watch done_o or interrupt_o for positive pulse;_
5. _retrieve data from readdata_o;_

## Chapter 3 Architecture

_The architecture is a chain of simple modules alongside 2 control blocks. The number of modules is set by parameter K_NUMBERS._

_The control blocks are module intgenerator and module rungenerator._

_Rungenerator is a shift register controlled by start_i and all_sorted_i signals._

_Intgenerator is made from an edge select and a counter._

_Stage modules are made from a shift register and a comparator. The size of the shift register is set by parameter N_BITS. The shift register has parallel load capabilities.__That's all; simple works best._

## Chapter 4 Operation

_Here is described the normal operation of Bubble Sort hardware, assuming the unsorted data is already loaded in the module, until the moment when all data is sorted. Reset and abort are not discussed. Load and retrieve of data are straightforward and no further details are needed._

_At the arrival of start_i positive pulse the rungenerator module starts to generate a continuous train of wide run pulses until brought to stop by the all_sorted_i signal. The run pulses are delivered to the K_NUMBERS stages by run_o._

_During the run pulse, at each clk rising edge, each stage module is taking one bit from the shift register and compare it with the bit from bit_i input. The compare module inside each stage is self locking when a valid compare decision can be done. Lets name An the number stored in internal register of the stage and Bn the number arriving at bit_i input. The bits of the largest number of An and Bn will be sent out through bit_o output to reach bit_i input of the next stage. The bits of the smallest number will be sent through value_o to be stored back in a shift register. This makes a An number that is not moved by the sorting process to be shifted through next stage module before being brought back to the holding shift register._

_This way, at each run pulse, a stage module is comparing an input number with the one stored inside and deliver to the next stage the largest of the 2 just as in bubble sort software algorithm._

_Each stage module is also propagating the run signal to the next stage ensuring parallel operation of stages. The second propagated signal is the swap signal. This is active high and indicates a swap of numbers taking place during current or a previous stage._

_Both run and swap signals provided by the last stage module are used by the intgenerator module to decide the end of sorting process. Just as in software the bubble sort, it is considered achieving the goal when no swapping takes place. The intgenerator stops the run wide pulses by done_o signal generated by missing swap indication at falling edge of the run signal._

_The done_o output of intgenerator linked to the all_sorted_i input of the rungenerator module is only stopping the generation of run signal, while, due to the chain architecture, the run pulses previously generated will continue to propagate from stage to stage. Even_if no swapping will take place, the stage modules will be shifting data so the readdata_o will become valid word by word as the run signal moves away. To indicate all readdata_o words are ready, the intgenerator module counts the done pulses and when it reaches the estimated value it generates a pulse on the signal interrupt_o. At this point the data should be read from the module before writing any new unsorted array.

## Chapter 5 Clock

_This sorting module was built with speed in mind so the clk can be run at high speeds. Running from the clock of the bus will probably be a bad idea. To benefit from the design, a faster clk should be dedicated to this module._

_So, even if this module is presented as a synchronous single clk design in practice it will end as a multi clock project._

## Chapter 5 Final chapter

_The sorting module is simple and this makes it probably the best sorting module in the world, alongside other features:_

* _small area required;_
* _area increases linearly with word size and number of words;_
* _fclk_max does not depend on the word size or number of words (ok, there is not absolute independence as far as the placement is affecting fclk_max);_

_There are some issues; some are by design, like:_

* _variable duration of sorting dependent on the data to be sorted;_
* _clock problems due the fast clock imposed by the serial nature of the design;_

_Some of the limitations are easy to overcome, please see the list below._

_For the enthusiastic student/hobbyist:_

* _can you make it faster (any of: clk speed or number of clk periods is ok as long as the area does not grow excessively)?_
* _can you make it work with signed numbers?_
* _can you extend it to {key,value}_?_
* _can you implement abort_i functionality?_

_I hope you will have at least as much fun playing with it as I had writing it._

_Thank you._

_PS: There is a trick in the code so any student willing to drop it on the homework without studying it, will have a surprise._

_PS PS: Let me rephrase: there is a chance that the module have more than a trick - nobody is perfect. If you spot any issues please use the email on the front page. Thank you._