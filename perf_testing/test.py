import os
import sys

# 将 perf_testing 设置为根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from aw.Utils import generate_hapray_report

def main():
    # 直接使用场景目录路径
    scene_dir = 'perf_output/wechat001'
    
    print(f"Testing generate_hapray_report function...")
    print(f"Scene directory: {scene_dir}")
    
    # 调用函数生成报告
    success = generate_hapray_report(scene_dir)
    
    # 输出结果
    if success:
        print("Test passed: Report generated successfully")
    else:
        print("Test failed: Failed to generate report")


if __name__ == "__main__":
    main()

