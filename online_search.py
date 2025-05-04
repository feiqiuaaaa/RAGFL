import json
import time
import traceback
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
            code_summary_list_str = code_summary_list_str + "\n-----------------------------\n" + _id + ":\n" + "合约地址: " + str(
                metadata['address']) + "\n" + code_summary

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
                metadata['is_fault'] = ''
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
    # SushiSwap
    # fault_hash = '0x90fb0c9976361f537330a5617a404045ffb3fef5972cf67b531386014eeae7a9'
    # faultless_hash = '0x7df39084b561ee2e7809e690f11e8e258dc65b6128399acbacf1f2433308de6a,0xddd734c1f3e097d3d1cdd7d4c0ffae166b39992a1d055008bf6660b8c0b7582e,0x5c1d151599bbacc19a09dfee888d3be2ccf3e2fa781679b9e0970e18b3300e44'

    # Alchemix
    # fault_hash = '0x3e86045bb9cde8f8cfcb5d943df531c7e68370c2d71cd631b1cee0950cf068f5,0xed3ea69b36024afb5389c3b940d46108a13fd31212992229d5c8257769cf8eeb,0x73df02bb2372d5a1f4278eb84d8222f90e12e4d0c9131c5831d0e62587bbe1bb,0x4fa64411ccd2982c43947a54b8e780ea6523da5c7e0c9545bf85697422b21577,0x3cc071f9f40294bb250fc7b9aa6b2d7e6ca5707ce4d6d222157d7a0feef618b3,0x38ecc8363836e43aca99d994bb9325a8f3770d7a1d1fffd62c82cf5230525836'
    # faultless_hash = '0x115f9ad8c58e5019a8bbd77202970b9306ec3bff66b9861a14e92d099e3c2336'

    # Cover
    # fault_hash = '0xd721b0ef2886f14b75548b70d2d1fd82bea085ca24f5de29b833a64cfd8f7a50,0xadf27f5dd052482d46fdf69a5208a27cc7352522c7c19bbde5aee18f6ea4373b'
    # faultless_hash = '0x3b3800548aa30b098c1f917ee70bd971b1d9eee2c786b8e8deddba220a65e441,0x326ed6982d3969f91f7817f75dd1754ff25c9556cc6d6bc80d6871b9185e676d'

    # Formation.Fi
    # fault_hash = '0xa992b28ecf2eed778d20d5200946ea341b950be0c3d78b1f2237a4d8d795de95'
    # faultless_hash = '0x94beaa5113b61e99677ec4039928c52b406a021e2b8845e32f4461ca29739665,0x9286c5ef4abf97bc0d9e2aa7fbd8187f7484985da5a285bac9516b4b89709b77,0x97681e7949557faa35caacbee7105ca4a749e8a838f9d30caa2a39a521125b4a'

    # Visor Finance
    # fault_hash = '0x27f2210536553392cf180c0b37055b3dc92094a5d585d7d2a51f790c9145e47c,0x69272d8c84d67d1da2f6425b339192fa472898dce936f24818fda415c1c1ff3f'
    # faultless_hash = '0x24e276cfc0cbd280a71da775ae35da39a107b97f819a3b2cd7cb40e9cc3afb82,0xcf762a8f4502cbeb4ab79626cc5a7c65c6dde5b487c8fa9b58f421e10e4807e8'

    # Umbrella Network
    fault_hash = '0x33479bcfbc792aa0f8103ab0d7a3784788b5b0e1467c81ffbed1b7682660b4fa'
    faultless_hash = '0xa2c40c7c1dce77c4290ecab357fc930dcdf524351767ebfa6faa9e19667d7c87,0x935ca4702e375fb713a67cf55a68600a6a094c3ed17953d7a267490d3bd99f90,0x7792a175c1ec0c7541d0e58b9b107641b4c506daeb651c3f0eb4e7b96625cfdf'

    # Fortress Protocol
    # fault_hash = '0x13d19809b19ac512da6d110764caee75e2157ea62cb70937c8d9471afcb061bf'
    # faultless_hash = '0x3805353291c4195347c84ec69d041bfffd233048e83eeaf75a5a5c9133774cc7,0x1201f84fbac94b8b494c53c6ab654777f9cf10c7228a215dc61b7fafe2eb770d,0x988f458a492ba28455afd4a038860e4cb2ee2484b41e60e1f8283bfcea9ee241'

    for i in range(20):
        print("第" + str(i) + "次运行实验: \n")
        file_path = "night_data/" + str(i) + ".txt"
        try:
            # 主逻辑代码
            with open(file_path, "w", encoding="utf-8") as file:
                start_time = time.time()  # 开始计时！
                searcher.process(fault_hash, faultless_hash, file, "Ethereum")
                end_time = time.time()  # 结束计时！
                elapsed_time = end_time - start_time  # 计算经过的时间
                file.write('\n------------------------------------\n运行时间:' + str(elapsed_time) + 'seconds')
        except Exception as e:
            try:
                # 异常处理代码（尝试写入异常信息到文件）
                with open(file_path, "a", encoding="utf-8") as file:  # 使用追加模式
                    file.write("\n\n--- 异常信息 ---\n")
                    traceback.print_exc(file=file)  # 写入完整堆栈跟踪

            except Exception as inner_e:
                # 如果连异常信息都写入失败，则打印到控制台
                print(f"无法写入异常信息到文件 {file_path}: {str(inner_e)}")
