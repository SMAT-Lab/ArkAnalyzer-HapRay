# HapPerf

#### 使用说明
1.  unzip hap
    ```
    node happerf.core.js -p xxx.hap -o output
    ```
2.  负载拆解
    ```
    node hapray-cmd.js  hapray dbtools -i <inputh_path>
    ```
3.  负载拆解支持带so符号导入
    ```
    node hapray-cmd.js  hapray dbtools -i <inputh_path> -s <so_path>
    ```



