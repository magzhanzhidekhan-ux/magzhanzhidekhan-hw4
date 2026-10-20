import strategies as S
from tools import TOOLS
msgs = [{"role": "user", "content": "Say OK."}]
a = S.chat(messages=msgs, tools=TOOLS).usage.prompt_tokens
b = S.chat(messages=msgs).usage.prompt_tokens
print("with tools:", a, "without:", b, "difference:", a - b)