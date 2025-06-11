let technicianGroups = {};
let uploadedFile = null;
let repTasks = [];
let currentRepTaskIndex = 0;
let repAssignments = [];
let presentTechnicians = [];
let eligibleTechnicians = {}; // This is key for the REP modal
let filename = '';
let sessionId = '';
let additionalTaskCounter = 0; // Counter for additional task IDs

// Generate a simple session ID
function generateSessionId() {
    return Math.random().toString(36).substring(2, 15);
}

// Fetch the grouped technicians from the server
console.log('INDEX.HTML: Fetching technician groups...');
fetch('/technicians')
    .then(response => {
        console.log('INDEX.HTML: Technicians response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('INDEX.HTML: Technician groups received:', data);
        technicianGroups = data;
    })
    .catch(error => {
        console.error('INDEX.HTML: Error fetching technicians:', error);
        showMessage('Error fetching technicians list. Please refresh the page.', 'error');
    });

function populateTechnicianGroups() {
    console.log('INDEX.HTML: Populating technician groups...');
    if (!Object.keys(technicianGroups).length) {
        console.error('INDEX.HTML: No technician groups available for populateTechnicianGroups.');
        showMessage('No technicians available. Please check server configuration.', 'error');
        return;
    }
    const groupsContainer = document.getElementById('technicianGroups');
    groupsContainer.innerHTML = '';

    for (const [groupName, technicians] of Object.entries(technicianGroups)) {
        const groupDiv = document.createElement('div');
        groupDiv.className = `group ${groupName.toLowerCase()}`;

        const groupTitle = document.createElement('h3');
        groupTitle.textContent = groupName;
        groupDiv.appendChild(groupTitle);

        const buttonsDiv = document.createElement('div');
        buttonsDiv.className = 'technician-buttons';

        technicians.forEach(tech => {
            const button = document.createElement('button');
            button.className = 'technician-button';
            button.textContent = tech;
            button.dataset.technician = tech;
            button.addEventListener('click', function () {
                this.classList.toggle('absent');
            });
            buttonsDiv.appendChild(button);
        });

        groupDiv.appendChild(buttonsDiv);
        groupsContainer.appendChild(groupDiv);
    }
    console.log('INDEX.HTML: Technician groups populated.');
}

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        messageDiv.style.display = 'block';
        messageDiv.className = type;
        messageDiv.textContent = text;
        // Scroll to message to ensure it's visible
        messageDiv.scrollIntoView({behavior: 'smooth', block: 'center'});
    } else {
        console.error("INDEX.HTML: Message div not found!");
    }
}

function showAbsentModal() {
    console.log('INDEX.HTML: Showing absent modal...');
    populateTechnicianGroups();
    const absentModal = document.getElementById('absentModal');
    if (absentModal) absentModal.style.display = 'flex';
    else console.error("INDEX.HTML: Absent modal div not found!");
}

function hideAbsentModal() {
    console.log('INDEX.HTML: Hiding absent modal...');
    const absentModal = document.getElementById('absentModal');
    if (absentModal) absentModal.style.display = 'none';
}

