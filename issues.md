# Project Issues

## P1-High Priority

1. ### Specific Assignment Rules (#33)
**Category:** `Task Assignment and Scheduling Logic`

**Sub-tasks:**
- In REP tasks modal -> Force specific technicians to work on designated tasks. It would be nice if I select a technician or technicians, then appear next to the technician a checkbox if I want to force him to work on that task, taking priority over other tasks.
- If, for PM tasks (backend), fewer technicians can work on a task than the expected (from planning), I think while assigning PM and REP tasks to technicians and generating dashboard, give option to go to technician mappings to rearrange mappings so that more technicians are available for that task and then return; or, if not possible to add more technicians, proceed as normal.
- Allow assignment of unskilled technicians with skilled ones, ensuring compatibility with general skills. This is an extreme situation, so only apply to A priority tasks. This is to make sure that in the A priority tasks we always have the right amount of technicians so the task can be completed as planned.
- Prioritise certain task types (e.g., repair tasks) over others for specific technician groups (e.g., PLC technicians). For example, PLC technicians will work first on REP tasks and later, if they have time, will continue on PM tasks (situation where REP task and PM task are A priority and this PLC technician is assigned to the REP task because it is a PLC task and has the skills to work on the PM task).
- Implement a "help" concept where idle technicians can assist others on full-shift tasks after completing their own.
     - Help concept:
		- Task A is assigned to technician A -> Full shift
		- Technician B has task c -> finish at 25% of the shift -> doesn't do anything else
		- Technician B could help technician A -> How could we implement this?

2. ### Database integration with external APIs (#29)
**Category:** `Database and Data Management`

**Sub-tasks:**
- Ensure the database can support integration with external tools or APIs for future use.
- Create a table for "lines" in the database and link it to the technician table using relevant identifiers (e.g., satellite points).

3. ### Extract data from Excel files (#28)
**Category:** `Database and Data Management`

**Sub-tasks:**
- When adding a new task from Excel, ensure the ability to define required technologies/skills before assignment to avoid tasks appearing as "has no required technology defined."
- Add an option to import task names from an Excel file, compare with the current database, show differences, and allow actions like add (if new), edit, or delete (if not in the new list but exists in the database).
- Integrate "Planning Notes" column data from Excel into the dashboard table by combining it with another relevant column (e.g., lines) into a single column.
- Update the total task list by extracting data from an external system as an Excel file, comparing it with database data, and adding new tasks or removing deleted ones (including updating assignments and reordering priorities).

4. ### Flexible Scheduling (#16)
**Category:** `Task Assignment and Scheduling Logic`

**Sub-tasks:**
- Add options to include tasks from previous shifts (unfinished), weekend plans, or additional tasks dynamically.
- Enable rescheduling or adaptation to changes during planned timeframes.
- Allow adjustable breaks for technicians and evaluate impacts on task interactions.
- Update task duration dynamically using average values from external data sources and refine with an appropriate algorithm.

5. ### Optimization Improvements (#15)
**Category:** `Task Assignment and Scheduling Logic`

**Sub-tasks:**
- Explore faster approaches for non-permutation assignments:
- Enhance heuristics for greedy assignment (e.g., dynamic sorting criteria or task selection rules).
- Implement local search techniques to refine initial schedules by swapping or moving tasks for better scores.
- Consider advanced metaheuristics like Simulated Annealing or Genetic Algorithms for complex scenarios.
- Model the problem using Constraint Programming (CP) or Integer Linear Programming (ILP) solvers for optimal solutions.
- During permutation-based optimization, display a progress bar or processing indicator in the UI.
- Optimize performance by limiting group size or combinations for large teams during technician grouping.

6. ### Core Assignment Logic (#14)
**Category:** `Task Assignment and Scheduling Logic`

**Sub-tasks:**
- Document the task assignment process in a manual or explanation:
- Permutation-based optimization for high-priority tasks (limited to a small number due to computational load).
- Assign tasks to groups with technician count closest to planned numbers.
- Prioritize groups with the lowest average priority level and workload.
- Place tasks in the first available spot from the shift start where all group members are available.
- Prioritize fully scheduled tasks over partially scheduled ones.

7. ### Flexible Scheduling (#13)
**Category:** `Generalization and Standardization`

8. ### Generic Skill Management (#12)
**Category:** `Generalization and Standardization`

9. ### Internationalization (i18n) (#11)
**Category:** `Generalization and Standardization`

10. ### Theme and Branding (#10)
**Category:** `Generalization and Standardization`

11. ### Pluggable Data Sources (#9)
**Category:** `Generalization and Standardization`

12. ### Customizable Workflows (#8)
**Category:** `Generalization and Standardization`

13. ### Modular Architecture (#7)
**Category:** `Generalization and Standardization`

