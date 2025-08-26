#### Database and Data Management
- **Remove task priorities** from the database (specifically from the table related to task assignments, column for priority). -> Do not mix it up with task priority (A, B, C...) which is still needed.
- **Extract data from Excel files**:
  - When adding a new task from Excel, ensure the ability to define required technologies/skills before assignment to avoid tasks appearing as "has no required technology defined."
  - Add an option to import task names from an Excel file, compare with the current database, show differences, and allow actions like add (if new), edit, or delete (if not in the new list but exists in the database).
  - Integrate "Planning Notes" column data from Excel into the dashboard table by combining it with another relevant column (e.g., lines) into a single column.
  - Update the total task list by extracting data from an external system as an Excel file, comparing it with database data, and adding new tasks or removing deleted ones (including updating assignments and reordering priorities).
- **Database integration with external APIs**:
  - Ensure the database can support integration with external tools or APIs for future use.
  - Create a table for "lines" in the database and link it to the technician table using relevant identifiers (e.g., satellite points).
- **Live updates and synchronization** for real-time data consistency across the application.

#### User Interface and Dashboard Enhancements
- **Technician Dashboard Improvements**:
  - Freeze the table header when scrolling (disappear when moving to other sections like Gantt Chart).
  - Make the table a scrollable element with sticky main and section headers during scrolling within respective sections.
  - Add live layout updates to show which lines are busy or free with tasks.
- **Gantt Chart Enhancements**:
  - Remove specific duration labels (e.g., "434 min of work") and display only the Gantt Chart.
  - Simplify time slots in the header to show just the time, positioned above grid lines for a clock-like effect.
  - Reduce time slot granularity from 15 minutes to 5 minutes, with vertical grid lines marking every 15 minutes.
  - Add a live red line indicating the current time (currently only updates on refresh and has issues with late shifts or day changes).
  - Adjust the Gantt window to align with team schedules.
  - Implement alternative or additional scrolling mechanisms (similar to map applications).
  - Improve messaging or annotations for task instances within the Gantt Chart.
  - Enable clicking on a task in the Gantt Chart to auto-scroll to the corresponding table row, blink the row for 3 seconds (considering filters), and explore reverse functionality.
- **Task Interaction Features**:
  - Allow technicians to mark completed tasks (e.g., in green) and filter the Gantt Chart by specific technicians or tasks.
  - Provide navigation arrows in task modals to switch between different tasks.
  - Display notes or line information in relevant task modals.
- **Additional UI Features**:
  - In task management pages, remove placeholder text (e.g., "New Task") when the input field is clicked.
  - Fix visual update issues in input fields for priority display (currently shows old value until saved).
  - Add an option in the main page to toggle non-production hours (e.g., 8h or 12h) for specific scenarios like shutdowns, with defaults for certain days and editable week numbers.
  - Adapt the UI to look good at 100% browser zoom.
- **Additional Tasks Modal**:
  - Add the option to select priority (A, B, C, ...).

#### Task Assignment and Scheduling Logic
- **Core Assignment Logic**:
  - Document the task assignment process in a manual or explanation:
    - Permutation-based optimization for high-priority tasks (limited to a small number due to computational load).
    - Assign tasks to groups with technician count closest to planned numbers.
    - Prioritize groups with the lowest average priority level and workload.
    - Place tasks in the first available spot from the shift start where all group members are available.
    - Prioritize fully scheduled tasks over partially scheduled ones.
- **Error fixing in REP tasks modal**:
  - When an additional task is added, an error "No eligible technicians found for this task" is displayed. Investigate if this is properly connected to the skills mapping.
- **Optimization Improvements**:
  - Explore faster approaches for non-permutation assignments:
    - Enhance heuristics for greedy assignment (e.g., dynamic sorting criteria or task selection rules).
    - Implement local search techniques to refine initial schedules by swapping or moving tasks for better scores.
    - Consider advanced metaheuristics like Simulated Annealing or Genetic Algorithms for complex scenarios.
    - Model the problem using Constraint Programming (CP) or Integer Linear Programming (ILP) solvers for optimal solutions.
  - During permutation-based optimization, display a progress bar or processing indicator in the UI.
  - Optimize performance by limiting group size or combinations for large teams during technician grouping.
- **Specific Assignment Rules**:
  - Force specific technicians to work on designated tasks.
  - For tasks requiring fewer technicians than planned, provide an option to update technician mappings or proceed with database updates.
  - Allow assignment of unskilled technicians with skilled ones, ensuring compatibility with general skills.
  - Prioritize certain task types (e.g., repair tasks) over others for specific technician groups (e.g., PLC technicians).
  - Implement a "help" concept where idle technicians can assist others on full-shift tasks after completing their own.
  - Assign tickets or miscellaneous tasks to remaining available slots after primary scheduling.
- **Flexible Scheduling**:
  - Add options to include tasks from previous shifts (unfinished), weekend plans, or additional tasks dynamically.
  - Enable rescheduling or adaptation to changes during planned timeframes.
  - Allow adjustable breaks for technicians and evaluate impacts on task interactions.
  - Update task duration dynamically using average values from external data sources and refine with an appropriate algorithm.

#### Task and Technician Mapping Features
- **Manage Task-Technology Mappings**:
  - Ensure task names are unique to prevent duplicates when adding tasks (investigate why duplicates are added).
  - Rename sections like "Manage Technologies & Groups" with a clearer convention (e.g., Group > Subcategory > Skills).
  - Remove unnecessary buttons like "Save All."
  - Test core logic for task assignment functionalities.
  - Allow users to input a task name and view capable technicians.
  - Assign varying importance to skills for a task.
  - Create a graphical map of all mappings (technician-skills-tasks) with statistics to identify skill gaps.
- **Technician and Skill Management**:
  - Integrate training information for technicians into the database.
  - Check spare parts availability before task assignment, especially for planned tasks with delivery schedules.
  - Explore integration with a skills matrix or training system through APIs to manage competencies.

#### External System Integration
- **General API Integration**:
  - Build options to link the application with external systems for data exchange (e.g., asset maintenance or management endpoints).
  - Follow best practices for API usage like testing in non-production environments, securing credentials, and refreshing tokens.
- **Task Data Updates**:
  - Automate retrieval and comparison of task data from external sources to update the database or dashboards.

#### Reporting and Miscellaneous
- **Report Generation**:
  - Save reports in a specific folder with a consistent naming pattern, especially for multiple reports created on the same day.
  - Create detailed versions of dashboards or reports for specific roles with additional data extraction and historical Gantt views.
- **User Documentation**:
  - Write a detailed manual explaining how the application works.
- **Deployment and Hosting**:
  - Request IT to host the application on a server with a dedicated domain for wider access.
  - Explore hosting solutions for automated notifications (e.g., email or team messages) when new dashboards are generated.
  - Remove hardcoded date calculations and unnecessary debugging code before production release.

#### Additional Features and Ideas
- **Multilingual Support**:
  - Consider adding translations (e.g., to German).
- **Innovative Concepts**:
  - Explore data matrix implementation or self-assessment forms for initial data population.