function showRepModal() {
    console.log('INDEX.HTML: showRepModal called. Current REP task index:', currentRepTaskIndex, 'Total REP tasks:', repTasks.length);
    if (currentRepTaskIndex < repTasks.length) {
        const task = repTasks[currentRepTaskIndex];
        console.log('INDEX.HTML: Current REP task for modal:', JSON.stringify(task)); // Stringify to see all props
        const ticketInfoDiv = document.getElementById('ticketInfo');
        if (ticketInfoDiv) {
            ticketInfoDiv.innerHTML = `
                            <p><strong>Task:</strong> ${task.name || task.scheduler_group_task || 'Unknown Task'}</p>
                            <p><strong>Ticket/MO:</strong> ${task.ticket_mo || 'N/A'}</p>
                            ${task.ticket_url ? `<p><strong>Link:</strong> <a href="${task.ticket_url}" target="_blank">${task.ticket_url}</a></p>` : ''}
                            <p><strong>Technicians Planned:</strong> ${task.mitarbeiter_pro_aufgabe}</p>
                            <p><strong>Duration:</strong> ${task.planned_worktime_min} minutes</p>
                            <p><strong>Progress:</strong> ${currentRepTaskIndex + 1} of ${repTasks.length}</p>
                            ${task.isAdditionalTask ? '<p><span class="additional-task-badge">Additional Task</span></p>' : ''}
                        `;
        } else {
            console.error("INDEX.HTML: ticketInfo div not found!");
        }
        populateRepTechnicians(task);
        const repSearchInput = document.getElementById('repSearch');
        if (repSearchInput) repSearchInput.value = '';
        const repModalDiv = document.getElementById('repModal');
        if (repModalDiv) repModalDiv.style.display = 'flex';
        else console.error("INDEX.HTML: REP modal div not found!");
    } else {
        console.log('INDEX.HTML: All Rep tasks processed, submitting final assignments...');
        const formData = new FormData();
        // MODIFIED: Send present_technicians directly
        formData.append('present_technicians', JSON.stringify(presentTechnicians));
        formData.append('rep_assignments', JSON.stringify(repAssignments));
        formData.append('session_id', sessionId);
        // ADD THIS: Send all tasks that were part of the REP modal flow
        formData.append('all_processed_tasks', JSON.stringify(repTasks));

        // MODIFIED: Call /generate_dashboard
        fetch('/generate_dashboard', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                console.log('INDEX.HTML: /generate_dashboard response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('INDEX.HTML: /generate_dashboard response data:', data);
                showMessage(data.message, data.message.includes('Error') ? 'error' : 'success');
                if (data.dashboard_url) { // Check for dashboard_url
                    const openDashboardButton = document.getElementById('openDashboardButton');
                    if (openDashboardButton) {
                        openDashboardButton.href = data.dashboard_url; // Set the correct URL
                        openDashboardButton.style.display = 'inline-block';
                    }
                }
            })
            .catch(error => {
                console.error('INDEX.HTML: Error in /generate_dashboard call:', error);
                showMessage('An error occurred generating dashboard: ' + error.message, 'error');
            });
    }
}

function hideRepModal() {
    console.log('INDEX.HTML: Hiding Rep modal...');
    const repModalDiv = document.getElementById('repModal');
    if (repModalDiv) repModalDiv.style.display = 'none';
}

