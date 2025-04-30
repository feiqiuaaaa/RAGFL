import csv
import subprocess
import time
from io import StringIO

import networkx
import networkx as nx
from web3 import Web3
import matplotlib.pyplot as plt
import sys
from pathlib import Path
import os


class GraphLoader:
    def __init__(self):
        # 初始化 web3 对象
        w3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/1277d00f1f424cbb9212838bb034a8ce"))
        assert w3.is_connected(), "Failed to connect to Ethereum node!"
        self.w3 = w3

    def get_address_of_sub_graph(self, txs: list) -> []:
        add_set = set()
        # 添加节点（交易哈希）
        for tx in txs:
            # 获取交易的发送者和接收者以创建边
            tx_detail = self.w3.eth.get_transaction(tx)
            from_address = tx_detail['from']
            to_address = tx_detail['to']
            add_set.add(from_address)
            add_set.add(to_address)
        return list(add_set)

    def save_networkx_to_mermaid_md(self, graph: nx.DiGraph) -> str:
        # 处理节点，生成Mermaid节点定义
        nodes = []
        for node, data in graph.nodes(data=True):
            node_id = str(node).replace(' ', '_').replace(':', '_').replace('-', '_')  # 替换特殊字符
            # 拼接节点属性
            attrs = [f'{k}: {v}' for k, v in data.items()]
            node_label = ', '.join(attrs) if attrs else ''
            nodes.append(f'    {node_id}["{node_label}"]')

        # 处理边，生成Mermaid边定义
        edges = []
        for u, v, data in graph.edges(data=True):
            u_id = str(u).replace(' ', '_').replace(':', '_').replace('-', '_')
            v_id = str(v).replace(' ', '_').replace(':', '_').replace('-', '_')
            # 提取哈希和标签
            edge_label = []
            if 'hash' in data:
                edge_label.append(f'hash: {data["hash"]}')
            if 'label' in data:
                edge_label.append(f'label: {data["label"]}')
            edge_label = '<br>'.join(edge_label)
            edges.append(f'    {u_id} -->|"{edge_label}"| {v_id}')

        # 组合Mermaid代码
        mermaid_code = '\n'.join(nodes + edges)

        return f'```mermaid\n{mermaid_code}\n```\n'

    def call_block_chain_spider(self, hash_list: []):
        project_root = Path(__file__).parent
        try:
            spider_dir = os.path.join(project_root, 'BlockChainSpider')
            os.chdir(spider_dir)
            hash_str = ','.join(hash_list)
            cmd = [
                'scrapy',
                'crawl', 'trans.evm',
                '-a', 'hash=' + hash_str,
                '-a',
                'enable=BlockchainSpider.middlewares.trans.TraceMiddleware,BlockchainSpider.middlewares.trans.TokenTransferMiddleware,BlockchainSpider.middlewares.trans.TokenPropertyMiddleware',
                '-a', 'out=./data'
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in process.stdout:
                print(line, end='')
            return_code = process.wait()
            if return_code != 0:
                os.chdir(project_root)
                raise subprocess.CalledProcessError(return_code, cmd)
        except Exception as e:
            print(f"执行失败: {str(e)}")
            raise
        finally:
            os.chdir(project_root)

    def create_transaction_graph(self, graph_path: str, important_graph_path: str) -> networkx.DiGraph:
        # 初始化有向图
        graph = nx.DiGraph()

        node_list = {}
        with open(important_graph_path, 'r', encoding='utf-8') as important_graph_file:
            csv_reader = csv.DictReader(important_graph_file)
            # 遍历每一行记录
            for row in csv_reader:
                node = row['node']
                importance = row['importance']
                node_list[node] = {'importance': importance}

        with open(graph_path, 'r', encoding='utf-8') as graph_file:
            csv_reader = csv.DictReader(graph_file)
            # 遍历每一行记录
            for row in csv_reader:
                # 提取发送方和接收方地址
                from_addr = row['from']
                to_addr = row['to']

                # 检查 from 或 to 是否在 node_list 中
                if from_addr in node_list and to_addr in node_list:
                    graph.add_node(from_addr, importance=node_list[from_addr]['importance'])
                    graph.add_node(to_addr, importance=node_list[to_addr]['importance'])
                    graph.add_edge(from_addr, to_addr)

        return graph

    def get_token_transfer_and_trace(self, token_transfer_path: str, trace_path: str, _hash: str) -> tuple:
        token_transfer_list = []
        with open(token_transfer_path, 'r', encoding='utf-8') as token_transfer_file:
            csv_reader = csv.reader(token_transfer_file)
            header = next(csv_reader)  # 提取表头
            token_transfer_list.append(header)
            # 遍历每一行记录
            for row in csv_reader:
                if row[6] == _hash:
                    token_transfer_list.append(row)

        transfer_io = StringIO()
        writer = csv.writer(transfer_io, lineterminator='\n')
        writer.writerows(token_transfer_list)
        transfer_str = transfer_io.getvalue()
        transfer_io.close()

        trace_list = []
        with open(trace_path, 'r', encoding='utf-8') as trace_file:
            csv_reader = csv.reader(trace_file)
            header = next(csv_reader)  # 提取表头
            trace_list.append(header)
            # 遍历每一行记录
            for row in csv_reader:
                if row[10] == _hash:
                    trace_list.append(row)

        trace_io = StringIO()
        writer = csv.writer(trace_io, lineterminator='\n')
        writer.writerows(trace_list)
        trace_str = trace_io.getvalue()
        trace_io.close()
        return transfer_str, trace_str

    def get_token_property(self, path: str, _hash: str) -> str:
        with open(path, mode='r', encoding='utf-8') as file:
            return file.read()


if __name__ == '__main__':
    fault_txhash = '0x90fb0c9976361f537330a5617a404045ffb3fef5972cf67b531386014eeae7a9'
    faultless_txhash = '0x7df39084b561ee2e7809e690f11e8e258dc65b6128399acbacf1f2433308de6a,0xddd734c1f3e097d3d1cdd7d4c0ffae166b39992a1d055008bf6660b8c0b7582e,0x5c1d151599bbacc19a09dfee888d3be2ccf3e2fa781679b9e0970e18b3300e44'

    fault_txhash_list = fault_txhash.split(',')
    faultless_txhash_list = faultless_txhash.split(',')
    tx_hash = {
        'fault': {'transaction_hash': fault_txhash_list},
        'faultless': {'transaction_hash': faultless_txhash_list}
    }

    # 获取交易哈希中涉及的交易地址
    address_list = GraphLoader().get_address_of_sub_graph(tx_hash)

    # address_list = ['0xeb31973e0febf3e3d7058234a5ebbae1ab4b8c23',
    #                 '0xE11fc0B43ab98Eb91e9836129d1ee7c3Bc95df50',
    #                 '0xE5350E927B904FdB4d2AF55C566E269BB3df1941',
    #                 '0xe2Bb94210B41Ce4c01B9B97f3Ac62E728E472f9C']
    GraphLoader().call_block_chain_spider(address_list)

    # 读取 csv 文件并生成 DiGraph
    for address in address_list:
        csv_path = './BlockchainSpider/data/' + address + '.csv'
        important_csv_path = './BlockchainSpider/data/importance/' + address + '.csv'
        sub_graph = GraphLoader().create_transaction_graph(csv_path, important_csv_path)

        # 保存子图信息
        result = GraphLoader().save_networkx_to_mermaid_md(sub_graph)

        import matplotlib

        matplotlib.use('TkAgg')
        nx.draw(sub_graph, with_labels=True)
        plt.show()
