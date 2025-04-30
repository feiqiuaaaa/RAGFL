import os
from openai import OpenAI
from string import Template


def load_prompt(file_path: str, variables: dict = None) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"路径不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        template = Template(f.read())
        return template.substitute(variables or {})


def get_summary_from_llm(system_prompt: str, user_prompt: str, call_type=0) -> []:
    client = OpenAI(api_key="sk-3b88436dd2044fc6a9d3fdccb779b1c6", base_url="https://api.deepseek.com")
    # client = OpenAI(api_key="f774bfb4-c2a8-45db-978d-c3bbbf5c6e19", base_url="https://ark.cn-beijing.volces.com/api/v3")

    response = None
    if call_type == 0:  # r1
        response = call_deepseek_reasoner(client, system_prompt, user_prompt)
    elif call_type == 1:  # v3
        response = call_deepseek_chat(client, system_prompt, user_prompt)
    elif call_type == 2:  # format
        response = call_format_llm(client, system_prompt, user_prompt)

    if response is None:
        return None
    choice = response.choices[0]
    finish_reason = choice.finish_reason.strip()
    if finish_reason != 'stop':
        return [finish_reason, ""]
    return [finish_reason, choice.message.content]


def call_deepseek_reasoner(client, f_system_prompt, f_user_prompt):
    return client.chat.completions.create(
        # "doubao-1-5-pro-32k-250115"
        # "deepseek-chat"
        model="deepseek-reasoner",
        messages=[
            {"role": "system", "content": f_system_prompt},
            {"role": "user", "content": f_user_prompt},
        ],
        stream=False
    )


def call_deepseek_chat(client, f_system_prompt, f_user_prompt):
    return client.chat.completions.create(
        # "doubao-1-5-pro-32k-250115"
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f_system_prompt},
            {"role": "user", "content": f_user_prompt},
        ],
        stream=False
    )


def call_format_llm(client, f_system_prompt, f_user_prompt):
    return client.chat.completions.create(
        # "doubao-1-5-pro-32k-250115"
        # "deepseek-chat"
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f_system_prompt},
            {"role": "user", "content": f_user_prompt},
        ],
        response_format={
            'type': 'json_object'
        }
    )


if __name__ == '__main__':
    system_prompt = load_prompt("prompt/location_trace_chain_system_prompt")
    user_prompt = load_prompt("prompt/location_trace_chain_user_prompt_test")
    chain_summary = get_summary_from_llm(system_prompt, user_prompt)
    if chain_summary[0] != 'stop':
        print(' error! message:' + chain_summary[0])
    chain_summary = chain_summary[1]
    print(chain_summary)
