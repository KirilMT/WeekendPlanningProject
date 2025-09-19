import pandas as pd
from datetime import datetime, timedelta
import re
try:
    from wkndPlanning.config import Config
except ImportError:  # Fallback if direct import path differs
    Config = None


def _now():
    """Return debug fixed datetime if configured, else real current datetime."""
    if Config is not None:
        fixed = Config.get_fixed_datetime()
        if fixed:
            return fixed
    return datetime.now()

# Step 0: Determine the current week (KW)
def get_current_week():
    current_date = _now()
    week_number = current_date.isocalendar().week
    return f"Summary KW{week_number:02d}", current_date

# Helper function to get the current week number (e.g., "17")
def get_current_week_number():
    current_date = _now()
    week_number = current_date.isocalendar().week
    return f"{week_number:02d}"

# Step 1: Determine the current day
def get_current_day():
    current_date = _now()
    # If current time is before 6 AM, it's part of the previous day's night shift
    if current_date.hour < 6:
        effective_date = current_date - timedelta(days=1)
        return effective_date.strftime("%A")  # e.g., "Friday"
    else:
        return current_date.strftime("%A")  # e.g., "Monday"

# Step 2: Determine the current shift
def get_current_shift():
    current_time = _now().hour
    # current_time = 20  # Hardcoded for testing (3 PM)
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
    # Determine Day/Shift headers for quantity column (assumed to be in row 0 and 1)
    day_headers_row = fill_merged_cells(df.iloc[0])  # Fill merged cells in row 1 (0-indexed)
    shift_headers_row = fill_merged_cells(df.iloc[1])  # Row 2 (index 1) contains the shift

    target_day = current_day
    current_week = get_current_week_number()
    target_header = f"{target_day} CW-{current_week}"
    matching_columns_for_day = []

    for idx, col_header_val in enumerate(day_headers_row):
        if str(col_header_val).strip() == target_header:
            matching_columns_for_day.append(idx)

    if not matching_columns_for_day:
        raise ValueError(f"No columns found for day header '{target_header}'. Check Excel row 1 (index 0).")

    target_col = None
    for col_idx in matching_columns_for_day:
        shift_value = str(shift_headers_row.iloc[col_idx]).lower().strip()
        if shift_value == current_shift:
            target_col = col_idx
            break

    if target_col is None:
        raise ValueError(f"Column for {target_day} with shift '{current_shift}' not found under day header '{target_header}'. Check Excel row 2 (index 1).")

    # Convert target column to numeric for filtering quantity
    df.iloc[:, target_col] = pd.to_numeric(df.iloc[:, target_col], errors='coerce')

    # Filter rows based on quantity in target_col
    # Initial filter for rows with valid quantity
    filtered_df = df[df.iloc[:, target_col].notna() & (df.iloc[:, target_col] >= 1)].copy() # Use .copy() to avoid SettingWithCopyWarning

    # Further filter to include only rows from Excel row 10 (index 9) onwards
    filtered_df = filtered_df[filtered_df.index >= 9]

    if filtered_df.empty:
        raise ValueError(f"No data rows found with quantity >= 1 in column for '{target_header}' (shift '{current_shift}') at or after Excel row 10 (index 9).")

    return filtered_df, target_col


