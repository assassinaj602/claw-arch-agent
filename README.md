# ClawArchAgent: Architecture-Driven Code Agent

ClawArchAgent is a lightweight, autonomous code synthesis agent designed to translate architectural specifications (Requirements, Component Specifications, and 4+1 PlantUML diagrams) into runnable desktop applications with accompanying verification suites and deployment contracts.

The system is modeled after the agentic loops analyzed in `Windy3f3f3f3f/how-claude-code-works` and implemented in `ultraworkers/claw-code`, using DeepSeek (`deepseek-v4-pro` / `deepseek-chat`) via official API endpoints, with native support for TokenHarbor (`https://tokenharbor.ai/v1`) and OpenRouter gateway endpoints.

---

## ⚡ Quick Start

### 1. Launch the Desktop Code Agent GUI (Recommended)
```bash
python main.py
```
*Opens the standalone desktop interface to configure your API key, view the 13 extracted PlantUML diagrams, and run autonomous synthesis.*

### 2. Run Headless CLI (for Remote / SSH Servers)
```bash
python main.py --cli --api-key YOUR_DEEPSEEK_API_KEY
```

### 3. Launch the Synthesized "Space Fractions" Desktop Game
```bash
python run_game.py
```
*Launches the native Tkinter desktop game window (Canvas fraction visuals, state machine, streak bonuses, and SQLite high scores).*

### 4. Standalone Windows Executables (Zero Python Setup)
Pre-compiled standalone Windows executables with zero Python installation required:
* **`dist/ClawArchAgent.exe`**: Double-click to launch the Code Agent Desktop Application. Configure API key, input files, output directory, and execute code synthesis with live token & USD cost telemetry.
* **`dist/SpaceFractions.exe`**: Double-click to launch the Space Fractions Desktop Game directly with full Canvas visuals, sound effects, SQLite high score persistence, and admin question editor.

To compile both executables locally on Windows:
```bash
python build_exe.py
# Or double-click build_exe.bat
```

---

## 1. System Architecture & Mapping to Reference Implementations

```
                                  +---------------------------------+
                                  | Architectural Specifications    |
                                  | - Architecture_Documentation.md |
                                  | - Architecture_View.md          |
                                  +----------------+----------------+
                                                   |
                                                   v
                                  +---------------------------------+
                                  | preprocessor.py                 |
                                  | (Deterministic AST/IR Compiler) |
                                  +----------------+----------------+
                                                   |
                                                   v (architecture_ir.json)
+-------------------------------+ +---------------------------------+ +-------------------------------+
| Tkinter Desktop GUI /         | | query_engine.py                 | | client.py                     |
| Headless CLI Interface        | | - ReAct Dispatch Loop           | | - HTTPX Connection Pool       |
| - API Key & Model Select      | | - Parallel Tool Calls Batcher   | | - deepseek-v4-pro Auto-Route  |
| - Real-time Telemetry Queue   | | - ContextCompressor (L1-L3)     | | - Backoff & Alias Fallback    |
| - Standalone Process Launcher | | - Autonomous Verifier Gate      | |                               |
+---------------+---------------+ +----------------+----------------+ +---------------+---------------+
                |                                  |                                  |
                +----------------------------------+----------------------------------+
                                                   |
                                                   v
                                  +---------------------------------+
                                  | Target Application Workspace    |
                                  | "Space Fractions" Desktop App   |
                                  | - main.py (Tkinter Canvas UI)   |
                                  | - components/ (Game, Question)  |
                                  | - openapi.yaml, internal.proto  |
                                  | - sql/, k8s/, Dockerfile        |
                                  | - tests/test_space_fractions.py |
                                  +---------------------------------+
```

### 1.1 Architectural Pillars

| Component | Module | Reference Mechanism (`how-claude-code-works`) |
| :--- | :--- | :--- |
| **Deterministic Preflight** | `src/agent/preprocessor.py` | Extracts markdown tables and all 13 PlantUML diagram blocks across 11 views into a normalized JSON Intermediate Representation (`architecture_ir.json`), reducing initial context token footprint by 65%. |
| **Agent Dispatch Loop** | `src/agent/query_engine.py` | ReAct loop supporting parallel tool executions per assistant turn. Minimizes multi-turn round-trips when scaffolding components to keep total runs within 4-6 turns. |
| **Tool Sandbox & Read Policy** | `src/agent/tools.py` | Strictly enforces workspace path containment and the Pre-Edit Read Policy (Chapter 4): files must be inspected via `read_file` before `edit_file` can modify content. |
| **Context Compression** | `src/agent/context_compressor.py` | 3-stage compression (Level 1: tool output trimming; Level 2: deduplicating superseded IR reads; Level 3: folding completed turns into state snapshots while preserving atomic `assistant[tool_calls]` to `tool` message pairing). |
| **In-Process Verifier** | `src/agent/tools.py` | Validates AST syntax (`ast.parse`) and executes unit tests in-process via `unittest` when `pytest` is absent or running inside a frozen binary. |
| **Embedded Runtime Runner** | `src/main_gui.py` (`--run-target`) | Solves running the generated desktop application on Windows machines with zero Python preinstalled by using `ClawArchAgent.exe`'s own bundled Python/Tkinter runtime to spawn the generated game. |

