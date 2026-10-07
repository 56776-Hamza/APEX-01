import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers.utils import get_json_schema

# Load tokenizer and model
model_id = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
print(f"Loading {model_id}...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
    device_map="auto"
)

def multiply(a: float, b: float):
    """
    A function that multiplies two numbers

    Args:
        a: The first number to multiply
        b: The second number to multiply
    """
    return a * b

messages = [
    {"role": "user", "content": "what is 2.0909090923 x 0.897987987"},
]

print("Applying chat template with tools...")
tokenized_chat = tokenizer.apply_chat_template(
    messages,
    tools=[multiply],
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt"
).to(model.device)

print("Generating response...")
with torch.no_grad():
    outputs = model.generate(
        tokenized_chat,
        max_new_tokens=1024,
        temperature=1.0,
        top_p=1.0,
        eos_token_id=tokenizer.eos_token_id
    )

print("\n--- Output ---")
print(tokenizer.decode(outputs[0]))
