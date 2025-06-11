// --- Technician Data Fetching and UI Population ---
async function fetchMappings(technicianNameToSelect = null) {
    try {
        const response = await fetch('/api/get_technician_mappings');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        currentMappings = data;

        const oldSelectedValue = technicianSelect.value;
        technicianSelect.innerHTML = '<option value="">Select a Technician</option>';
        if (data.technicians) {
            Object.keys(data.technicians).sort().forEach(techName => {
                const option = document.createElement('option');
                option.value = techName;
                option.textContent = escapeHtml(techName);
                technicianSelect.appendChild(option);
            });
        }

        let finalTechnicianToLoad = null;
        if (technicianNameToSelect && data.technicians && data.technicians[technicianNameToSelect]) {
            finalTechnicianToLoad = technicianNameToSelect;
        } else if (oldSelectedValue && data.technicians && data.technicians[oldSelectedValue]) {
            finalTechnicianToLoad = oldSelectedValue;
        }

        if (finalTechnicianToLoad) {
            technicianSelect.value = finalTechnicianToLoad;
            if (typeof loadTechnicianDetails === 'function') {
                await loadTechnicianDetails(finalTechnicianToLoad);
            } else {
                console.error('loadTechnicianDetails function is not defined. Cannot refresh technician view.');
                displayMessage('Error: UI refresh function missing.', 'error');
            }
        } else {
            selectedTechnician = null;
            currentSelectedTechnicianId = null;
            if (document.getElementById('technicianDetails')) {
                document.getElementById('technicianDetails').style.display = 'none';
            }
            if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
            if (taskListDiv) taskListDiv.innerHTML = '';
            if (technicianSpecialitiesContainerDiv) technicianSpecialitiesContainerDiv.innerHTML = '<p>Select a technician.</p>';
            if (technicianSkillsListContainerDiv) technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician.</p>';
        }
    } catch (error) {
        displayMessage(`Error fetching technician mappings: ${error.message}`, 'error');
        console.error('Error in fetchMappings:', error);
        if (technicianSelect) technicianSelect.innerHTML = '<option value="">Error loading technicians</option>';
        selectedTechnician = null;
        currentSelectedTechnicianId = null;
        if (document.getElementById('technicianDetails')) {
            document.getElementById('technicianDetails').style.display = 'none';
        }
        if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
    }
}

