import os
import csv


def count_newlines_in_folder_to_csv(folder_path, output_csv):
    try:
        # 检查文件夹是否存在
        if not os.path.isdir(folder_path):
            print(f"路径 {folder_path} 不是有效的文件夹。")
            return

        # 创建一个列表存储结果
        results = []

        # 遍历文件夹中的所有文件
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 打开并读取文件内容
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 统计换行符数量
                    newline_count = content.count('\n')
                    results.append((file_path, newline_count))
                except Exception as e:
                    print(f"处理文件 {file_path} 时出错: {e}")
                    results.append((file_path, "Error"))

        # 写入 CSV 文件
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # 写入标题行
            writer.writerow(['File Path', 'Line Count'])
            # 写入统计结果
            writer.writerows(results)

        print(f"结果已保存到 CSV 文件: {output_csv}")
    except Exception as e:
        print(f"处理文件夹时发生错误: {e}")


if __name__ == '__main__':
    # 替换为目标文件夹路径和输出 CSV 文件路径
    folder_path = "source_code"
    output_csv = "output.csv"
    count_newlines_in_folder_to_csv(folder_path, output_csv)
