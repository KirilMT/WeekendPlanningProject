# TECHNICIAN DASHBOARD
## User Manual

***

## Table of Contents
1. [Introduction](#introduction)
2. [Main Dashboard Components](#main-dashboard-components)
   - [Task Table](#task-table)
   - [Gantt Chart](#gantt-chart)
   - [Connection Between Table and Gantt Chart](#connection-between-table-and-gantt-chart)
3. [Using the Dashboard](#using-the-dashboard)
   - [Filtering Options](#filtering-options)
   - [Hover and Interactive Features](#hover-and-interactive-features)
4. [System Integration](#system-integration)
5. [Support Information](#support-information)

***

## Introduction

The Technician Dashboard provides maintenance supervisors and technicians with an easy-to-use tool for managing maintenance tasks. The dashboard shows scheduling, assigns resources, and tracks tasks all in one place to help make work more efficient.

## Main Dashboard Components

### Task Table

The task table shows all maintenance information in a clear format with columns that include:

- Task ID and description
- Location information
- Priority level
- Start and end times
- Current status
- Assigned technicians
- Links to related documentation

Each row in the table represents a single task and has a unique index number that connects it to the Gantt chart.

### Gantt Chart

The Gantt chart shows when tasks are scheduled on a timeline:

- Each task appears as a colored block on the timeline
- The width of each block shows how long the task will take
- A red vertical line shows the current time
- Gray shaded areas show breaks or non-working hours

### Connection Between Table and Gantt Chart

The table and Gantt chart work together through:

1. **Unique Task Indexing**: 
   - Each task has the same position (row number) in both the table and Gantt chart
   - When you look at row 3 in the table, the same task appears in position 3 in the Gantt chart

2. **Color Coordination**:
   - Each task has a unique color that is consistent in both views
   - This color coding lets you quickly find the same task in both places

## Using the Dashboard

### Filtering Options

The dashboard has two main filtering options to help you focus on specific information:

1. **Filter by Technician**:
   - Purpose: Shows only tasks assigned to specific technicians
   - How to use: Select one or more technician names from the dropdown menu
   - When to use: When you want to see a particular technician's workload or schedule

2. **Filter by Task**:
   - Purpose: Shows only certain types of tasks based on various properties
   - How to use: Enter search terms or select options from the task filter dropdown
   - When to use: When you need to focus on specific task categories, priorities, or locations

You can use these filters separately or together. To clear filters and see all tasks again, click the "Reset" button.

### Hover and Interactive Features

The dashboard provides additional information when you interact with it:

1. **Table Interactions**:
   - Hovering over a row highlights the matching task in the Gantt chart
   - Clicking on a row selects it and centers the corresponding task in the Gantt view

2. **Gantt Chart Interactions**:
   - Hovering over a task block shows a popup with complete task details including:
     * Task description
     * Start and end times
     * Assigned technicians
     * Required tools and materials
     * Completion percentage
   - Hovering over the red time line shows the current time
   - Clicking on a task selects it and highlights the matching row in the table

## System Integration

The dashboard connects with other maintenance systems:

1. **Preventive Maintenance System**: 
   - Access maintenance records and documentation
   - View maintenance history
   - See manufacturer recommendations

2. **Work Order System**:
   - View complete work order details
   - Check parts and materials status
   - Access equipment information

3. **Ticketing System**:
   - Connect to service tickets
   - View customer communications
   - See problem descriptions and solutions
   - Update ticket status

To use these connections, click on the blue linked text in the task table. The system will open in a new browser tab.

## Task Assignment Algorithm

The dashboard uses a smart algorithm to assign technicians to tasks:

1. **How It Works**:
   - First, the system collects all available tasks from maintenance systems
   - Then it checks which technicians are available during the needed timeframes
   - Next, it matches technician skills with the requirements of each task
   - Finally, it creates optimal assignments based on several factors

2. **Key Factors in Assignments**:
   - Technician skills and certifications
   - Technician availability
   - Task priority and deadline
   - Location (to minimize travel time)
   - Even distribution of work among technicians

This automatic assignment process helps ensure that the right technicians are assigned to the right tasks at the right time, improving efficiency and reducing delays.

## Support Information

This manual explains how to use the Technician Dashboard. If you need help, have questions, or want to request changes, please contact the Technical Support team.

***

Document Version: 1.0  
Last Updated: [Current Date]
