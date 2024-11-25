# Dynamic-Behavior-Tree

# Pipeline for Human-Robot Collaboration in Industry 5.0

This repository presents an innovative pipeline for planning and controlling collaborative tasks between humans and robots in an industrial setting. This work is based on the thesis **"Multi-objective Optimization of Human-Robot Collaboration Based on Artificial Intelligence: Application to the Aerospace Industry"**, defended by Pierre Hémono.

## Table of Contents
- [Context](#context)
- [Objectives](#objectives)
- [Pipeline Architecture](#pipeline-architecture)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [References](#references)

---

## Context

Industry 5.0 places humans at the center of industrial processes while integrating advanced technologies for seamless collaboration with robots. This approach combines:
- **Scheduling based on multi-objective optimization**: Considering fatigue, ergonomics, and individual preferences.
- **Control based on Behavior Trees**: Ensuring responsiveness and adaptability during task execution.

---

## Objectives

1. Incorporate human factors into the planning and execution of tasks.
2. Optimize human-robot interactions to ensure an ergonomic and productive work environment.
3. Provide a robust pipeline combining:
   - **Macro scheduling** (task planning)
   - **Micro control** (task execution via Behavior Trees)

---

## Pipeline Architecture

The pipeline is divided into three main modules:

1. **Converter (P1)**:
   - Analyzes input data and constraints.
   - Generates PDDL knowledge bases.

2. **Dispatcher (P2)**:
   - Creates the problem instance.
   - Solves it using a PDDL planner to generate a plan.

3. **Assembler (P3)**:
   - Translates the plan into an executable Behavior Tree.
   - Manages real-time deviations using ROSPlan.

![Pipeline](Pipeline.pdf)

---

## Technologies Used

### Programming Languages
- **Python**: Core scripts are written in Python, compatible with versions 2.7 and 3.8+.

### Planning
- **PDDL**: Planning Domain Definition Language, a standard for automated planning.
- **POPF3**: A forward-chaining partial-order planner for PDDL, used for temporal planning.  
  Repository: [https://github.com/popflogic/popftemp](https://github.com/popflogic/popftemp)  
  Paper: **Coles et al.**, "Hybrid Temporal Planning: Reaching Into the Middle Ground," IJCAI 2009.

### Control Frameworks
- **py-trees**: A Python library for constructing and running Behavior Trees, developed by Daniel Stonier.  
  Repository: [https://github.com/splintered-reality/py_trees](https://github.com/splintered-reality/py_trees)  
  Documentation: [https://py-trees.readthedocs.io](https://py-trees.readthedocs.io)

### Robotics Middleware
- **ROS** (Robot Operating System): Provides the middleware for robot control and interaction.  
  Version used: **ROS Melodic**  
  Website: [https://www.ros.org/](https://www.ros.org/)

- **ROSPlan**: A framework for robot planning in ROS, developed by the University of Edinburgh.  
  Repository: [https://github.com/KCL-Planning/ROSPlan](https://github.com/KCL-Planning/ROSPlan)  
  Paper: **Michael Cashmore et al.**, "ROSPlan: Planning in the Robot Operating System," ICAPS 2015.

### Motion Planning
- **MoveIt**: A motion planning framework for ROS, used for robot arm manipulation.  
  Website: [https://moveit.ros.org/](https://moveit.ros.org/)

### Optimization
- **Gurobi**: Used for solving multi-objective scheduling problems.  
  Website: [https://www.gurobi.com/](https://www.gurobi.com/)

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/PierreHemono/Dynamic-Behavior-Tree.git
   cd Dynamic-Behavior-Tree
