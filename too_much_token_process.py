import chromadb

import llm

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./chroma")
    contract_collection = client.get_or_create_collection("Contract")
    function_collection = client.get_or_create_collection("Function")

    bug_summary = "一、关键异常点\n1. 故障交易（0x90fb0c...）在兑换路径中出现极端滑点：在地址0xf41e354eb138b328d56957b36b7f814826708724的流动性池中，输入1,529,945,811单位代币仅兑换出0.000000000002393 ETH，兑换比例严重失衡。\n2. 多个流动性池（如0xceff5175...和0x9a138670...）的代币储备量在单笔交易内发生剧烈变动，WBTC池的reserve0从6,352,066,326骤减至6,352,066,326 - 344,084,748，而WETH池的reserve1同步异常波动。\n3. 交易接收方合约0xe11fc0b4...（疑似DEX路由合约）在单次交易中触发超过20次跨合约调用，涉及多个LP池的代币转移和销毁操作，Gas消耗（395,221）显著高于正常交易（平均约280,000）。\n\n二、漏洞原因分析\n1. 价格操纵漏洞：攻击者利用低流动性池（如0xf41e354e...）的储备不平衡，通过大额输入扭曲兑换比例。该池的WETH储备量（reserve1）极低（0x交易中显示为3,248,922,473,511单位，但实际对应ETH精度18位，仅约3.248 ETH），微小交易即可引发价格剧烈波动。\n2. 跨池套利路径设计缺陷：路由合约未对多级兑换路径中的滑点进行全局校验。攻击者通过WBTC→WETH→SUSHI路径，先在高流动性池（0xceff5175...）完成大额WBTC兑换WETH，随后在低流动性池（0xf41e354e...）利用扭曲价格完成WETH→SUSHI兑换，套取高额SUSHI。\n3. LP代币销毁异常：故障交易中，地址0x9a138670...向零地址转出604,800,790单位的SLP代币（价值约3.44 WBTC），但未同步验证流动性移除比例，可能因整数溢出或精度计算错误导致超额销毁。\n\n三、攻击路径还原\n1. 闪电贷借入WBTC：攻击者从WBTC池（0x9a138670...）借出344,084,748 WBTC（3.44 WBTC），触发LP代币销毁。\n2. 一级兑换（WBTC→WETH）：通过高流动性池0xceff5175...将WBTC兑换为8.345 WETH，利用大额交易暂时推高WETH价格。\n3. 二级兑换（WETH→SUSHI）：在低流动性池0x795065dc...以扭曲价格将WETH兑换为2,355,789 SUSHI，因该池储备比例失衡（WETH极少），微小输入即可获取超额SUSHI。\n4. 利润转移：最终将2,355,789 SUSHI转入地址0x8798249c...（疑似收益聚合器），完成套利。\n\n四、trace调用链（故障交易）\n调用链主体路径：\n0x51841d9afe10fe55571bdb8f4af1060415003528 → 0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50 → 0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac（Factory合约） → 0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3（WBTC-WETH池） → 0xceff51756c56ceffca006cd410b03ffc46dd3a58（WETH关联池） → 0xf41e354eb138b328d56957b36b7f814826708724（异常低流动性池） → 0x795065dcc9f64b5614c407a6efdc400da6221fb0（SUSHI池） → 0x8798249c2e607446efb7ad49ec89dd1865ff4272（收益地址）。\n\n完整合约地址调用序列：\n0x51841d9afe10fe55571bdb8f4af1060415003528\n0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50\n0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac\n0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3\n0x2260fac5e5542a773aa44fbcfedf7c193bc2c599\n0x798d1be841a82a273720ce31c822c61a67a601c3\n0xceff51756c56ceffca006cd410b03ffc46dd3a58\n0xf41e354eb138b328d56957b36b7f814826708724\n0x795065dcc9f64b5614c407a6efdc400da6221fb0\n0x6b3595068778dd592e39a122f4f5a5cf09c90fe2\n0x8798249c2e607446efb7ad49ec89dd1865ff4272"
    final_contracts = ['SushiSwap-UniswapV2Pair.sol', 'SushiSwap-UniswapV2Router02.sol', 'SushiSwap-IUniswapV2Router02.sol', 'SushiSwap-IUniswapV2Pair.sol', 'SushiSwap-UniswapV2Library.sol', 'SushiSwap-SushiMaker.sol', 'SushiSwap-MasterChef.sol', 'SushiSwap-SushiToken.sol', 'SushiSwap-TransferHelper.sol', 'SushiSwap-SafeMath.sol', 'SushiSwap-IUniswapV2Factory.sol', 'SushiSwap-Ownable.sol', 'SushiSwap-Context.sol', 'SushiSwap-ERC20.sol', 'SushiSwap-IERC20.sol', 'SushiSwap-SafeERC20.sol', 'SushiSwap-Math.sol']
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
