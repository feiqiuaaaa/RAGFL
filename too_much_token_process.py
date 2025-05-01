import chromadb

import llm

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./chroma")
    contract_collection = client.get_or_create_collection("Contract")
    function_collection = client.get_or_create_collection("Function")

    bug_summary = '一、关键异常点\n1. 故障交易（0x90fb0c9976...）中，WBTC/WETH流动性池（0x9a13867...）出现异常代币转移：从路由合约（0xe11fc0b...）转入345,678,860聪WBTC后立即销毁等量代币，同时铸造53,612聪WBTC到路由合约，显示可能存在流动性池储备操控。\n2. 同一交易中，路由合约向WBTC/WETH交易对（0xceff517...）转入344,578,316聪WBTC后，接收8.88 WETH的兑换输出，但后续WETH转移至SUSHI质押合约（0x8798249...）时数额异常放大至82,959,161,476,883,201,166 Wei（约82.95 WETH），存在代币数量计算错误。\n3. 非故障交易（如0x7df39084b5...）均涉及代币销毁与铸造操作，但仅故障交易出现流动性池Sync事件后的储备量失衡（WBTC池减少超30万聪，WETH池同步异常增长）。\n\n二、漏洞原因分析\n该漏洞源于路由合约（0xe11fc0b...）的闪电贷回调函数未正确验证调用者权限，导致攻击者通过以下步骤实施攻击：\n1. **闪电贷滥用**：攻击者通过路由合约发起闪电贷，借入WBTC后立即触发流动性池的Swap操作，利用池中代币价格偏差进行套利。\n2. **储备操控漏洞**：当路由合约调用流动性池的sync()函数更新储备时，攻击者通过恶意合约在同步前后插入代币转移操作（如0x9a13867...的Transfer事件），使实际储备量与记录值出现偏差。\n3. **算术溢出攻击**：在WETH兑换SUSHI阶段（0x795065d...的Swap事件），攻击者利用代币精度差异（WBTC为8位，WETH为18位），通过大额输入触发兑换计算溢出，导致SUSHI输出量异常增加（最终获得14,662,164,108,074,804,165,472 SUSHI，约1.46e+22）。\n4. **权限缺失**：路由合约未对质押操作（转入0x8798249...）实施代币所有权验证，使得攻击者可直接转移异常获得的SUSHI至质押合约完成获利。\n\n三、攻击路径还原\n1. 攻击者调用路由合约发起闪电贷，借入345,678,860聪WBTC。\n2. 在闪电贷回调中，将WBTC转入WBTC/WETH流动性池，触发Swap操作兑换WETH，利用sync前后的储备量差异获取超额WETH（8.88→82.95）。\n3. 将异常获得的WETH转入SUSHI/WETH池，通过算术溢出漏洞兑换巨额SUSHI。\n4. 最终通过路由合约将SUSHI质押至xSUSHI合约（0x8798249...），完成资金沉淀。\n\n四、trace调用链（故障交易）\n0x51841d9afe10fe55571bdb8f4af1060415003528 → 0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50 → 0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac → 0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3 → 0x2260fac5e5542a773aa44fbcfedf7c193bc2c599 → 0xceff51756c56ceffca006cd410b03ffc46dd3a58 → 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 → 0x795065dcc9f64b5614c407a6efdc400da6221fb0 → 0x6b3595068778dd592e39a122f4f5a5cf09c90fe2 → 0x8798249c2e607446efb7ad49ec89dd1865ff4272'
    final_contracts = ['SushiSwap-SushiBar.sol', 'SushiSwap-SushiMaker.sol', 'SushiSwap-IUniswapV2Pair.sol', 'SushiSwap-UniswapV2Pair.sol', 'SushiSwap-IUniswapV2Router02.sol', 'SushiSwap-UniswapV2Router02.sol', 'SushiSwap-IUniswapV2Callee.sol', 'SushiSwap-MasterChef.sol', 'SushiSwap-SafeERC20.sol', 'SushiSwap-UniswapV2Library.sol', 'SushiSwap-Address.sol', 'SushiSwap-SafeMath.sol', 'SushiSwap-SushiToken.sol', 'SushiSwap-IUniswapV2Router01.sol', 'SushiSwap-Timelock.sol', 'SushiSwap-Ownable.sol', 'SushiSwap-TransferHelper.sol']
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
