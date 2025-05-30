import os
import json
import pandas as pd
from typing import List, Dict, Any
import argparse
from pathlib import Path

def merge_summary_info(directory: str) -> List[Dict[str, Any]]:
    """合并指定目录下所有summary_info.json文件中的数据"""
    merged_data = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == "summary_info.json":
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        if isinstance(data, dict):
                            merged_data.append(data)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    merged_data.append(item)
                                else:
                                    print(f"警告: 文件 {file_path} 包含非字典项，已跳过")
                        else:
                            print(f"警告: 文件 {file_path} 格式不符合预期，已跳过")
                except Exception as e:
                    print(f"错误: 无法读取文件 {file_path}: {str(e)}")

    return merged_data


def process_to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """将合并后的数据转换为DataFrame并处理为透视表"""
    if not data:
        print("警告: 没有数据可处理")
        return pd.DataFrame()

    # 转换为DataFrame
    df = pd.DataFrame(data)

    # 组合rom_version和app_version作为列名
    df['version'] = df['rom_version'] + '+' + df['app_version']

    # 使用apply逐行处理step_id
    df['scene_name'] = df.apply(
        lambda row: f"{row['scene']}步骤{row['step_id']}: {row['step_name']}",
        axis=1
    )

    # 创建透视表，行=scene_name，列=version，值=count
    pivot_table = df.pivot_table(
        index='scene_name',
        columns='version',
        values='count',
        aggfunc='sum',  # 如果有重复值，使用求和聚合
        fill_value=0  # 空值填充为0
    )

    return pivot_table


def add_percentage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    添加百分比列，将第一列作为基线与后续每列进行比较

    Args:
        df: 原始透视表DataFrame

    Returns:
        添加了百分比列的DataFrame
    """
    if df.empty or len(df.columns) < 2:
        print("警告: 数据不足，无法计算百分比")
        return df

    # 获取基线列（第一列）
    baseline_col = df.columns[0]

    # 为除基线列外的每一列计算百分比
    for col in df.columns[1:]:
        # 计算百分比 (新值-基线值)/基线值*100%
        percentage_col = f"{col}_百分比"
        df[percentage_col] = ((df[col] - df[baseline_col]) / df[baseline_col])

        # 将百分比列放在对应数据列之后
        col_idx = df.columns.get_loc(col)
        df = df[[c for c in df.columns if c != percentage_col] + [percentage_col]]

    return df


def save_to_excel(df: pd.DataFrame, output_file: Path) -> None:
    """将DataFrame保存到Excel文件，并设置百分比格式"""
    if df.empty:
        print("错误: 没有数据可保存")
        return

    # 创建Excel写入器
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 写入数据
        df.to_excel(writer, sheet_name='Summary')

        # 获取工作表对象
        worksheet = writer.sheets['Summary']

        # 获取所有百分比列的索引
        percentage_cols = [i for i, col in enumerate(df.columns) if col.endswith('_百分比')]

        # 应用格式设置
        for row_idx in range(2, len(df) + 3):  # +2是因为Excel行从1开始，+1是因为有标题行
            for col_idx in percentage_cols:
                cell = worksheet.cell(row=row_idx, column=col_idx + 2)  # +2是因为Excel列从1开始，DataFrame索引从0开始
                cell.number_format = '0.00%'  # 设置为百分比格式

        # 调整列宽以适应内容
        for i, col in enumerate(df.columns):
            column_width = max(len(str(x)) for x in df[col])
            column_width = max(column_width, len(str(col))) + 2
            worksheet.column_dimensions[chr(65 + i + 1)].width = column_width  # A=65, B=66, ...

        # 调整第一列宽度
        first_col_width = max(len(str(x)) for x in df.index) + 2
        worksheet.column_dimensions['A'].width = first_col_width

    print(f"数据已成功导出到 {output_file}")
    print(f"透视表尺寸: {df.shape[0]}行 x {df.shape[1]}列")


def create_summary_excel(input_path: str) -> bool:
    try:
        if not os.path.isdir(input_path):
            print(f"错误: 目录 {input_path} 不存在")
            return False

        # 合并JSON数据
        merged_data = merge_summary_info(input_path)

        if not merged_data:
            print("错误: 没有找到任何summary_info.json文件或文件内容为空")
            return False

        # 处理为透视表
        pivot_df = process_to_dataframe(merged_data)

        # 确保有足够的列来计算百分比
        if len(pivot_df.columns) > 1:
            # 添加百分比列（以第一列为基线）
            pivot_df = add_percentage_columns(pivot_df)
            print(f"已计算相对于 {pivot_df.columns[0]} 的百分比增长")
        else:
            print("警告: 数据列不足，无法计算百分比增长")

        # 确定输出路径
        output_path = Path(input_path) / 'summary_pivot.xlsx'

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存到Excel
        save_to_excel(pivot_df, output_path)

        return True
    except  Exception as e:
        print("未知错误：没有生成汇总excel" + str(e))
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='将summary_info.json合并并转换为Excel透视表')
    parser.add_argument('--input', '-i', required=True, help='输入目录路径')
    parser.add_argument('--output', '-o', help='输出Excel文件路径')

    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"错误: 目录 {args.input} 不存在")
        exit(1)

    # 合并JSON数据
    merged_data = merge_summary_info(args.input)

    if not merged_data:
        print("错误: 没有找到任何summary_info.json文件或文件内容为空")
        exit(1)

    # 处理为透视表
    pivot_df = process_to_dataframe(merged_data)

    # 确保有足够的列来计算百分比
    if len(pivot_df.columns) > 1:
        # 添加百分比列（以第一列为基线）
        pivot_df = add_percentage_columns(pivot_df)
        print(f"已计算相对于 {pivot_df.columns[0]} 的百分比增长")
    else:
        print("警告: 数据列不足，无法计算百分比增长")

    # 确定输出路径
    output_path = Path(args.output) if args.output else Path(args.input) / 'summary_pivot.xlsx'

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存到Excel
    save_to_excel(pivot_df, output_path)
