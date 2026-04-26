# Gait Health
Leveraging portable, low-cost gait sensing to monitor health

## What is the project about?
This project explores the use of human gait patterns as an unobstrusive indicator of health status. To narrow down the scope of this project, we will target Parkinson's disease specifically. By leveraging IMU sensors, we aim to capture motion data during walking and analyze it to detect symptoms of Parkinson's. Gait is a rich biometric signal that reflects neurological, muscular, and skeletal health, making it a powerful yet underutilized tool for continuous health monitoring.

## Why is this project exciting for you and your group?

This project excites us because of its potential to scale and impact everyday life. Health is universal; everyone, regardless of age or background, must continuously monitor and maintain their well-being.

One of the most persistent challenges in healthcare is cost and accessibility. Traditional health monitoring often depends on costly clinical appointments, frequent hospital visits, or subjective self-reporting, all of which can create barriers for many populations. These barriers are especially detrimental for the elderly population, people living in rural areas, and communities with limited access to healthcare infrastructure. As a result, many health conditions go undetected until they become severe.

By using low-cost, portable IMU sensors to monitor gait, this project offers an accessible alternative to traditional healthcare monitoring systems. Gait data can be collected continuously and unobtrusively, enabling early detection of changes in physical or neurological health without requiring specialized facilities. This approach aligns with our shared interest in creating technology that is practical, affordable, and meaningful in real-world settings.


Research the state-of-the-art algorithms for detecting two Parkinson's disease gait symptoms using a single ankle/shoe-mounted IMU (MPU-6050 at 100 Hz):

1. **Freezing of Gait (FoG)** — sudden inability to initiate or continue walking; characteristic signal: high-frequency trembling (3–8 Hz) with no forward progression
2. **Gait Shuffling** — reduced step height and shortened stride; characteristic signal: reduced vertical acceleration peaks, shorter cadence intervals

Focus on:
- The Freeze Index (FI) = power(3–8 Hz) / power(0.5–3 Hz) on the vertical axis — a ratio > threshold indicates FoG
- Step detection heuristics (peak detection on vertical accel) for shuffle detection
- Computationally cheap approaches suitable for a microcontroller (no heavy ML)
- Sliding window sizes typically used (0.5–2 second windows are common)
- Typical threshold values from literature

Do NOT write code — just summarize the algorithmic approach, parameters, and thresholds used in published work. Use web search if needed.
