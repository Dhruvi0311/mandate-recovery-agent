from typing import Literal
from langgraph.graph import StateGraph, END, START
from src.agent.state import AgentState
from src.agent.nodes import llm_chat_node

def route_decision(state: AgentState) -> str:
    """
    Deterministically routes the graph based on the Decision Engine's output.
    This prevents the LLM from trying to schedule a retry if it was told DO_NOT_RETRY.
    """
    decision = state["decision_context"].decision
    
    if decision in ["DO_NOT_RETRY", "WAIT_FOR_BETTER_WINDOW", "REAUTHORIZE_MANDATE", "ALTERNATIVE_PAYMENT"]:
        return "explain_and_close"
    
    return "ask_consent"

def build_graph(llm):
    """
    Builds the LangGraph state machine.
    We pass the `llm` in so we can inject a mock during testing.
    """
    
    workflow = StateGraph(AgentState)
    
    # We wrap the node to inject the LLM
    def chat_node_wrapper(state):
        return llm_chat_node(state, llm)
        
    workflow.add_node("agent", chat_node_wrapper)
    
    # Define the conditional routing immediately at START
    workflow.add_conditional_edges(
        START,
        route_decision,
        {
            "explain_and_close": "agent",
            "ask_consent": "agent"
        }
    )
    
    # After the agent node runs, we end the graph.
    # In a full conversational loop, this would route back to the user or a tool execution node.
    # For MVP deterministic state validation, the agent either succeeds or fails safely.
    workflow.add_edge("agent", END)
    
    return workflow.compile()
