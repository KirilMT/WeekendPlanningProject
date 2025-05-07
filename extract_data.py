import pandas as pd
from datetime import datetime
import os
import re

# Step 0: Determine the current week (KW)
def get_current_week():
    current_date = datetime(2025, 4, 21)  # Hardcoded for testing
    week_number = current_date.isocalendar().week
    return f"Summary KW{week_number:02d}"  # e.g., "Summary KW17"

# Helper function to get the current week number (e.g., "17")
def get_current_week_number():
    current_date = datetime(2025, 4, 21)  # Hardcoded for testing
    week_number = current_date.isocalendar().week
    return f"{week_number:02d}"

# Step 1: Determine the current day
def get_current_day():
    current_date = datetime(2025, 4, 21)  # Hardcoded for testing
    return current_date.strftime("%A")  # e.g., "Monday"

# Step 2: Determine the current shift
def get_current_shift():
    current_time = 15  # Hardcoded for testing (3 PM)
    if 6 <= current_time < 18:  # 6 AM to 6 PM
        return "early"
    else:  # 6 PM to 6 AM
        return "late"

# Helper function to fill merged cells
def fill_merged_cells(row):
    filled_row = row.copy()
    last_value = ""
    for i in range(len(filled_row)):
        if pd.isna(filled_row.iloc[i]) or str(filled_row.iloc[i]).strip() == "":
            filled_row.iloc[i] = last_value
        else:
            last_value = str(filled_row.iloc[i]).strip()
    return filled_row

# Step 3: Find the correct column and apply filter
def find_and_filter_data(df, current_day, current_shift):
    headers = fill_merged_cells(df.iloc[0])  # Fill merged cells in row 1
    print("Headers in row 1 (cleaned):", headers.tolist())  # Debug

    if isinstance(df.columns, pd.MultiIndex):
        print("Detected MultiIndex columns. Flattening...")
        col_names = ["_".join(str(level).strip() for level in col if str(level) != "nan") for col in df.columns]
    else:
        col_names = df.columns.astype(str).tolist()

    target_day = current_day  # e.g., "Monday"
    current_week = get_current_week_number()  # e.g., "17"
    target_header = f"{target_day} CW-{current_week}"  # e.g., "Monday CW-17"
    matching_columns = []

    print("Column names:", col_names)  # Debug
    for idx, col in enumerate(col_names):
        header_value = str(headers.iloc[idx]).strip()
        print(f"Checking column {idx}: header='{header_value}', col_name='{col}'")  # Debug
        if header_value == target_header:
            matching_columns.append(idx)

    if not matching_columns:
        raise ValueError(f"No columns found for {target_header}. Check row 1 headers.")

    shift_row = fill_merged_cells(df.iloc[1])  # Row 2 (index 1) contains the shift
    target_col = None
    for col_idx in matching_columns:
        shift_value = str(shift_row.iloc[col_idx]).lower().strip()
        print(f"Column {col_idx} shift: {shift_value}")  # Debug
        if shift_value == current_shift:
            target_col = col_idx
            break

    if target_col is None:
        raise ValueError(f"Column for {target_day} with shift {current_shift} not found in week {current_week}")

    df.iloc[:, target_col] = pd.to_numeric(df.iloc[:, target_col], errors='coerce')

    print(f"Values in target_col (index {target_col}) before filtering (first 15 rows):")
    print(df.iloc[:15, target_col].tolist())

    filtered_df = df[df.iloc[:, target_col].notna() & (df.iloc[:, target_col] >= 1)]

    print(f"Filtered DataFrame indices before slicing: {filtered_df.index.tolist()}")
    print(f"Values in target_col after filtering:")
    print(filtered_df.iloc[:, target_col].tolist())

    filtered_df = filtered_df[filtered_df.index >= 8]

    print(f"Filtered DataFrame indices after slicing: {filtered_df.index.tolist()}")

    if filtered_df.empty:
        raise ValueError("No rows remain after filtering and slicing. Check if any rows have values >= 1 in the target column after row 9.")

    return filtered_df, target_col

