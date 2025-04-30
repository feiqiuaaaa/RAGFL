import requests
import json
from web3 import Web3
import chromadb
import llm

ETHERSCAN_API_KEY = '4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE'


# 获取交易的合约地址
def get_receipt_from_tx(tx_hash) -> dict:
    # tx = web3.eth.get_transaction_receipt(tx_hash)
    url = f'https://api.etherscan.io/api?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={ETHERSCAN_API_KEY}'
    response = requests.get(url)
    data = response.json()
    if data['result'] is not None:
        return data['result']


if __name__ == '__main__':
    trans = [
        "0x90fb0c9976361f537330a5617a404045ffb3fef5972cf67b531386014eeae7a9",
        "0x0af5a6d2d8b49f68dcfd4599a0e767450e76e08a5aeba9b3d534a604d308e60b",
        "0xcec93808a657d00cbb0245711e9419d0ea278b3a60a9a6d0a8c3353523c0e982",
        "0xe0527f7befaea54257113a09c8b3f4cd416e11a0e196cd2ba2e5e07c47767ddf"
    ]
    # tran = "0x5c1d151599bbacc19a09dfee888d3be2ccf3e2fa781679b9e0970e18b3300e44"

    for tran in trans:
        tx_json = get_receipt_from_tx(tran)
        tx_json_str = json.dumps(tx_json)

        # 调用大模型生成总结信息
        system_prompt = llm.load_prompt("prompt/tx_summary_system_prompt")
        user_prompt = llm.load_prompt("prompt/tx_summary_user_prompt") + tx_json_str
        tx_summary = llm.get_summary_from_llm(system_prompt, user_prompt)
        if tx_summary[0] != 'stop':
            print(tran + ' error! message:' + tx_summary[0])
        tx_summary = tx_summary[1]
        print(tran + ": " + tx_summary)

        # # 将交易分析放入 Transaction 集合中
        # client = chromadb.HttpClient(host='47.102.102.136', port=8000)
        # collection = client.get_or_create_collection("Transaction")
        # collection.add(
        #     documents=[tx_summary],
        #     ids=[tran]
        # )

        # res = collection.get(ids=["0x5c1d151599bbacc19a09dfee888d3be2ccf3e2fa781679b9e0970e18b3300e44"])
        # print(res)
