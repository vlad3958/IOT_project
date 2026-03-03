from app.entities.agent_data import AgentData
from app.entities.processed_agent_data import ProcessedAgentData


def process_agent_data(
    agent_data: AgentData,
) -> ProcessedAgentData:
    """
    Process agent data and classify the state of the road surface.
    Parameters:
        agent_data (AgentData): Agent data that contains accelerometer, GPS, and timestamp.
    Returns:
        processed_data (ProcessedAgentData): Processed data containing the classified
        state of the road surface and agent data.
    """
    z = agent_data.accelerometer.z
    y = agent_data.accelerometer.y

    if abs(y) > 300 or z < 16000:
        road_state = "pothole"
    elif abs(y) > 150 or z < 16400:
        road_state = "bumpy"
    else:
        road_state = "smooth"

    return ProcessedAgentData(
        road_state=road_state,
        agent_data=agent_data,
    )
