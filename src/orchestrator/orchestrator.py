import os
import sys
from pathlib import Path

# ==========================================
# 1. SETUP & PATH RESOLUTION
# ==========================================
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parents[1]  # climbs to project root

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from src.tools.agent_tools import query_telemetry_db, fetch_corridor_conditions, search_compliance_sop
from langchain_openai import ChatOpenAI
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_ollama import ChatOllama
except ImportError:
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        from langchain_community.llms import Ollama as ChatOllama

# ==========================================
# 2. STATE STRUCTURE
# ==========================================

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]



# ==========================================
# 2. FACTORY INITIALIZATION: AGENT REASONER LLM
# ==========================================

AGENT_LLM_SETTING = os.getenv("AGENT_LLM_SETTING", "OLLAMA").strip().upper()

if AGENT_LLM_SETTING == "OPENAI":
    print("🤖 Brain Mode: Utilizing Cloud OpenAI Reasoner (gpt-4o)...")
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

elif AGENT_LLM_SETTING == "DEEPSEEK":
    print("🐳 Brain Mode: Utilizing Flagship DeepSeek Cloud Reasoner (deepseek-v4-pro)...")    
    # Fully updated to match 2026 DeepSeek API parameters and endpoint contracts
    llm = ChatOpenAI(
        model="deepseek-v4-flash",                          # deepseek-v4-flash, deepseek-v4-pro
        temperature=0,
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",                # Fixed connection string url endpoint
        max_tokens=2048,                                    # Gives the deep reasoner plenty of output runway
        # extra_body={
        #     "thinking": {"type": "enabled"},              # Activates DeepSeek Deep-Thinking mode
        #     "reasoning_effort": "high"                    # Drives maximal reasoning depth for logic maps
        # }
    )

elif AGENT_LLM_SETTING == "GROQ":
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    print(f"⚡ Brain Mode: Utilizing Ultra-Fast Groq Cloud Reasoner ({groq_model})...")
    if ChatGroq is None:
        from langchain_groq import ChatGroq
    llm = ChatGroq(
        model=groq_model,
        temperature=0,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )

else:  # FALLBACK / DEFAULT RUNNER MODE
    print("🤗 Brain Mode: Local Fallback Activated. Binding Local Ollama (qwen2.5:7b)...")
    llm = ChatOllama(model="qwen2.5:7b", temperature=0, num_predict=1024)

fde_tools = [query_telemetry_db, fetch_corridor_conditions, search_compliance_sop]
llm_with_tools = llm.bind_tools(fde_tools)

# ==========================================
# 3. STATE ROUTING & CONDITIONAL EDGES
# ==========================================

def reasoning_node(state: AgentState):
    """
    The main agent reasoning node.
    Calls the LLM with the current messages and returns the response.
    """
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

graph_builder = StateGraph(AgentState)

graph_builder.add_node("reasoner", reasoning_node)
# 1. Add tools
graph_builder.add_node("tools", ToolNode(fde_tools))
graph_builder.add_edge(START, "reasoner")
graph_builder.add_conditional_edges("reasoner", tools_condition)
graph_builder.add_edge("tools", "reasoner")

checkpointer = MemorySaver()
workflow = graph_builder.compile(checkpointer=checkpointer)