function populateRepTechnicians(task) {
    console.log('INDEX.HTML: populateRepTechnicians called for task ID:', task.id, 'Task Details:', JSON.stringify(task));
    const techniciansContainer = document.getElementById('repTechnicians');
    if (!techniciansContainer) {
        console.error("INDEX.HTML: repTechnicians container div not found!");
        return;
    }
    techniciansContainer.innerHTML = ''; // Clear previous checkboxes

    // Clear any previous informational message
    const existingInfoMsg = document.getElementById('repTaskAvailabilityInfo');
    if (existingInfoMsg) {
        existingInfoMsg.remove();
    }

    console.log('INDEX.HTML: Full eligibleTechnicians object (before populating modal):', JSON.stringify(eligibleTechnicians));
    const availableTechsFromEligible = eligibleTechnicians[task.id] || [];
    console.log(`INDEX.HTML: Technicians from eligibleTechnicians for task.id ${task.id} (for modal):`, JSON.stringify(availableTechsFromEligible));

    const sortedTechnicians = [...availableTechsFromEligible].sort((a, b) => a.name.localeCompare(b.name));

    const techniciansPlannedForTask = parseInt(task.mitarbeiter_pro_aufgabe) || 0;

    // Add an informational message if fewer technicians are available for selection than planned
    if (sortedTechnicians.length < techniciansPlannedForTask && sortedTechnicians.length > 0 && techniciansPlannedForTask > 0) {
        const infoMsg = document.createElement('p');
        infoMsg.id = 'repTaskAvailabilityInfo'; // For easy removal if modal is re-populated
        infoMsg.style.color = 'dimgray';
        infoMsg.style.fontSize = '0.9em';
        infoMsg.style.marginBottom = '10px';
        infoMsg.style.textAlign = 'left';
        infoMsg.textContent = `Note: This task is planned for ${techniciansPlannedForTask} technician(s). Currently, ${sortedTechnicians.length} are eligible and available for selection. You may proceed with the available technicians.`;

        const repSearchInput = document.getElementById('repSearch'); // Insert before search bar
        if (repSearchInput && repSearchInput.parentNode) {
            repSearchInput.parentNode.insertBefore(infoMsg, repSearchInput);
        } else { // Fallback if search input isn't there for some reason
            const ticketInfoDiv = document.getElementById('ticketInfo');
            if (ticketInfoDiv && ticketInfoDiv.parentNode) {
                ticketInfoDiv.parentNode.insertBefore(infoMsg, ticketInfoDiv.nextSibling);
            }
        }
    }


    const validateRepButton = document.getElementById('validateRep');

    if (sortedTechnicians.length === 0) {
        techniciansContainer.innerHTML = '<p>No technicians available with at least 75% of the required time for this task.</p>';
        if (validateRepButton) validateRepButton.disabled = true;
    } else {
        if (validateRepButton) validateRepButton.disabled = false;
        sortedTechnicians.forEach(tech => {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = tech.name;
            checkbox.dataset.technician = tech.name;
            label.appendChild(checkbox);

            const textSpan = document.createElement('span');
            // MODIFIED: Simplified baseText to only show technician's name
            const baseText = `${tech.name}`;
            const taskFullDurationForDisplay = tech.task_full_duration;

            // The 'available_time' here is the gross total work minutes for the shift.
            // This condition now checks if the task itself is longer than the entire shift duration.
            if (taskFullDurationForDisplay > 0 && tech.available_time < taskFullDurationForDisplay) {
                const partialSpan = document.createElement('span');
                partialSpan.style.color = 'orange';
                partialSpan.style.fontWeight = 'bold';
                // MODIFIED: Updated partial assignment message slightly for clarity
                partialSpan.textContent = ' (Task duration exceeds shift total)';
                textSpan.appendChild(document.createTextNode(baseText));
                textSpan.appendChild(partialSpan);
            } else {
                textSpan.textContent = baseText;
            }

            label.appendChild(textSpan);
            techniciansContainer.appendChild(label);
        });
    }
}

function filterTechnicians() {
    console.log('INDEX.HTML: Filtering technicians...');
    const repSearchInput = document.getElementById('repSearch');
    if (!repSearchInput) return;
    const searchValue = repSearchInput.value.toLowerCase();
    const checkboxes = document.querySelectorAll('#repTechnicians label');
    checkboxes.forEach(label => {
        const techName = label.textContent.toLowerCase();
        label.style.display = techName.includes(searchValue) ? 'block' : 'none';
    });
}

// Function to show the additional task modal
function showAdditionalTaskModal() {
    console.log('INDEX.HTML: Showing Additional Task modal');
    const additionalTaskModal = document.getElementById('additionalTaskModal');
    if (additionalTaskModal) {
        // Reset the form
        document.getElementById('additionalTaskForm').reset();

        // Clear any validation state
        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        document.querySelectorAll('.invalid-feedback').forEach(el => el.style.display = 'none');

        // Show the modal
        additionalTaskModal.style.display = 'flex';
    } else {
        console.error("INDEX.HTML: Additional Task modal not found!");
    }
}

// Function to hide the additional task modal
function hideAdditionalTaskModal() {
    console.log('INDEX.HTML: Hiding Additional Task modal');
    const additionalTaskModal = document.getElementById('additionalTaskModal');
    if (additionalTaskModal) {
        additionalTaskModal.style.display = 'none';
    }
}

