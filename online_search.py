import csv
import json
import traceback
from io import StringIO
from typing import Set

import chromadb
from tenacity import retry, stop_after_attempt, wait_exponential

import llm
from get_source_code import get_contract_address_from_tx
from nx import GraphLoader
from tx_receipt import get_receipt_from_tx


class OnlineSearcher:

    def __init__(self):
        self.client = self.connect_client()
        self.contract_collection = self.get_collection("Contract", self.client)
        self.function_collection = self.get_collection("Function", self.client)

    def process(self, fault_txhash: str, faultless_txhash: str, _file, _platform):
        # 交易分析过程
        # 交易哈希列表初始化
        fault_txhash_list = fault_txhash.split(',')
        faultless_txhash_list = faultless_txhash.split(',')
        tx_list = fault_txhash_list + faultless_txhash_list
        tx_hash = {
            'fault': {'transaction_hash': fault_txhash_list},
            'faultless': {'transaction_hash': faultless_txhash_list}
        }

        # 获取合约地址
        address_list: Set[str] = set()
        for _hash in tx_list:
            address = get_contract_address_from_tx(_hash, _platform)
            if address is not None:
                address_list.add(address)
        if not address_list:
            print("\n-----------------------------------------\n获取的合约地址为空！\n")
            return

        print("正在获取资金流动和trace...\n")
        # 资金流动 + trace
        loader = GraphLoader()
        # loader.call_block_chain_spider(tx_list)
        # 读取 token20Transfer trace tokenProperty 文件并格式化
        token_transfer_csv_path = './BlockchainSpider/data/Token20TransferItem.csv'
        trace_csv_path = './BlockchainSpider/data/TraceItem.csv'
        tx_token_trans_str = ''
        tx_trace_str = ''
        for tx in tx_list:
            transfer_str, trace_str = loader.get_token_transfer_and_trace(token_transfer_csv_path, trace_csv_path, tx)
            tx_token_trans_str = tx_token_trans_str + tx + ': \n' + transfer_str + '\n'
            tx_trace_str = tx_trace_str + tx + ': \n' + trace_str + '\n'
        tx_token_property_path = './BlockchainSpider/data/TokenPropertyItem.csv'
        with open(tx_token_property_path, mode='r', encoding='utf-8') as file:
            tx_token_property_str = file.read()

        # 交易基本信息
        tx_receipt = {}
        tx_receipt_str = ''
        print("正在交易基本情况分析...\n")
        for tx in tx_list:
            tx_json = get_receipt_from_tx(tx)
            tx_json_str = json.dumps(tx_json)
            system_prompt = llm.load_prompt("prompt/tx_summary_system_prompt")
            user_prompt = llm.load_prompt("prompt/tx_summary_user_prompt") + tx_json_str
            tx_summary = llm.get_summary_from_llm(system_prompt, user_prompt)
            if tx_summary[0] != 'stop':
                print(tx + ' error! message:' + tx_summary[0])
            tx_summary = tx_summary[1]
            tx_receipt[tx] = {'summary': tx_summary}
            tx_receipt_str = tx_receipt_str + tx + ': ' + tx_summary + '\n'
            # print(tx + ": " + tx_summary)

        # 实时故障报告

        # 根据交易分析进行 query
        variables = {
            'tx_hash': str(tx_hash),
            'tx_receipt': tx_receipt_str,
            'tx_report': '',
            'tx_token_trans': tx_token_trans_str,
            'tx_trace': tx_trace_str,
            'tx_token_property': tx_token_property_str
        }
        print("正在交易故障情况分析...\n")
        system_prompt = llm.load_prompt("prompt/bug_summary_system_prompt")
        user_prompt = llm.load_prompt("prompt/bug_summary_user_prompt", variables)
        # print("------------------------------------------------" + "\n" + user_prompt)
        bug_summary = llm.get_summary_from_llm(system_prompt, user_prompt)
        if bug_summary[0] != 'stop':
            print(' error! message:' + bug_summary[0])
        bug_summary = bug_summary[1]
        # print("------------------------------------------------" + "\n" + bug_summary)
        _file.write("------------------------------------------------" + "\n交易故障分析：\n" + bug_summary)

        print("正在匹配向量库合约片段...\n")

        query_results = self.contract_collection.query(
            query_texts=[bug_summary],
            n_results=40,
            include=["distances", "documents", "metadatas"],
            where={"address": {"$in": list(address_list)}}
        )
        _file.write("\n------------------------------------------------" + "\n向量库匹配结果：\n" + str(query_results))
        # print(query_results)

        # 检索结果重排序
        print("正在进行重排序...\n")
        code_summary_list_str = ""
        code_summary_list = query_results['documents']
        _id_list = query_results['ids']
        metadata_list = query_results['metadatas']
        for _id, code_summary, metadata in zip(_id_list[0], code_summary_list[0], metadata_list[0]):
            code_summary_list_str = code_summary_list_str + "\n-----------------------------\n" + _id + ":\n" + "合约地址: " + str(metadata['address']) + "\n" + code_summary

        rerank_variables = {
            "bug_summary": bug_summary,
            "code_summary_list": code_summary_list_str
        }
        system_prompt = llm.load_prompt("prompt/rerank_summary_system_prompt")
        user_prompt = llm.load_prompt("prompt/rerank_summary_user_prompt", rerank_variables)
        rerank_result = llm.get_summary_from_llm(system_prompt, user_prompt, 2)
        if rerank_result[0] != 'stop':
            print(' error! message:' + rerank_result[0])
        rerank_result = rerank_result[1]
        std_rerank_result = json.loads(rerank_result)
        final_contracts = []
        if std_rerank_result is not None:
            rerank_list = std_rerank_result['result']
            for rerank in rerank_list:
                final_contracts.append(rerank['name'])

        _file.write("\n------------------------------------------------" + "\n重排序结果：\n" + str(final_contracts))

        print("正在进行结果定位...\n")

        function_str = ""
        for contract_name in final_contracts:
            function_list = self.function_collection.get(
                where={"belong": {"$eq": contract_name}}
            )
            contract = self.contract_collection.get(ids=contract_name)
            if len(contract.get('documents')) == 0:
                address = ''
            else:
                address = contract['metadatas'][0]['address']
            if len(function_list.get('documents')) == 0:
                continue
            ids = function_list.get('ids')
            metadatas = function_list.get('metadatas')
            documents = function_list.get('documents')
            for fid, metadata, document in zip(ids, metadatas, documents):
                function_str += "\n------------------------------------------------\n函数切片ID: " + fid + "\n所属合约地址" + address + "\n元数据:" + str(
                    metadata) + "\n函数切片:\n" + document

        _file.write("\n------------------------------------------------" + "\n函数切片：\n" + function_str)

        location_variables = {
            'bug_summary': bug_summary,
            'function_str': function_str,
        }
        system_prompt = llm.load_prompt("prompt/location_trace_chain_system_prompt")
        user_prompt = llm.load_prompt("prompt/location_trace_chain_user_prompt", location_variables)
        location_result = llm.get_summary_from_llm(system_prompt, user_prompt)
        if location_result[0] != 'stop':
            print(' error! message:' + location_result[0])
        location_result = location_result[1]
        # print("------------------------------------------------" + "\n" + rerank_result)
        _file.write("\n------------------------------------------------" + "\n故障定位结果：\n" + location_result)

        # # 对排名结果进行 csv 格式解析
        # location_list = []
        # csv_file = StringIO(location_result)
        # csv_reader = csv.DictReader(
        #     csv_file,
        #     fieldnames=["函数切片ID", "分数"],
        #     delimiter=','
        # )
        # # 遍历每一行记录
        # for row in csv_reader:
        #     function_id = row['函数切片ID']
        #     location_list.append(function_id)
        #
        # # 评估实验结果
        # top_1, top_3, top_5, mar, mfr = self.evaluation(location_list)
        # _file.write("top-1: " + str(top_1) + "\n")
        # _file.write("top-3: " + str(top_3) + "\n")
        # _file.write("top-5: " + str(top_5) + "\n")
        # _file.write("mar: " + str(mar) + "\n")
        # _file.write("mfr: " + str(mfr) + "\n")

        # # 最后进行汇总分析 + 原因解释
        # system_prompt = llm.load_prompt("")
        # user_prompt = llm.load_prompt("")
        # summary = llm.get_summary_from_llm(system_prompt, user_prompt)
        # return summary

    @retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1))
    def connect_client(self):
        # chromadb.HttpClient(host='47.102.102.136', port=8000)
        return chromadb.PersistentClient(path="./chroma")

    @retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1))
    def get_collection(self, name: str, client):
        return client.get_or_create_collection(name)

    def evaluation(self, location_result: list):
        # 查库确定故障函数排名
        rank = dict()
        rank_list = []
        for index, location_function in enumerate(location_result):
            func = self.function_collection.get(ids=location_function)
            if func is None or len(func['metadatas']) == 0:
                continue
            rank[location_function] = func['metadatas'][0]['is_fault']
            if rank[location_function] is True:
                rank_list.append(index + 1)

        if len(rank_list) == 0:
            return 0, 0, 0, 0, 0

        # Top-1
        top_1 = 0
        if rank_list[0] == 1:
            top_1 = top_1 + 1

        # Top-3
        top_3 = 0
        top_5 = 0
        for index, rank in enumerate(rank_list):
            if rank <= 3:
                top_3 = top_3 + 1
            if rank <= 5:
                top_5 = top_5 + 1

        # MAR
        sum_of_rank = 0
        for rank in rank_list:
            sum_of_rank = sum_of_rank + rank
        mar = sum_of_rank / len(rank_list)

        # MFR
        mfr = rank_list[0]

        return top_1, top_3, top_5, mar, mfr