---

## 2. Token Budget & Cost Economics

Evaluation runs are bounded by a strict `$1.00 USD` ceiling monitored in real time by `src/agent/token_ledger.py`.

DeepSeek official API token pricing applied:
* Input tokens: `$0.27` per 1,000,000 tokens
* Cached input tokens: `$0.07` per 1,000,000 tokens
* Output tokens: `$1.10` per 1,000,000 tokens

### Typical Synthesis Run Benchmark

| Turn | Action / Phase | Prompt Tokens | Output Tokens | Cached Tokens | Turn Cost (USD) | Cumulative Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Scaffolding contracts from IR | 4,210 | 128 | 0 | $0.0013 | $0.0013 |
| **2** | Generating domain components | 4,890 | 1,420 | 3,840 | $0.0021 | $0.0034 |
| **3** | Generating desktop UI (`main.py`) | 6,940 | 1,980 | 5,120 | $0.0029 | $0.0063 |
| **4** | Generating tests & Dockerfile | 8,420 | 850 | 7,100 | $0.0018 | $0.0081 |
| **5** | Verification pass & finish | 9,800 | 160 | 8,900 | $0.0010 | **$0.0091** |

Total run cost averages **$0.01 to $0.04 USD**, well below the $1.00 evaluation threshold.

---

## 3. Installation & Local Development

### Prerequisites
* Python 3.10+
* Tkinter system libraries (`python3-tk` on Debian/Ubuntu, `python3-tkinter` on Fedora)

### Setup
```bash
git clone https://github.com/assassinaj602/claw-arch-agent.git
cd claw-arch-agent
python -m pip install -r requirements.txt
```

### Running Unit Tests
```bash
python -m unittest discover tests -v
```

All 23 automated tests cover preprocessor parsing, token ledger accounting, pre-edit read guard, context compression invariants, in-process verification, and game component state machines.

---

## 4. Running the Desktop Application

### Option A: Launching Desktop GUI via Python
```bash
python main.py
```
*(Optionally set `export DEEPSEEK_API_KEY="your-api-key"` beforehand to pre-populate the key field).*

### Option B: Running Headless CLI (for SSH / Remote Environments)
```bash
python main.py --cli --api-key $DEEPSEEK_API_KEY
```

### Option C: Building and Running Standalone Windows Executable
To compile `ClawArchAgent.exe` locally on Windows:
```bash
python build_exe.py
# Executable is generated in dist/ClawArchAgent.exe
```

Alternatively, pre-compiled binaries are generated on every commit via GitHub Actions (`.github/workflows/build-windows-exe.yml`) on `windows-latest` and downloadable under GitHub Actions workflow artifacts.

---

## 5. Generated Target Application: Space Fractions

The synthesized target application located in `examples/space_fractions_desktop/` satisfies all specifications in `Architecture_Documentation.md` and `Architecture_View.md`:

1. **Introductory Movie Scene** (`Section A`): Animated Canvas starfield with spaceship coordinates briefing and skip option.
2. **Main Menu** (`UseCaseDiagram`): Navigation for `Play Game`, `View Score`, `View Help`, and `Update Questions (Admin)`.
3. **Interactive Gameplay** (`StateDiagram` & `SequenceDiagram1`):
   * Dynamic visual fraction graphics (proportional pie slices and fuel tank ratios).
   * State machine transitions (`Playing` <-> `Paused` -> `GameOver`).
   * Streak bonus multipliers.
4. **Mission Ending Scene**: Performance evaluation, mastery feedback, and persistence to `spacefractions.db` (`sql/game_ddl.sql`).
5. **Admin Operations** (`SequenceDiagram2`): Direct question pool additions with SQLite persistence (`sql/question_ddl.sql`).

To run the sample game directly:
```bash
cd examples/space_fractions_desktop
python main.py
```
Or run through the agent's bundled launcher:
```bash
python src/main_gui.py --run-target examples/space_fractions_desktop/main.py
```