// Function to validate the additional task form
function validateAdditionalTaskForm() {
    let isValid = true;

    // Required fields validation
    ['taskName', 'taskDuration', 'taskTechnicians', 'taskQuantity', 'taskType'].forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            field.nextElementSibling.style.display = 'block';
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            field.nextElementSibling.style.display = 'none';

            // Additional numeric validation for numbers that must be positive
            if (fieldId === 'taskQuantity' && parseInt(field.value) <= 0) {
                field.classList.add('is-invalid');
                field.nextElementSibling.style.display = 'block';
                isValid = false;
            }
            // Duration and technicians can be 0 (for informational tasks)
        }
    });

    return isValid;
}

// Function to create an additional task
function createAdditionalTask() {
    if (!validateAdditionalTaskForm()) {
        return;
    }

    // Get form values
    const taskName = document.getElementById('taskName').value;
    const taskLines = document.getElementById('taskLines').value;
    const taskTicketMO = document.getElementById('taskTicketMO').value;
    const taskTicketURL = document.getElementById('taskTicketURL').value;
    const taskPriority = document.getElementById('taskPriority').value;
    const taskDuration = parseInt(document.getElementById('taskDuration').value) || 0;
    const taskTechnicians = parseInt(document.getElementById('taskTechnicians').value) || 0;
    const taskQuantity = parseInt(document.getElementById('taskQuantity').value) || 1;
    const taskType = document.getElementById('taskType').value; // Get task type

    // Generate a unique ID for the additional task
    additionalTaskCounter++;
    const additionalTaskId = `additional_${additionalTaskCounter}`;

    // Create task object with the same structure as Excel-imported tasks
    const additionalTask = {
        id: additionalTaskId,
        scheduler_group_task: taskName, // Changed from 'name'
        lines: taskLines,
        mitarbeiter_pro_aufgabe: taskTechnicians,
        planned_worktime_min: taskDuration,
        priority: taskPriority,
        quantity: taskQuantity,
        task_type: taskType, // Use selected task type
        ticket_mo: taskTicketMO,
        ticket_url: taskTicketURL,
        isAdditionalTask: true  // Add a flag to identify additional tasks
    };

    console.log('INDEX.HTML: Created additional task:', additionalTask);

    // Add the additional task to the eligibleTechnicians object
    eligibleTechnicians[additionalTaskId] = [];

    // Determine eligible technicians for this additional task
    const minAcceptableTimeForEligibility = taskDuration * 0.75;

    // Try to get total_work_minutes from the first present technician's eligibility data for any existing task
    let totalWorkMinutesForEligibility = 720; // Default fallback
    if (presentTechnicians.length > 0) {
        const firstPresentTech = presentTechnicians[0];
        for (const taskIdKey in eligibleTechnicians) {
            const techList = eligibleTechnicians[taskIdKey];
            const foundTech = techList.find(t => t.name === firstPresentTech);
            if (foundTech && typeof foundTech.available_time === 'number') {
                totalWorkMinutesForEligibility = foundTech.available_time; // This is the gross available time
                break;
            }
        }
    }
    if (totalWorkMinutesForEligibility === 720 && Object.keys(eligibleTechnicians).length > 0) {
        // Fallback if first tech wasn't in any list, try any tech from any list
        const anyTaskId = Object.keys(eligibleTechnicians)[0];
        if (eligibleTechnicians[anyTaskId].length > 0 && typeof eligibleTechnicians[anyTaskId][0].available_time === 'number') {
            totalWorkMinutesForEligibility = eligibleTechnicians[anyTaskId][0].available_time;
        }
    }
    console.log(`Using totalWorkMinutesForEligibility: ${totalWorkMinutesForEligibility} for additional task eligibility.`);

    presentTechnicians.forEach(techName => {
        // For additional tasks, assume full availability initially for the modal
        // The backend will handle actual scheduling based on all tasks.
        let techObj = {
            name: techName,
            available_time: totalWorkMinutesForEligibility, // Use total work minutes
            task_full_duration: taskDuration
        };

        if (taskDuration === 0 || techObj.available_time >= minAcceptableTimeForEligibility) {
            eligibleTechnicians[additionalTaskId].push(techObj);
        }
    });

    // Add the additional task to repTasks at the current position
    // If the current task type is PM, we might need a different logic or array
    // For now, assuming additional tasks are treated like REP tasks for modal flow
    repTasks.splice(currentRepTaskIndex, 0, additionalTask);

    // Hide the additional task modal
    hideAdditionalTaskModal();

    // Show the REP modal for this task (or the next one if it was a PM task)
    showRepModal();
}

