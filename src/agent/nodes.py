from typing import Dict, Any
from src.agent.state import AgentState
from src.agent.prompts import get_system_prompt
from src.agent.tools import schedule_retry, trigger_fallback, ToolException

def parse_consent(message: str) -> bool:
    """Very basic deterministic consent parser for the MVP simulation."""
    msg = message.lower().strip()
    positive = ["yes", "sure", "do it", "schedule it", "okay"]
    negative = ["no", "don't", "not now", "cancel it"]
    
    if any(p in msg for p in positive):
        return True
    if any(n in msg for n in negative):
        return False
    return False # Default to false for ambiguity

def llm_chat_node(state: AgentState, llm) -> AgentState:
    """
    Simulates the LLM chat node. In production, this would invoke an LLM.
    For the test harness, we pass a mocked LLM that acts deterministically based on the state.
    """
    
    # 1. Update consent based on the last message (simulating the customer's response)
    if state["messages"]:
        last_message = state["messages"][-1]
        if last_message.startswith("Customer:"):
            state["consent_granted"] = parse_consent(last_message)
    
    # 2. Call the LLM to get the next action or message
    system_prompt = get_system_prompt(state["decision_context"])
    
    # We pass the state to the LLM (or mock LLM)
    response = llm.invoke(state)
    
    # 3. Process LLM response
    if "tool_calls" in response:
        # The LLM decided to call a tool
        try:
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                kwargs = tool_call["args"]
                
                if tool_name == "schedule_retry":
                    dec_ctx = dict(vars(state["decision_context"])) if hasattr(state["decision_context"], '__dict__') else dict(state["decision_context"])
                    if "customer_id" not in dec_ctx or not dec_ctx["customer_id"]:
                        dec_ctx["customer_id"] = state.get("customer_id")
                    result = schedule_retry.invoke({
                        "attempt_id": state["attempt_id"],
                        "agreed_date": kwargs.get("agreed_date"),
                        "consent_granted": state["consent_granted"],
                        "decision_context": dec_ctx
                    })
                    state["action_status"] = "COMPLETED"
                    state["messages"].append(f"Tool {tool_name} success: {result}")
                    
                elif tool_name == "trigger_fallback":
                    result = trigger_fallback.invoke({
                        "attempt_id": state["attempt_id"],
                        "fallback_type": kwargs.get("fallback_type"),
                        "decision_context": vars(state["decision_context"]) if hasattr(state["decision_context"], '__dict__') else state["decision_context"]
                    })
                    state["action_status"] = "COMPLETED"
                    state["fallback_reason"] = kwargs.get("fallback_type")
                    state["messages"].append(f"Tool {tool_name} success: {result}")
        except ToolException as e:
            # Catch the boundary violation!
            state["action_status"] = "FAILED"
            state["messages"].append(f"Tool execution rejected: {str(e)}")
    else:
        # The LLM generated a text message
        state["messages"].append(f"Agent: {response['content']}")
        
    return state
