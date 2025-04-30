import csv

from online_search import OnlineSearcher

if __name__ == '__main__':

    location_result = ""

    # 对排名结果进行 csv 格式解析
    location_list = []
    csv_reader = csv.DictReader(location_result)
    # 遍历每一行记录
    for row in csv_reader:
        function_id = row['函数切片ID']
        location_list.append(function_id)

    fault_list = []
    top_1, top_3, top_5, mar, mfr = OnlineSearcher().evaluation(fault_list)