function getTotalWorkMinutesFromSomewhere() {
    // This function is no longer directly called by createAdditionalTask.
    // Kept for reference or if other parts might use it, but should be reviewed.
    console.warn("getTotalWorkMinutesFromSomewhere is a placeholder. Ensure it returns the correct total work minutes if used elsewhere.");
    return 720; // Defaulting to 12 hours, adjust as necessary or fetch dynamically
}

document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function (event) {
            event.preventDefault();
            console.log('INDEX.HTML: Upload form submitted.');
            const fileInput = document.getElementById('excelFile');
            if (!fileInput || !fileInput.files.length) {
                console.log('INDEX.HTML: No file selected.');
                showMessage('Please select a file to upload.', 'error');
                return;
            }
            uploadedFile = fileInput.files[0];
            sessionId = generateSessionId();
            const formData = new FormData();
            formData.append('excelFile', uploadedFile);
            formData.append('session_id', sessionId);
            console.log('INDEX.HTML: FormData for initial upload:', Array.from(formData.entries()));
            console.log('INDEX.HTML: Sending initial upload request...');

            // Show loading message
            showMessage('Uploading and validating file...', 'success');

            // Disable submit button while processing
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
                .then(response => {
                    console.log('INDEX.HTML: Initial upload response status:', response.status);
                    // Store the response status for checking if it's an error
                    const isResponseError = !response.ok;
                    return response.json().then(data => {
                        // Return both the data and the error status
                        return {data, isResponseError};
                    });
                })
                .then(({data, isResponseError}) => {
                    // Re-enable submit button
                    submitButton.disabled = false;

                    console.log('INDEX.HTML: Initial upload response data:', data);

                    // Check if there was an error in the response
                    if (isResponseError || data.message.includes('Error') || data.message.includes('not contain data for the current week')) {
                        console.log('INDEX.HTML: Initial upload error:', data.message);

                        // Display a more compact error message
                        const messageDiv = document.getElementById('message');
                        if (messageDiv) {
                            messageDiv.style.display = 'block';
                            // className will be set based on error type below

                            // For week number mismatch errors
                            if (data.message.includes('Week mismatch error')) {
                                messageDiv.className = 'error week-mismatch-error'; // Apply specific class
                                // Extract the current week number and available weeks
                                const weekMatch = data.message.match(/current week \((\d+)\)/);
                                const currentWeekNum = weekMatch ? weekMatch[1] : '?';

                                const availableMatch = data.message.match(/week\(s\): ([^"]+)/);
                                const availableWeeks = availableMatch ? availableMatch[1].trim() : 'None';

                                // Find the largest available week
                                let largestWeek = '';
                                if (availableWeeks !== 'None') {
                                    const weekNumbers = availableWeeks.split(', ').map(w => parseInt(w));
                                    if (weekNumbers.length > 0) {
                                        largestWeek = Math.max(...weekNumbers).toString();
                                    }
                                }

                                // Create an improved week error message with better formatting
                                // The outer #message.error div provides background and main border.
                                messageDiv.innerHTML = `
                                        <div style="display: flex; align-items: center; gap: 12px;">
                                            <div style="font-size: 22px; line-height: 1; color: #c62828;">⚠️</div>
                                            <div>
                                                <div style="font-weight: bold; margin-bottom: 3px;">Incorrect Excel File</div>
                                                <div style="font-size: 0.9em;">You uploaded an Excel file for week <span style="font-weight: bold;">${largestWeek}</span> but the current week is <span style="font-weight: bold;">${currentWeekNum}</span>.</div>
                                                <div style="margin-top: 5px; font-style: italic; opacity: 0.85; font-size: 0.85em;">Please upload an Excel file that contains data for week ${currentWeekNum}.</div>
                                            </div>
                                        </div>
                                    `;
                            } else {
                                // Other errors - use general error styling
                                messageDiv.className = 'error';
                                messageDiv.textContent = data.message; // The ::before pseudo-element will add the icon
                            }

                            // Scroll to message to ensure it's visible
                            messageDiv.scrollIntoView({behavior: 'smooth', block: 'center'});
                        }
                    } else {
                        console.log('INDEX.HTML: Initial upload successful, preparing for absent modal.');
                        showMessage('File uploaded successfully. Please select absent technicians.', 'success');
                        repTasks = data.repTasks || [];
                        console.log('INDEX.HTML: repTasks after initial upload:', JSON.stringify(repTasks));
                        filename = data.filename || '';
                        sessionId = data.session_id || sessionId;
                        currentRepTaskIndex = 0;
                        repAssignments = [];
                        showAbsentModal();
                    }
                })
                .catch(error => {
                    // Re-enable submit button
                    if (submitButton) submitButton.disabled = false;

                    console.error('INDEX.HTML: Initial upload fetch error:', error);
                    showMessage('An error occurred during initial upload: ' + error.message, 'error');
                });
        });
    } else {
        console.error("INDEX.HTML: uploadForm not found!");
    }

    const confirmAbsentButton = document.getElementById('confirmAbsent');
    if (confirmAbsentButton) {
        confirmAbsentButton.addEventListener('click', function () {
            console.log('INDEX.HTML: Confirm absent technicians clicked.');
            const absentButtons = document.querySelectorAll('.technician-button.absent');
            const absentTechnicians = Array.from(absentButtons).map(btn => btn.dataset.technician);
            console.log('INDEX.HTML: Absent technicians selected:', absentTechnicians);
            presentTechnicians = Object.values(technicianGroups).flat().filter(tech => !absentTechnicians.includes(tech));
            console.log('INDEX.HTML: Present technicians:', presentTechnicians);
            const formData = new FormData();
            formData.append('absentTechnicians', JSON.stringify(absentTechnicians)); // Corrected typo: absentTechnarians to absentTechnicians
            formData.append('filename', filename);
            formData.append('session_id', sessionId);
            console.log('INDEX.HTML: Sending PM processing request (after absent selection)...');
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
                .then(response => {
                    console.log('INDEX.HTML: PM processing response status:', response.status);
                    return response.json();
                })
                .then(data => {
                    console.log('INDEX.HTML: PM processing response data:', data);
                    if (data.message.includes('Error')) {
                        showMessage(data.message, 'error');
                        hideAbsentModal();
                    } else {
                        repTasks = data.repTasks || [];
                        eligibleTechnicians = data.eligibleTechnicians || {}; // CRITICAL: eligibleTechnicians populated here
                        filename = data.filename || filename;
                        sessionId = data.session_id || sessionId;
                        console.log('INDEX.HTML: repTasks after PM processing:', JSON.stringify(repTasks));
                        console.log('INDEX.HTML: eligibleTechnicians for REP tasks after PM processing:', JSON.stringify(eligibleTechnicians));
                        hideAbsentModal();
                        if (repTasks.length > 0) {
                            // Store totalWorkMinutes globally or make it accessible
                            // For example, if it's part of the 'data' response:
                            // window.totalWorkMinutes = data.totalWorkMinutes;
                            showRepModal();
                        } else {
                            showMessage('No REP tasks to assign. Generating dashboard...', 'success');
                            const finalFormData = new FormData();
                            // MODIFIED: Send present_technicians directly
                            finalFormData.append('present_technicians', JSON.stringify(presentTechnicians));
                            finalFormData.append('rep_assignments', JSON.stringify([])); // No REP assignments
                            finalFormData.append('session_id', sessionId);
                            // MODIFIED: Call /generate_dashboard
                            fetch('/generate_dashboard', {
                                method: 'POST',
                                body: finalFormData
                            })
                                .then(response => response.json())
                                .then(finalData => {
                                    showMessage(finalData.message, finalData.message.includes('Error') ? 'error' : 'success');
                                    if (finalData.dashboard_url) { // Check for dashboard_url
                                        const openDashboardButton = document.getElementById('openDashboardButton');
                                        if (openDashboardButton) {
                                            openDashboardButton.href = finalData.dashboard_url; // Set the correct URL
                                            openDashboardButton.style.display = 'inline-block';
                                        }
                                    }
                                })
                                .catch(error => {
                                    showMessage('An error occurred generating dashboard with no REP tasks: ' + error.message, 'error');
                                });
                        }
                    }
                })
                .catch(error => {
                    console.error('INDEX.HTML: PM processing fetch error:', error);
                    showMessage('An error occurred during PM processing: ' + error.message, 'error');
                    hideAbsentModal();
                });
        });
    } else {
        console.error("INDEX.HTML: confirmAbsent button not found!");
    }

    const repSearchInput = document.getElementById('repSearch');
    if (repSearchInput) {
        repSearchInput.addEventListener('input', filterTechnicians);
    } else {
        console.error("INDEX.HTML: repSearch input not found!");
    }

    const validateRepButton = document.getElementById('validateRep');
    if (validateRepButton) {
        validateRepButton.addEventListener('click', function () {
            console.log('INDEX.HTML: Validate Rep selection clicked.');
            const selectedCheckboxes = document.querySelectorAll('#repTechnicians input[type="checkbox"]:checked');
            const selectedTechnicians = Array.from(selectedCheckboxes).map(cb => cb.value);
            const task = repTasks[currentRepTaskIndex];
            const techniciansPlanned = parseInt(task.mitarbeiter_pro_aufgabe) || 0;

            // Get the number of technicians currently available for selection in the modal
            const availableTechsInModal = eligibleTechnicians[task.id] ? eligibleTechnicians[task.id].length : 0;

            console.log('INDEX.HTML: Selected technicians for REP:', selectedTechnicians, 'Technicians Planned:', techniciansPlanned, 'Available in Modal:', availableTechsInModal);

            if (techniciansPlanned > 0 && selectedTechnicians.length === 0) {
                alert(`This task is planned for ${techniciansPlanned} technician(s). Please select at least one technician to proceed, or skip the task.`);
                return;
            }

            // NEW LOGIC:
            // If enough technicians are available in the modal to meet the plan,
            // but the user selected fewer than planned, then show a blocking alert.
            if (availableTechsInModal >= techniciansPlanned && selectedTechnicians.length < techniciansPlanned && techniciansPlanned > 0) {
                alert(`This task is planned for ${techniciansPlanned} technician(s), and enough are available. Please select at least ${techniciansPlanned} technician(s).`);
                return;
            }
            // If fewer technicians are available in the modal than planned (availableTechsInModal < techniciansPlanned),
            // or if the task is planned for 0 technicians,
            // or if the user selected the planned number or more,
            // then proceed without a blocking alert. The informational message in populateRepTechnicians handles the first case.

            repAssignments.push({
                task_id: task.id,
                technicians: selectedTechnicians,
                ticket_mo: task.ticket_mo,
                ticket_url: task.ticket_url,
                isAdditionalTask: task.isAdditionalTask || false // Preserve additional task flag
            });
            console.log('INDEX.HTML: Rep assignment added:', repAssignments[repAssignments.length - 1]);

            // Update eligibleTechnicians for SUBSEQUENT tasks
            const assignedTaskDuration = parseInt(task.planned_worktime_min) || 0;
            // No longer update eligibleTechnicians here, as it's based on gross time for the modal.
            // The backend (assign_tasks) will handle the actual time calculations.
            /*
            selectedTechnicians.forEach(assignedTechName => {
                Object.keys(eligibleTechnicians).forEach(otherTaskId => {
                    eligibleTechnicians[otherTaskId] = eligibleTechnicians[otherTaskId].map(tech => {
                        if (tech.name === assignedTechName) {
                            return { ...tech, available_time: tech.available_time - assignedTaskDuration };
                        }
                        return tech;
                    }).filter(tech => {
                        const otherTaskDetails = repTasks.find(t => t.id === otherTaskId);
                        if (!otherTaskDetails) return false;

                        const otherTaskFullDuration = parseInt(otherTaskDetails.planned_worktime_min) || 0;
                        const otherTaskMinAcceptable = otherTaskFullDuration * 0.75;

                        if (otherTaskFullDuration > 0) {
                            return tech.available_time >= otherTaskMinAcceptable;
                        }
                        return true;
                    });
                });
            });
            console.log("INDEX.HTML: eligibleTechnicians updated after assignment:", JSON.stringify(eligibleTechnicians));
            */

            currentRepTaskIndex++;
            hideRepModal();
            showRepModal(); // Show the next REP task or finalise
        });
    } else {
        console.error("INDEX.HTML: validateRep button not found!");
    }

    const skipRepButton = document.getElementById('skipRep');
    if (skipRepButton) {
        skipRepButton.addEventListener('click', function () {
            console.log('INDEX.HTML: Skip Rep task clicked.');
            const rawReason = prompt("Please enter a reason for skipping this task (optional):", "");
            let skipReasonMessage = "Skipped reason."; // Default if prompt is cancelled or empty

            if (rawReason !== null && rawReason.trim() !== "") {
                skipReasonMessage = `Skipped reason: ${rawReason.trim()}`;
            } else if (rawReason === null) { // User pressed Cancel
                skipReasonMessage = "Skipped reason (note cancelled).";
            } else { // User pressed OK with empty or whitespace
                skipReasonMessage = "Skipped reason (no specific note provided).";
            }

            repAssignments.push({
                task_id: repTasks[currentRepTaskIndex].id,
                technicians: [],
                ticket_mo: repTasks[currentRepTaskIndex].ticket_mo,
                ticket_url: repTasks[currentRepTaskIndex].ticket_url,
                skipped: true,
                skip_reason: skipReasonMessage, // Add the reason here
                isAdditionalTask: repTasks[currentRepTaskIndex].isAdditionalTask || false // Preserve additional task flag
            });
            console.log('INDEX.HTML: Rep task skipped:', repAssignments[repAssignments.length - 1]);
            currentRepTaskIndex++;
            hideRepModal();
            showRepModal(); // Show the next REP task or finalise
        });
    } else {
        console.error("INDEX.HTML: skipRep button not found!");
    }

    // Add event listener for "Add Additional Task" button
    const addAdditionalTaskButton = document.getElementById('addAdditionalTask');
    if (addAdditionalTaskButton) {
        addAdditionalTaskButton.addEventListener('click', function () {
            console.log('INDEX.HTML: Add Additional Task button clicked.');
            hideRepModal();
            showAdditionalTaskModal();
        });
    } else {
        console.error("INDEX.HTML: addAdditionalTask button not found!");
    }

    // Add event listeners for additional task form buttons
    const createAdditionalTaskButton = document.getElementById('createAdditionalTask');
    const cancelAdditionalTaskButton = document.getElementById('cancelAdditionalTask');
    const additionalTaskForm = document.getElementById('additionalTaskForm');

    if (additionalTaskForm) {
        additionalTaskForm.addEventListener('submit', function (event) {
            event.preventDefault();
            createAdditionalTask();
        });
    }

    if (cancelAdditionalTaskButton) {
        cancelAdditionalTaskButton.addEventListener('click', function () {
            hideAdditionalTaskModal();
            showRepModal(); // Return to the current REP task
        });
    }

    const openDashboardButton = document.getElementById('openDashboardButton');
    if (openDashboardButton) {
        openDashboardButton.onclick = function () {
            window.location.href = '/output/technician_dashboard.html';
        };
    }

    const manageMappingsBtn = document.getElementById('manageMappingsBtn');
    if (manageMappingsBtn) {
        manageMappingsBtn.onclick = function () {
            window.location.href = '/manage_mappings_ui';
        };
    }

});