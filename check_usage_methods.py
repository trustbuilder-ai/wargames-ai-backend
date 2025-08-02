import asyncio
import litellm

async def check_usage():
    response = await litellm.acompletion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Say hi"}]
    )
    
    usage = response.usage
    print(f"Usage type: {type(usage)}")
    print(f"Has model_dump: {hasattr(usage, 'model_dump')}")
    print(f"Usage methods: {[m for m in dir(usage) if not m.startswith('_')]}")
    
    if hasattr(usage, 'model_dump'):
        print("\nmodel_dump output:")
        print(usage.model_dump())
        print("\nmodel_dump with include:")
        print(usage.model_dump(include={"prompt_tokens", "completion_tokens", "total_tokens"}))

asyncio.run(check_usage())