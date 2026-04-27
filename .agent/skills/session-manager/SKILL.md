---
name: session-manager
description: Aligns the agent with the project roadmap and enforces work-log integrity before concluding a session.
---

# Goal
Manage the lifecycle of a trading research session, ensuring the agent is synchronized with Ibby's roadmap and that all work is documented according to the Project Constitution.

# Instructions
1. **Session Initialization**:
    - Read the project "Constitution" at `/.agent/rules/AGENT.md`.
    - Read the most recent work log in `outputs/work-log/` to understand the current state.
    - Cross-reference the "Next session starts from" section with the objectives in `docs/roadmap/sessions-23-50.md`.
2. **Implementation Planning**:
    - Propose a specific scope for the current session based on the Roadmap Tracks (e.g., Track D for Circuit Breakers).
    - Present the plan to Ibby and wait for a "GO" before modifying any files or running code.
3. **Session Conclusion (The Stop Hook)**:
    - Before stopping, verify that a new work log has been created in `outputs/work-log/` within the last 120 minutes.
    - If no log is found, the agent MUST generate one following the template in `AGENT.md` before the session is considered complete.

# Constraints
- **Audit Requirement**: The agent cannot declare a session "done" without a corresponding Work Log and a PR opened against the `develop` branch.
- **Persona Review**: Every session summary must include a brief sign-off from the **Architect**, **Scientist**, and **Mentor**.
- **No Silent Exit**: If the agent detects it is running out of context or time, it must trigger the work-log creation immediately.

# Examples
- **User**: "Start session 25."
- **Agent**: (Reads roadmap and logs) -> "Last session finished the Instrument registry. Session 25 starts the Daily Loss Limit logic in Track D. Architect and Scientist are ready. Proceed?".