import asyncio
import litellm
from pprint import pprint

async def debug_usage():
    response = await litellm.acompletion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Say hello"}]
    )
    
    print("Full response:")
    pprint(vars(response))
    
    print("\n\nUsage object:")
    pprint(vars(response.usage))
    
    print("\n\nUsage type:")
    print(type(response.usage))
    print(response.usage.__class__.__name__)

if __name__ == "__main__":
    asyncio.run(debug_usage())