# Step 4: Extract data
def extract_data(file_path):
    try:
        sheet_name = get_current_week()  # e.g., "Summary KW17"
        current_day = get_current_day()  # e.g., "Monday"
        current_shift = get_current_shift()  # e.g., "early"
        current_week = get_current_week_number()

        _, file_extension = os.path.splitext(file_path)

        if file_extension.lower() == '.xlsb':
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='pyxlsb', header=None)
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl', header=None)

        print("First 10 rows of DataFrame:")
        print(df.head(10))
        print("DataFrame columns:", df.columns.tolist())
        print("Raw row 2 (headers):", df.iloc[1].fillna("").to_list())

        filtered_df, target_col = find_and_filter_data(df, current_day, current_shift)

        headers = fill_merged_cells(df.iloc[1])  # Row 2 (index 1)
        print("Headers in row 2 (cleaned):", headers.to_list())

        required_columns = {
            "scheduler_col": "Scheduler Group /  Task",
            "planning_notes_col": "Planning notes",
            "lines_col": "Lines",
            "mitarbeiter_col": "Mitarbeiter pro Aufgabe",
            "worktime_col": "Planned Worktime in Min",
            "priority_col": "Prio",
            "task_type_col": "&",
            "ticket_mo_col": "Scheduler Name / Dispatch ID / Ticket ID"
        }

        column_indices = {}
        for col_name, header in required_columns.items():
            if col_name == "task_type_col":
                matching_columns = headers[headers.str.contains(r"&", na=False, case=False)]
                if matching_columns.empty:
                    print("Warning: No column header with '&' found. Assuming all tasks are PM.")
                    filtered_df['task_type'] = 'PM'
                    column_indices[col_name] = 'task_type'
                else:
                    column_indices[col_name] = matching_columns.index[0]
            else:
                normalized_header = re.sub(r'\s+', ' ', header.lower().replace('\n', ' ').strip())
                matching_columns = headers[
                    headers.str.lower().str.replace(r'\s+', ' ', regex=True).str.contains(
                        normalized_header, na=False, case=False
                    )
                ]
                if matching_columns.empty and col_name not in ["planning_notes_col", "priority_col", "ticket_mo_col"]:
                    print(f"Error: Column '{header}' not found in row 2. Available headers:")
                    print(headers.to_list())
                    raise ValueError(f"Column '{header}' not found in row 2 of the Excel file.")
                elif matching_columns.empty and col_name == "planning_notes_col":
                    print(f"Warning: Column '{header}' not found in row 2. Setting planning_notes to empty.")
                    filtered_df['planning_notes'] = ''
                    column_indices[col_name] = 'planning_notes'
                elif matching_columns.empty and col_name == "priority_col":
                    print(f"Warning: Column '{header}' not found in row 2. Setting priority to 'R'.")
                    filtered_df['priority'] = 'R'
                    column_indices[col_name] = 'priority'
                elif matching_columns.empty and col_name == "ticket_mo_col":
                    print(f"Warning: Column '{header}' not found in row 2. Setting ticket_mo to empty.")
                    filtered_df['ticket_mo'] = ''
                    column_indices[col_name] = 'ticket_mo'
                else:
                    column_indices[col_name] = matching_columns.index[0]

        # Clean task_type values
        if column_indices["task_type_col"] != 'task_type':
            filtered_df.iloc[:, column_indices["task_type_col"]] = filtered_df.iloc[:,
                                                                   column_indices["task_type_col"]].apply(
                lambda x: re.match(r'^(PM|Rep)', str(x), re.IGNORECASE).group(0).upper() if re.match(r'^(PM|Rep)',
                                                                                                     str(x),
                                                                                                     re.IGNORECASE) else 'PM'
            )

        # Extract data
        scheduler_data = filtered_df.iloc[:, column_indices["scheduler_col"]].astype(str).tolist()
        planning_notes_data = filtered_df.iloc[:, column_indices["planning_notes_col"]].astype(str).tolist() if \
        column_indices["planning_notes_col"] != 'planning_notes' else filtered_df['planning_notes'].astype(str).tolist()
        lines_data = filtered_df.iloc[:, column_indices["lines_col"]].astype(str).tolist()
        mitarbeiter_data = filtered_df.iloc[:, column_indices["mitarbeiter_col"]].astype(str).tolist()
        worktime_data = filtered_df.iloc[:, column_indices["worktime_col"]].astype(str).tolist()
        priority_data = filtered_df.iloc[:, column_indices["priority_col"]].astype(str).tolist() if column_indices[
                                                                                                        "priority_col"] != 'priority' else \
        filtered_df['priority'].astype(str).tolist()
        quantity_data = filtered_df.iloc[:, target_col].astype(str).tolist()
        task_type_data = filtered_df.iloc[:, column_indices["task_type_col"]].astype(str).tolist() if column_indices[
                                                                                                          "task_type_col"] != 'task_type' else \
        filtered_df['task_type'].astype(str).tolist()
        ticket_mo_data = filtered_df.iloc[:, column_indices["ticket_mo_col"]].astype(str).tolist() if column_indices[
                                                                                                          "ticket_mo_col"] != 'ticket_mo' else \
        filtered_df['ticket_mo'].astype(str).tolist()

        extracted_data = []
        for i in range(len(scheduler_data)):
            ticket_mo = ticket_mo_data[i].strip()
            ticket_url = ""
            if task_type_data[i].upper() == 'REP' and ticket_mo and ticket_mo != 'nan':
                # Determine if it's a ticket or MO based on length
                if len(ticket_mo) <= 6:
                    ticket_url = f"https://flux-gfb.tesla.com/app/issues/view/{ticket_mo}"
                else:
                    ticket_url = f"https://flux-gfb.tesla.com/app/schedules/planner-maintenance-grid?ids={ticket_mo}"

            extracted_data.append({
                "scheduler_group_task": scheduler_data[i],
                "planning_notes": planning_notes_data[i],
                "lines": lines_data[i],
                "mitarbeiter_pro_aufgabe": mitarbeiter_data[i],
                "planned_worktime_min": worktime_data[i],
                "priority": priority_data[i],
                "quantity": quantity_data[i],
                "task_type": task_type_data[i],
                "ticket_mo": ticket_mo,
                "ticket_url": ticket_url
            })

        if not extracted_data:
            print(
                f"No tasks found after filtering. Check if the {sheet_name} sheet contains tasks with values >= 1 in the '{current_day} CW-{current_week}' column for shift '{current_shift}' starting from row 9.")

        return extracted_data

    except Exception as e:
        print(f"Error in extract_data: {str(e)}")
        return []