14. ### Configurable Terminology (#6)
**Category:** `Generalization and Standardization`

## P2-Medium Priority

15. ### Manage Task-Technology Mappings (#34)
**Category:** `Task and Technician Mapping Features`

**Sub-tasks:**
- Ensure task names are unique to prevent duplicates when adding tasks (investigate why duplicates are added).
- Rename sections like "Manage Technologies & Groups" with a clearer convention (e.g., Group > Subcategory > Skills).
- Test core logic for task assignment functionalities.
- Allow users to input a task name and view capable technicians.
- Assign varying importance to skills for a task.
- Create a graphical map of all mappings (technician-skills-tasks) with statistics to identify skill gaps.

16. ### Additional UI Features (#31)
**Category:** `User Interface and Dashboard Enhancements`

**Sub-tasks:**
- In task management pages, remove placeholder text (e.g., "New Task") when the input field is clicked.
- Fix visual update issues in input fields for priority display (currently shows old value until saved).
- Add an option in the main page to toggle non-production hours (e.g., 8h or 12h) for specific scenarios like shutdowns, with defaults for certain days and editable week numbers.
- Adapt the UI to look good at 100% browser zoom.

17. ### Gantt Chart Enhancements (#30)
**Category:** `User Interface and Dashboard Enhancements`

**Sub-tasks:**
- Remove specific duration labels (e.g., "434 min of work") and display only the Gantt Chart.
- Simplify time slots in the header to show just the time, positioned above grid lines for a clock-like effect.
- Reduce time slot granularity from 15 minutes to 5 minutes, with vertical grid lines marking every 15 minutes.
- Add a live red line indicating the current time (currently only updates on refresh and has issues with late shifts or day changes).
- Adjust the Gantt window to align with team schedules.
- Implement alternative or additional scrolling mechanisms (similar to map applications).
- Improve messaging or annotations for task instances within the Gantt Chart.
- Enable clicking on a task in the Gantt Chart to auto-scroll to the corresponding table row, blink the row for 3 seconds (considering filters), and explore reverse functionality.

18. ### Technician and Skill Management (#17)
**Category:** `Task and Technician Mapping Features`

**Sub-tasks:**
- Integrate training information for technicians into the database.
- Check spare parts availability before task assignment, especially for planned tasks with delivery schedules.
- Explore integration with a skills matrix or training system through APIs to manage competencies.

19. ### Additional Tasks Modal (#5)
**Category:** `User Interface and Dashboard Enhancements`

**Sub-tasks:**
- Add the option to select priority (A, B, C, ...).

20. ### Task Interaction Features (#4)
**Category:** `User Interface and Dashboard Enhancements`

**Sub-tasks:**
- Allow technicians to mark completed tasks (e.g., in green) and filter the Gantt Chart by specific technicians or tasks.
- Provide navigation arrows in task modals to switch between different tasks.
- Display notes or line information in relevant task modals.

## P3-Low Priority

21. ### Implementation (#27)
**Category:** `Testing and Data Seeding`

22. ### Proposal (#26)
**Category:** `Testing and Data Seeding`

23. ### Create a Dummy Data Seeding Mechanism (#25)
**Category:** `Testing and Data Seeding`

24. ### Innovative Concepts (#24)
**Category:** `Additional Features and Ideas`

**Sub-tasks:**
- Explore data matrix implementation or self-assessment forms for initial data population.

25. ### Multilingual Support (#23)
**Category:** `Additional Features and Ideas`

**Sub-tasks:**
- Consider adding translations (e.g., to German).

26. ### Deployment and Hosting (#22)
**Category:** `Reporting and Miscellaneous`

**Sub-tasks:**
- Request IT to host the application on a server with a dedicated domain for wider access.
- Explore hosting solutions for automated notifications (e.g., email or team messages) when new dashboards are generated.
- Remove hardcoded date calculations and unnecessary debugging code before production release.

27. ### User Documentation (#21)
**Category:** `Reporting and Miscellaneous`

**Sub-tasks:**
- Write a detailed manual explaining how the application works.

28. ### Report Generation (#20)
**Category:** `Reporting and Miscellaneous`

**Sub-tasks:**
- Save reports in a specific folder with a consistent naming pattern, especially for multiple reports created on the same day.
- Create detailed versions of dashboards or reports for specific roles with additional data extraction and historical Gantt views.

29. ### Task Data Updates (#19)
**Category:** `External System Integration`

**Sub-tasks:**
- Automate retrieval and comparison of task data from external sources to update the database or dashboards.

30. ### General API Integration (#18)
**Category:** `External System Integration`

**Sub-tasks:**
- Build options to link the application with external systems for data exchange (e.g., asset maintenance or management endpoints).
- Follow best practices for API usage like testing in non-production environments, securing credentials, and refreshing tokens.
