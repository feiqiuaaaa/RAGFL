import chromadb

import llm

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./chroma")
    contract_collection = client.get_or_create_collection("Contract")
    function_collection = client.get_or_create_collection("Function")

    bug_summary = '一、关键异常点\n1. 故障交易中，Uniswap V2池（0x0d4a11d5...）转出2亿USDT至中间合约（0xd02c260f...），随后中间合约向代币合约（0xcb6afdc8...）转入1亿USDT，同时代币合约铸造并转出1e19数量级的高精度代币（Formation USD），最终销毁等量代币，形成虚假流动性操作。\n2. 代币合约（0xcb6afdc8...）存在无限授权风险，允许任意地址铸造代币，且在交易中未验证调用者权限，导致攻击者通过中间合约操控代币供应量。\n3. 资金流动路径异常：USDT从流动性池被大量提取后，未按正常兑换比例生成对应代币，而是通过多次调用代币合约的未受控函数（如0x6e553f65、0x6f1a366d）完成高额代币铸造与销毁，形成套利漏洞。\n\n二、漏洞原因分析\n1. **代币合约权限控制缺失**：Formation USD代币合约（0xcb6afdc8...）的铸造函数（如Mint）未设置权限验证，攻击者通过中间合约（0xd02c260f...）直接调用铸造函数，生成任意数量代币，随后利用销毁或流动性操作将虚假代币转换为真实USDT。\n2. **Uniswap V2池价格操控**：攻击者通过大额USDT注入流动性池，利用代币合约的无限铸造能力，人为扩大代币供应量并操纵池内价格，随后通过Swap事件以极低比例兑换回USDT，完成套利。\n3. **重入或回调漏洞**：在调用Uniswap V2池的Swap函数（0x022c0d9f）时，代币合约未对回调函数（如uniswapV2Call）进行重入防护，导致攻击者在单次交易中重复触发代币铸造与兑换逻辑，放大资金泄露。\n\n三、攻击路径还原\n1. **授权阶段**：攻击者授权中间合约无限操作USDT（Approval事件），为后续大额转账铺路。\n2. **流动性操控**：调用Uniswap V2池的Swap函数，输入2亿USDT，触发代币合约的铸造逻辑，生成1e19 Formation USD代币（实际价值远高于输入USDT）。\n3. **代币套现**：将铸造的代币通过销毁或虚假流动性操作（Sync事件）转换为USDT，最终将99,799,397,652 USDT转回攻击者地址（0x6510438a...），完成资金窃取。\n\n四、trace调用链（故障交易）\n1. 0x6510438a7e273e71300892c6faf946ab3b04cbcb → 0xd02c260f54997146c9028b2ac7144b11ce4c20a6（授权调用）\n2. 0xd02c260f54997146c9028b2ac7144b11ce4c20a6 → 0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852（Uniswap V2 Swap）\n3. 0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852 → 0xdac17f958d2ee523a2206206994597c13d831ec7（USDT转账）\n4. 0xd02c260f54997146c9028b2ac7144b11ce4c20a6 → 0xcb6afdc84e8949ddf49ab00b5b351a5b0f65a723（代币铸造/销毁）\n5. 0xd02c260f54997146c9028b2ac7144b11ce4c20a6 → 0x6510438a7e273e71300892c6faf946ab3b04cbcb（USDT最终回流）'
    final_contracts = ['Formation.Fi-Vault.sol', 'Formation.Fi-ERC20.sol', 'Formation.Fi-SafeERC20.sol', 'Formation.Fi-Ownable.sol', 'Formation.Fi-ReentrancyGuard.sol', 'Formation.Fi-IERC20.sol', 'Formation.Fi-IERC20Metadata.sol', 'Formation.Fi-Address.sol']
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
    print("\n------------------------------------------------" + "\n故障定位结果：\n" + location_result)