if __name__ == '__main__':
    searcher = OnlineSearcher()
    fault_hash = '0x90fb0c9976361f537330a5617a404045ffb3fef5972cf67b531386014eeae7a9'
    faultless_hash = '0x7df39084b561ee2e7809e690f11e8e258dc65b6128399acbacf1f2433308de6a,0xddd734c1f3e097d3d1cdd7d4c0ffae166b39992a1d055008bf6660b8c0b7582e,0x5c1d151599bbacc19a09dfee888d3be2ccf3e2fa781679b9e0970e18b3300e44'
    for i in range(40):
        print("第" + str(i) + "次运行实验: \n")
        file_path = "night_data/" + str(i) + ".txt"
        try:
            # 主逻辑代码
            with open(file_path, "w", encoding="utf-8") as file:
                searcher.process(fault_hash, faultless_hash, file, "Ethereum")
        except Exception as e:
            try:
                # 异常处理代码（尝试写入异常信息到文件）
                with open(file_path, "a", encoding="utf-8") as file:  # 使用追加模式
                    file.write("\n\n--- 异常信息 ---\n")
                    traceback.print_exc(file=file)  # 写入完整堆栈跟踪

            except Exception as inner_e:
                # 如果连异常信息都写入失败，则打印到控制台
                print(f"无法写入异常信息到文件 {file_path}: {str(inner_e)}")