# Step 4: Extract data
def extract_data(excel_file_object):  # MODIFIED: Changed argument name
    try:
        error_messages = []  # Initialize list for error messages
        sheet_name = get_current_week()[0]  # e.g., "Summary KW17"
        current_day = get_current_day()  # e.g., "Monday"
        current_shift = get_current_shift()  # e.g., "early"
        current_week = get_current_week_number()

        # MODIFIED: Determine engine based on original filename from the stream object
        original_filename = getattr(excel_file_object, 'filename', '').lower()
        engine_to_use = 'pyxlsb' if original_filename.endswith('.xlsb') else 'openpyxl'

        # MODIFIED: Read from the excel_file_object (stream)
        df = pd.read_excel(excel_file_object, sheet_name=sheet_name, engine=engine_to_use, header=None)

        # Find the target column for quantity and the filtered DataFrame
        filtered_df, target_col = find_and_filter_data(df, current_day, current_shift)

        # Get the actual headers for data columns from Excel row 2 (index 1)
        headers = fill_merged_cells(df.iloc[1])
        # print("Headers for data columns (from Excel row 2 / index 1):", headers.to_list())

        required_columns = {
            "scheduler_col": "Scheduler Group /  Task",
            "planning_notes_col": "Planning notes",
            "lines_col": "Lines",
            "mitarbeiter_col": "Mitarbeiter pro Aufgabe",
            "worktime_col": "Planned Worktime in Min",
            "priority_col": "Prio",
            "task_type_col": "&",
            "ticket_mo_col": "Ticket oder MO ID"
        }

        column_indices = {}
        for col_name, header_text in required_columns.items():
            if col_name == "task_type_col":
                # Use headers (from df.iloc[1]) to find the '&' column
                matching_columns = headers[headers.str.contains(r"&", na=False, case=False)]
                if matching_columns.empty:
                    print("Warning: No column header with '&' found in Excel row 2 (index 1). Assuming all tasks are PM.")
                    filtered_df['task_type'] = 'PM'
                    column_indices[col_name] = 'task_type'
                else:
                    column_indices[col_name] = matching_columns.index[0]
            else:
                # Normalize header_text from required_columns for searching in Excel headers
                normalized_search_header = re.sub(r'\\s+', ' ', header_text.lower().replace('\\n', ' ').strip())
                normalized_search_header = re.sub(r'\\s*/\\s*', '/', normalized_search_header) # Handle " / " vs "/"

                # Normalize Excel headers for comparison
                excel_headers_normalized = headers.str.lower().str.replace('\\n', ' ', regex=False)
                excel_headers_normalized = excel_headers_normalized.str.replace(r'\\s*/\\s*', '/', regex=True)
                excel_headers_normalized = excel_headers_normalized.str.replace(r'\\s+', ' ', regex=True).str.strip()

                matching_columns = headers[excel_headers_normalized.str.contains(normalized_search_header, na=False, case=False)]

                if matching_columns.empty and col_name not in ["planning_notes_col", "priority_col", "ticket_mo_col"]:
                    raise ValueError(f"Column '{header_text}' not found in Excel row 2 (index 1).")
                elif matching_columns.empty and col_name == "planning_notes_col":
                    print(f"Warning: Column '{header_text}' not found in Excel row 2 (index 1). Setting planning_notes to empty.")
                    filtered_df['planning_notes'] = ''
                    column_indices[col_name] = 'planning_notes'
                elif matching_columns.empty and col_name == "priority_col":
                    print(f"Warning: Column '{header_text}' not found in Excel row 2 (index 1). Setting priority to 'R'.")
                    filtered_df['priority'] = 'R'
                    column_indices[col_name] = 'priority'
                elif matching_columns.empty and col_name == "ticket_mo_col":
                    print(f"Warning: Column '{header_text}' not found in Excel row 2 (index 1). Setting ticket_mo to empty.")
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
        # Get raw task type data for validation before any transformation
        raw_task_type_values = []
        if column_indices["task_type_col"] != 'task_type': # if it's an actual column index
            raw_task_type_values = filtered_df.iloc[:, column_indices["task_type_col"]].astype(str).tolist()
        else: # if it was defaulted to 'task_type' string key (meaning column not found)
            raw_task_type_values = ['PM'] * len(filtered_df) # Default to 'PM' for each row if column was missing

        ticket_mo_data = filtered_df.iloc[:, column_indices["ticket_mo_col"]].astype(str).tolist() if column_indices[
                                                                                                          "ticket_mo_col"] != 'ticket_mo' else \
        filtered_df['ticket_mo'].astype(str).tolist()

        extracted_data = []
        for i in range(len(scheduler_data)):
            # Corrected row_excel_number: original 0-based index + 1
            row_excel_number = filtered_df.index[i] + 1
            current_errors_for_row = []

            val_scheduler_group_task = scheduler_data[i].strip()
            val_mitarbeiter = mitarbeiter_data[i].strip()
            val_priority = priority_data[i].strip()
            val_worktime = worktime_data[i].strip()
            raw_task_type_value = raw_task_type_values[i].strip()

            # --- VALIDATIONS ---
            # 1. Scheduler Group / Task
            if not val_scheduler_group_task or val_scheduler_group_task.lower() == 'nan':
                current_errors_for_row.append("Scheduler Group / Task cannot be blank.")

            # 2. Mitarbeiter pro Aufgabe
            if not val_mitarbeiter or val_mitarbeiter.lower() == 'nan':
                current_errors_for_row.append("Mitarbeiter pro Aufgabe cannot be blank.")
            else:
                try:
                    if float(val_mitarbeiter) <= 0:
                        current_errors_for_row.append(f"Mitarbeiter pro Aufgabe ('{val_mitarbeiter}') must be a positive number.")
                except ValueError:
                    current_errors_for_row.append(f"Mitarbeiter pro Aufgabe ('{val_mitarbeiter}') must be a numeric value.")

            # 3. Prio
            if not val_priority or val_priority.lower() == 'nan':
                current_errors_for_row.append("Prio cannot be blank.")
            elif not re.match(r"^[A-Z]$", val_priority):
                current_errors_for_row.append(f"Prio ('{val_priority}') must be a single uppercase letter (A-Z).")

            # 4. Planned Worktime in Min
            if not val_worktime or val_worktime.lower() == 'nan':
                current_errors_for_row.append("Planned Worktime in Min cannot be blank.")
            else:
                try:
                    if float(val_worktime) <= 0:
                        current_errors_for_row.append(f"Planned Worktime in Min ('{val_worktime}') must be a positive number.")
                except ValueError:
                    current_errors_for_row.append(f"Planned Worktime in Min ('{val_worktime}') must be a numeric value.")

            # 5. Task Type
            processed_task_type = ""
            # Check if task_type_col was found or defaulted
            if column_indices["task_type_col"] == 'task_type': # This means the '&' column was NOT found, and we defaulted
                # If it defaulted, it means we assumed 'PM'. This is acceptable by definition.
                processed_task_type = "PM"
            else: # The '&' column was found, validate its content
                if not raw_task_type_value or raw_task_type_value.lower() == 'nan':
                    current_errors_for_row.append(f"Task Type (from '&' column) cannot be blank. Must be PM or Rep.")
                else:
                    match = re.match(r'^(PM|Rep)', raw_task_type_value, re.IGNORECASE)
                    if match:
                        processed_task_type = match.group(0).upper()
                    else:
                        current_errors_for_row.append(f"Task Type (from '&' column) must be PM or Rep. Found: '{raw_task_type_value}'.")

            if current_errors_for_row:
                for err in current_errors_for_row:
                    # Try to get a more descriptive task name for the error, if available
                    task_desc_for_error = val_scheduler_group_task if val_scheduler_group_task and val_scheduler_group_task.lower() != 'nan' else "N/A"
                    error_messages.append(f"Excel Row {row_excel_number} (Task: '{task_desc_for_error}'): {err}")
                continue # Skip this row, do not add to extracted_data

            # If all validations passed, proceed to create the data entry
            ticket_mo = ticket_mo_data[i].strip()
            ticket_url = ""
            if processed_task_type.upper() == 'REP' and ticket_mo and ticket_mo.lower() != 'nan':
                if len(ticket_mo) <= 6:
                    ticket_url = f"https://flux-gfb.tesla.com/app/issues/view/{ticket_mo}"
                else:
                    ticket_url = f"https://flux-gfb.tesla.com/app/schedules/planner-maintenance-grid?ids={ticket_mo}"

            extracted_data.append({
                "scheduler_group_task": val_scheduler_group_task,
                "planning_notes": planning_notes_data[i],
                "lines": lines_data[i],
                "mitarbeiter_pro_aufgabe": val_mitarbeiter,
                "planned_worktime_min": val_worktime,
                "priority": val_priority,
                "quantity": quantity_data[i],
                "task_type": processed_task_type,
                "ticket_mo": ticket_mo,
                "ticket_url": ticket_url
            })

        if not extracted_data and not error_messages:
            error_messages.append(
                f"No tasks found after filtering. Check if the {sheet_name} sheet contains tasks with values >= 1 in the '{current_day} CW-{current_week}' column for shift '{current_shift}' starting from row 9."
            )
        elif not extracted_data and error_messages:
             # If there were errors, it's more informative to just show those.
             # The message about no tasks might be redundant if errors explain why.
             pass # error_messages already contains the details

        return extracted_data, error_messages

    except ValueError as ve: # Catch specific ValueErrors from find_and_filter or others
        # These are often configuration/file structure issues
        # Ensure error_messages is initialized if it wasn't (e.g., error in find_and_filter data before error_messages = [])
        if 'error_messages' not in locals() and 'error_messages' not in globals():
            error_messages = []
        error_messages.append(f"Configuration or File Error: {str(ve)}")
        return [], error_messages # Ensure tuple is returned
    except Exception as e:
        # Ensure error_messages is initialized
        if 'error_messages' not in locals() and 'error_messages' not in globals():
            error_messages = []
        error_messages.append(f"Critical error during data extraction: {str(e)}")
        # import traceback
        # error_messages.append(traceback.format_exc())
        return [], error_messages # Ensure tuple is returned
        # print(f"Error in extract_data: {str(e)}") # Keep for server logs if needed
        # raise # Re-raising might hide specific error messages collected
