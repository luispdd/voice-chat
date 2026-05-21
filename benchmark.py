import time
from openai import OpenAI

# Initialize client to point directly to your stable LM Studio local server
client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"  # LM Studio does not require a real key, but a placeholder string must be present
)

def measure_tokens_per_second(prompt: str, model_name: str) -> None:
    print(f"Sending prompt to {model_name}...")
    print("-" * 40)
    
    # Track when the generation actually begins
    start_time = time.time()
    token_count = 0
    
    # Request a streaming response to capture chunks as they leave LM Studio
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    
    # Iterate through chunks and print text in real-time
    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            token_count += 1  # Increments with each incoming text fragment
            
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Calculate final generation metrics
    tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
    
    print("\n" + "-" * 40)
    print(f"Benchmark Results:")
    print(f"  - Total Generated Tokens: {token_count}")
    print(f"  - Total Time Elapsed:     {elapsed_time:.2f} seconds")
    print(f"  - Eval Rate Speed:        {tokens_per_second:.2f} tokens/s")
    print("-" * 40)

if __name__ == "__main__":
    # The exact same test prompt used during your previous Ollama tests
    test_prompt = "Write a poem about the sea."
    model_identifier = "qwen2.5-3b-instruct"
    
    measure_tokens_per_second(test_prompt, model_identifier)
