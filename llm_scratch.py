from backend.llm.client import LLMClient
from backend.llm.agent import LLMAgent
from backend.models.llm import ChatRequest, ChatMessage, ChatResponse

import asyncio


async def run_client():
    client: LLMClient = LLMClient()
    chat_request: ChatRequest = ChatRequest(
       model="gpt-4o",
       messages = [
            ChatMessage(
                role = "user",
                content = "How are you?"
            ),
       ]
    )
    chat_response: ChatResponse = await client.chat_completion(chat_request)
    print(chat_response)


async def run_agent():
    client: LLMClient = LLMClient()
    agent: LLMAgent = LLMAgent(client, )



if __name__ == "__main__":
    asyncio.run(main())
