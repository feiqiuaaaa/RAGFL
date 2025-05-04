import chromadb

import llm

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./chroma")
    contract_collection = client.get_or_create_collection("Contract")
    function_collection = client.get_or_create_collection("Function")

    bug_summary = ''
    final_contracts = ['Visor Finance-vVISR.sol', 'Visor Finance-Ownable.sol', 'Visor Finance-ERC20.sol', 'Visor Finance-SafeMath.sol', 'Visor Finance-Address.sol', 'Visor Finance-SafeERC20.sol', 'Visor Finance-Context.sol', 'Visor Finance-ERC20Snapshot.sol']
    function_str = ""
    for contract_name in final_contracts:
        function_list = function_collection.get(
            where={"belong": {"$eq": contract_name}}
        )
        contract = contract_collection.get(ids=contract_name)
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

    location_variables = {
        'function_str': function_str
    }
    system_prompt = llm.load_prompt("prompt/without_bug_summary_system_prompt")
    user_prompt = llm.load_prompt("prompt/without_bug_summary_user_prompt", location_variables)
    location_result = llm.get_summary_from_llm(system_prompt, user_prompt)
    if location_result[0] != 'stop':
        print(' error! message:' + location_result[0])
    location_result = location_result[1]
    # print("------------------------------------------------" + "\n" + rerank_result)
    print("\n------------------------------------------------" + "\n故障定位结果：\n" + location_result)
