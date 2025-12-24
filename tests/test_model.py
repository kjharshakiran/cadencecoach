
import os
import asyncio
# from google.adk.models import Model
from spartan_phalanx.config import get_model
from dotenv import load_dotenv

load_dotenv()

async def test_model():
    model_name = get_model()
    print(f"Testing model: {model_name}")
    
    try:
        # Initialize model directly to test
        # Note: The ADK Agent class handles model initialization, but we can try to use the underlying library if possible.
        # However, ADK abstracts it. Let's try to create a simple Agent and run it.
        from google.adk.agents import Agent
        
        agent = Agent(
            name="test_agent",
            model=model_name,
            instruction="You are a test agent."
        )
        
        # We need a runner to run the agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        
        session_service = InMemorySessionService()
        session_service.create_session(app_name="test_app", user_id="test_user", session_id="test_session")
        
        runner = Runner(
            agent=agent,
            session_service=session_service,
            app_name="test_app"
        )
        
        from google.genai import types
        content = types.Content(role="user", parts=[types.Part(text="Hello, are you working?")])
        
        print("Sending message...")
        async for event in runner.run_async(
            user_id="test_user",
            session_id="test_session",
            new_message=content
        ):
            if event.is_final_response():
                print(f"Response: {event.content.parts[0].text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_model())
