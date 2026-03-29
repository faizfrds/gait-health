# Walking Pattern Analysis System

```mermaid
graph TD
    A[User wears IMU on their shoe or ankle] --> B[Data acquired from sensors]
    
    subgraph Processing_Loop [Core System]
        B --> C[FFT performed to identify patterns]
        C --> D[Classify into different health conditions]
        D --> E{Pattern Check}
        
        E -->|Normal| F[Continue Monitoring]
        E -->|Unusual/Abnormal| G((ALARM))
    end

    %% The Cycle/Feedback Loops
    F -.->|Next Sample| B
    G -.->|Reset/Re-scan| B

    %% Styling
    style G fill:#f66,stroke:#333,stroke-width:4px
    style A fill:#bbf,stroke:#333
    style Processing_Loop fill:#f9f9f9,stroke-dasharray: 5 5
