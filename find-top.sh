#!/bin/bash

proj_dir="$1"
target_dir=""

if [ -d "$proj_dir/trunk/rtl" ]; then
    target_dir="$proj_dir/trunk/rtl"
elif [ -d "$proj_dir/trunk/src" ]; then
    target_dir="$proj_dir/trunk/src"
elif [ -d "$proj_dir/trunk/verilog" ]; then
    target_dir="$proj_dir/trunk/verilog"
elif [ -d "$proj_dir/rtl" ]; then
    target_dir="$proj_dir/rtl"
elif [ -d "$proj_dir/src" ]; then
    target_dir="$proj_dir/src"
elif [ -d "$proj_dir/verilog" ]; then
    target_dir="$proj_dir/verilog"
else
    if [ -d "$proj_dir/trunk" ]; then
        target_dir=$(find "$proj_dir/trunk" -type f -iname "*.v" | xargs -n1 dirname | sort | uniq -c | sort -nr | head -1 | awk '{print $2}')
    else
        target_dir=$(find "$proj_dir" -type f -iname "*.v" | xargs -n1 dirname | sort | uniq -c | sort -nr | head -1 | awk '{print $2}')
    fi
fi

find "$target_dir" -type f -iname "*.v" -not -path "*/bench/*" -not -path "*/sim/*" -not -path "*/formal/*" -not -path "*/testbench*"  > filelist.txt


# yosys -p "read_verilog -D SYNTHESIS $(cat filelist.txt | tr '\n' ' '); hierarchy -auto-top" | grep "Top module:"

filelist=$(cat filelist.txt | tr '\n' ' ')

while true; do
  yosys -p "read_verilog -D SYNTHESIS $filelist; hierarchy -auto-top" > yosys.log 2>&1
  if grep -q "ERROR:" yosys.log; then
    badfile=$(tac yosys.log | grep -m1 "^[0-9]\+\.\s\+Executing Verilog-2005 frontend:" | awk -F': ' '{print $2}')
    echo "移除錯誤檔案: $badfile"
    filelist=$(echo $filelist | tr ' ' '\n' | grep -v "$badfile" | tr '\n' ' ')
  else
    break
  fi
done

grep "$(grep "Top module:" yosys.log | head -1 | awk -F'\' '{print $2}')" filelist.txt