// --- Load Technician Details ---
async function loadTechnicianDetails(technicianName) {
    if (!technicianName) {
        selectedTechnician = null;
        currentSelectedTechnicianId = null;
        document.getElementById('technicianDetails').style.display = 'none';
        if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
        if (taskListDiv) taskListDiv.innerHTML = '';
        if (technicianSpecialitiesContainerDiv) technicianSpecialitiesContainerDiv.innerHTML = '<p>Select a technician.</p>';
        if (technicianSkillsListContainerDiv) technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician.</p>';
        return;
    }

    selectedTechnician = technicianName;
    const techData = currentMappings.technicians[selectedTechnician];

    if (!techData) {
        displayMessage(`Details for ${escapeHtml(technicianName)} not found.`, 'error');
        selectedTechnician = null;
        currentSelectedTechnicianId = null;
        document.getElementById('technicianDetails').style.display = 'none';
        return;
    }

    currentSelectedTechnicianId = techData.id;

    if (currentTechNameDisplay) currentTechNameDisplay.textContent = `Details for: ${escapeHtml(selectedTechnician)}`;
    if (techSattelitePointInput) techSattelitePointInput.value = techData.sattelite_point || '';
    if (techLinesInput) techLinesInput.value = (techData.technician_lines || []).join(', ');

    document.getElementById('technicianDetails').style.display = 'block';

    taskListDiv.innerHTML = '';
    const tasks = techData.task_assignments || [];
    sortAndRecalculatePriorities(tasks);

    if (tasks.length === 0) {
        taskListDiv.innerHTML = '<p>No tasks assigned.</p>';
    } else {
        tasks.forEach((task, index) => {
            const taskDiv = document.createElement('div');
            taskDiv.classList.add('task-item');
            taskDiv.dataset.taskId = task.id || `task-${index}`;

            const taskNameInput = document.createElement('input');
            taskNameInput.type = 'text';
            taskNameInput.classList.add('task-name-input');

            if (task.task === "New Task" && String(task.id).startsWith("new_")) {
                taskNameInput.placeholder = "New Task";
                taskNameInput.value = "";
            } else {
                taskNameInput.value = escapeHtml(task.task);
                taskNameInput.placeholder = 'Task Name';
            }

            taskNameInput.addEventListener('change', (e) => {
                task.task = e.target.value;
                recordChange(`Task name changed for ${selectedTechnician}`);
            });

            const displayPrioSpan = document.createElement('span');
            displayPrioSpan.textContent = ` (Display Group: ${task.display_prio || 'N/A'})`;
            displayPrioSpan.style.fontSize = '0.9em';
            displayPrioSpan.style.marginRight = '10px';
            displayPrioSpan.style.whiteSpace = 'nowrap';

            const taskPrioInput = document.createElement('input');
            taskPrioInput.type = 'number';
            taskPrioInput.value = task.user_prio;
            taskPrioInput.min = 1;
            taskPrioInput.classList.add('task-prio-input');
            taskPrioInput.addEventListener('change', (e) => {
                const newPrio = parseInt(e.target.value);
                if (!isNaN(newPrio) && newPrio >= 1) {
                    task.user_prio = newPrio;
                    recordChange(`Task priority changed for ${selectedTechnician}`);
                    sortAndRecalculatePriorities(tasks);
                    loadTechnicianDetails(selectedTechnician);
                } else {
                    e.target.value = task.user_prio;
                    displayMessage('Priority must be a number >= 1.', 'error');
                }
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('delete-task-btn', 'task-action-btn');
            deleteBtn.onclick = () => {
                if (confirm(`Delete task "${escapeHtml(task.task)}"?`)) {
                    currentMappings.technicians[selectedTechnician].task_assignments = tasks.filter(t => t !== task);
                    recordChange(`Task "${escapeHtml(task.task)}" deleted for ${selectedTechnician}`);
                    loadTechnicianDetails(selectedTechnician);
                }
            };

            if (task.ticket_url && task.ticket_mo) {
                const pmLink = document.createElement('a');
                pmLink.href = task.ticket_url;
                pmLink.textContent = `PM: ${escapeHtml(task.ticket_mo)}`;
                pmLink.target = '_blank';
                pmLink.classList.add('pm-link');
                pmLink.style.marginLeft = '10px';
                taskDiv.appendChild(pmLink);
            }


            taskDiv.appendChild(taskNameInput);
            taskDiv.appendChild(displayPrioSpan);
            taskDiv.appendChild(taskPrioInput);
            taskDiv.appendChild(deleteBtn);
            taskListDiv.appendChild(taskDiv);
        });
    }

    renderTechnicianSpecialities(techData);

    if (!techData.skills || Object.keys(techData.skills).length === 0) {
        await fetchTechnicianSkills(selectedTechnician);
    } else {
        renderTechnicianSkills();
    }
}

// --- Function to Save All Changes ---
async function saveAllChanges() {
    const payload = {technicians: {}};
    let dataToSaveExists = false;

    for (const techName in currentMappings.technicians) {
        if (currentMappings.technicians.hasOwnProperty(techName)) {
            const techDataFromState = currentMappings.technicians[techName];
            let currentTechPayload = {
                sattelite_point: techDataFromState.sattelite_point,
                technician_lines: techDataFromState.technician_lines || [],
                task_assignments: []
            };

            if (selectedTechnician === techName) {
                currentTechPayload.sattelite_point = techSattelitePointInput.value.trim();
                const linesStr = techLinesInput.value.trim();
                currentTechPayload.technician_lines = linesStr ? linesStr.split(',').map(l => {
                    const num = parseInt(l.trim());
                    return isNaN(num) ? null : num;
                }).filter(n => n !== null) : [];
            }

            if (techDataFromState.task_assignments && Array.isArray(techDataFromState.task_assignments)) {
                currentTechPayload.task_assignments = techDataFromState.task_assignments.map(task => ({
                    task: task.task,
                    prio: task.user_prio
                })).filter(t => t.task && typeof t.prio === 'number');
            }
            payload.technicians[techName] = currentTechPayload;
            dataToSaveExists = true;
        }
    }

    if (!dataToSaveExists) {
        displayMessage("No technician data configured to save.", "info");
        return;
    }

    try {
        const response = await fetch('/api/save_technician_mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || "All changes saved successfully.", 'success');
            clearUnsavedChanges();
            await fetchMappings(selectedTechnician);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error saving changes: ${error.message}`, 'error');
        console.error('Error in saveAllChanges:', error);
    }
}

