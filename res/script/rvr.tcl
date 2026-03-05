package require cmdline

set arg1 [lindex $argv 0]
set arg2 [lindex $argv 1]
set arg3 [lindex $argv 2]

set e1 $arg1
set e2 $arg2
set ixchariot_installation_dir "D:/Program Files (x86)/Ixia/IxChariot"
set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"
set testFile "$ixchariot_installation_dir/tests/lbtest.tst"
set timeout 50

cd $ixchariot_installation_dir
# （1）加载Chariot包
load ChariotExt
package require ChariotExt

# （2）创建测试对象
set test [chrTest new]
set runOpts [chrTest getRunOpts $test]
chrRunOpts set $runOpts TEST_END FIXED_DURATION
chrRunOpts set $runOpts TEST_DURATION 30; #设置测试运行时间

#chrPair set $pair PROTOCOL TCP; #设置协议
#chrPair setScriptVar $pair file_size 1000000;#发送字节数
#chrPair setScriptVar $pair send_buffer_size 1500;#buffer大小
#chrPair setScriptVar $pair send_data_rate "20 Mb";#发送速率

for {set i 1} {$i <= $arg3} {incr i} {
    puts "Create the pair..."
    set pair [chrPair new]
    # 给测试对添加地址属性.
    puts "Set required pair attributes..."
    chrPair set $pair E1_ADDR $e1 E2_ADDR $e2
    # 给测试对定义测试脚本
    puts "Use a script..."
    chrPair useScript $pair $script
    # 把测试对添加到测试对象中.
    puts "Add the pair to the test..."
    chrTest addPair $test $pair
}

# （7）运行测试
chrTest start $test

# （8）等待测试结束
if {![chrTest isStopped $test $timeout]} {
 puts "ERROR: Test didn’t stop"
 chrTest delete $test force
 return
}

# （9）打印

puts "==========="
puts "Test setup:\n----------"
puts "Number of pairs = [chrTest getPairCount $test]"
puts "E1 address : [chrPair get $pair E1_ADDR]"
puts "E2 address : [chrPair get $pair E2_ADDR]"
# We didn’t set the protocol, but let’s show it anyway.
puts "Protocol : [chrPair get $pair PROTOCOL]"
# We’ll show both the script filename and
# the application script name.
puts "Script filename : [chrPair get $pair SCRIPT_FILENAME]"
puts "Appl script name: [chrPair get $pair APPL_SCRIPT_NAME]"

# （10）读取测试结果: 吞吐量
puts ""
puts "Test results:\n------------"
puts "Number of timing records = \
[chrPair getTimingRecordCount $pair]"

set throughput [chrPairResults get $pair THROUGHPUT]
set avg [format "%.3f" [lindex $throughput 0]]
set min [format "%.3f" [lindex $throughput 1]]
set max [format "%.3f" [lindex $throughput 2]]
puts "Throughput:"
puts "avg $avg min $min max $max"

# （11）保存测试结果
puts "Save the test..."
chrTest save $test $testFile

# （12）清理
chrTest delete $test force

return