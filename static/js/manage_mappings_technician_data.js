// Variables like currentMappings, selectedTechnician, currentSelectedTechnicianId, etc.,\n// are now expected to be defined in manage_mappings_globals.js\n\n// DOM Elements (assuming these are specific to this file's scope or managed carefully if also global)\n// const technicianSelect = document.getElementById(\'technicianSelect\'); // Already in globals\nconst techSatellitePointSelect = document.getElementById(\'techSatellitePointSelect\'); \n// const techSattelitePointInput = document.getElementById(\'techSattelitePoint\'); // Old input, also in globals if still used\n// const techLinesInput = document.getElementById(\'techLines\'); // Old input, also in globals if still used\n// const taskListDiv = document.getElementById(\'taskList\'); // Already in globals\n// const technicianSkillsListContainerDiv = document.getElementById(\'technicianSkillsListContainer\'); // This might be specific or global\n// const currentTechNameDisplay = document.getElementById(\'currentTechNameDisplay\'); // Already in globals\n\n// --- Satellite Points Dropdown Population ---
async function fetchAndPopulateSatellitePointsDropdown() {
    try {
        const response = await fetch('/api/satellite_points');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const satellitePoints = await response.json();
        techSatellitePointSelect.innerHTML = '<option value="">Select Satellite Point</option>'; // Default option
        satellitePoints.forEach(sp => {
            const option = document.createElement('option');
            option.value = sp.id;
            option.textContent = escapeHtml(sp.name);
            techSatellitePointSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching satellite points:', error);
        displayMessage('Could not load satellite points for dropdown.', 'error');
        if (techSatellitePointSelect) techSatellitePointSelect.innerHTML = '<option value="">Error loading</option>';
    }
}

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
        if (techSatellitePointSelect) techSatellitePointSelect.value = ''; // Reset dropdown
        if (taskListDiv) taskListDiv.innerHTML = '';
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
    // if (techSattelitePointInput) techSattelitePointInput.value = techData.sattelite_point || ''; // Old input
    if (techSatellitePointSelect) {
        techSatellitePointSelect.value = techData.satellite_point_id || '';
    }
    // if (techLinesInput) techLinesInput.value = (techData.technician_lines || []).join(', '); // Old input, lines are now derived

    document.getElementById('technicianDetails').style.display = 'block';

    taskListDiv.innerHTML = ''; // Clear previous tasks

    // Render Skill-Matched Tasks
    const skillMatchedTasks = techData.skill_matched_tasks || { full_match: [], partial_match: [] };
    renderTaskCategory(skillMatchedTasks.full_match, "Full Skill Match", taskListDiv);
    renderTaskCategory(skillMatchedTasks.partial_match, "Partial Skill Match", taskListDiv);

    // Optionally, display a message if no skill-matched tasks are found
    if (skillMatchedTasks.full_match.length === 0 && skillMatchedTasks.partial_match.length === 0) {
        const noTasksP = document.createElement('p');
        noTasksP.textContent = 'No tasks found for which this technician possesses any of the required skills.';
        taskListDiv.appendChild(noTasksP);
    }

    // Add a section for tasks that are explicitly assigned but might not appear in skill-matched lists
    // (e.g. if a task has no skills defined, or if assignment logic differs)
    // This part needs careful consideration on how to integrate with the new display.
    // For now, the `renderTaskCategory` handles adding/removing from `explicitly_assigned_tasks`.

    if (!techData.skills || Object.keys(techData.skills).length === 0) {
        await fetchTechnicianSkills(selectedTechnician);
    } else {
        renderTechnicianSkills();
    }
}

function renderTaskCategory(tasks, categoryTitle, parentDiv) {
    if (tasks.length > 0) {
        const categoryHeader = document.createElement('h4');
        categoryHeader.textContent = categoryTitle;
        categoryHeader.style.marginTop = '15px';
        categoryHeader.style.borderBottom = '1px solid #ccc';
        categoryHeader.style.paddingBottom = '5px';
        parentDiv.appendChild(categoryHeader);

        tasks.forEach(task => {
            const taskDiv = document.createElement('div');
            taskDiv.classList.add('task-item', 'skill-matched-task-item');
            taskDiv.dataset.taskId = task.task_id;

            const taskNameSpan = document.createElement('span');
            taskNameSpan.classList.add('task-name-display');
            taskNameSpan.textContent = escapeHtml(task.task_name);
            taskNameSpan.style.fontWeight = 'bold';

            const skillsDetailDiv = document.createElement('div');
            skillsDetailDiv.classList.add('skills-detail-list');
            skillsDetailDiv.style.fontSize = '0.85em';
            skillsDetailDiv.style.marginLeft = '15px';
            skillsDetailDiv.style.marginTop = '5px';

            task.all_required_skills_info.forEach(skillInfo => {
                const skillLine = document.createElement('div');
                skillLine.classList.add('skill-detail-item');
                let textContent = `Skill: ${escapeHtml(skillInfo.skill_name)}`;
                if (skillInfo.possessed) {
                    textContent += ` (Possessed - Level: ${escapeHtml(skillInfo.level)})`;
                    skillLine.style.color = 'green';
                } else {
                    textContent += ` (Missing)`;
                    skillLine.style.color = 'red';
                }
                skillLine.textContent = textContent;
                skillsDetailDiv.appendChild(skillLine);
            });

            taskDiv.appendChild(taskNameSpan);
            taskDiv.appendChild(skillsDetailDiv);
            parentDiv.appendChild(taskDiv);
        });
    }
}

// --- Function to Save All Changes ---
async function saveAllChanges() {
    const payload = {technicians: {}};
    let dataToSaveExists = false;

    // Iterate over all technicians in currentMappings to ensure all are included in payload structure,
    // but only populate specific fields if they are the selectedTechnician OR if we implement broader editing.
    // For now, the primary save action is for the currently selected technician's details that can be changed in the UI.

    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        displayMessage("No technician selected or data is missing.", "info");
        // If we want to save all technicians even if not selected, this logic needs to change.
        // For now, we only save the one being viewed/edited.
        // return; // Commented out to allow saving even if no tech is selected, if other global changes were made.
    }

    // Process the selected technician if one is active
    if (selectedTechnician && currentMappings.technicians[selectedTechnician]) {
        const techName = selectedTechnician;
        const techDataFromState = currentMappings.technicians[techName];
        let currentTechPayload = {
            id: techDataFromState.id, // Include ID for backend to identify the technician
            satellite_point_id: null, // Initialize
            task_assignments: [] // Explicitly sending an empty array as per backend expectation
        };

        // Get satellite_point_id from the dropdown
        if (techSatellitePointSelect) {
            const selectedSPId = parseInt(techSatellitePointSelect.value, 10);
            if (!isNaN(selectedSPId) && selectedSPId > 0) {
                currentTechPayload.satellite_point_id = selectedSPId;
            }
        }
        payload.technicians[techName] = currentTechPayload;
        dataToSaveExists = true;
    } else {
        // If no technician is selected, we might still want to proceed if other types of changes were made (e.g., tasks, technologies)
        // For now, if the action is purely "Save Technician Data" (which was removed), this block wouldn't be hit.
        // The global "Save All Changes" might include other data structures in the future.
        // If payload.technicians remains empty, the backend should handle it gracefully.
        // To ensure the technicians object always exists if there were technicians loaded:
        if (Object.keys(currentMappings.technicians || {}).length > 0 && Object.keys(payload.technicians).length === 0) {
             // This indicates an issue or a save action without a selected tech, which is fine if no tech data was meant to be saved.
        }
    }

    // If other data types (tasks, technologies) were modified and tracked in `unsavedChanges`,
    // they would be prepared and added to the payload here.
    // For now, this function is focused on technician satellite point.

    if (!dataToSaveExists && Object.keys(unsavedChanges).length === 0) { // Also check general unsavedChanges
        displayMessage("No changes to save.", "info");
        return;
    }

    // If only non-technician data changes exist, we might need a different payload structure or endpoint.
    // Assuming /api/save_technician_mappings primarily expects technician data.
    // If payload.technicians is empty but other changes exist, this needs refinement.
    // For now, if dataToSaveExists is false (no technician data changed/selected), but unsavedChanges has other things,
    // we might need to skip the technician part of the payload or call a different endpoint.

    // Let's ensure we only send technician data if it was actually prepared.
    const finalPayload = {};
    if (dataToSaveExists) {
        finalPayload.technicians = payload.technicians;
    }

    // Add other unsaved changes to finalPayload if necessary (e.g., finalPayload.tasks = ...)
    // For now, this example only handles the technician satellite point via this specific save function.

    if (Object.keys(finalPayload).length === 0) {
        displayMessage("No data prepared for saving.", "info");
        return;
    }

    try {
        const response = await fetch('/api/save_technician_mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(finalPayload) // Use finalPayload here
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || "All changes saved successfully.", 'success');
            clearUnsavedChanges(); // Clear general unsaved changes flag/summary
            await fetchMappings(selectedTechnician); // Refresh data for the current technician
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error saving changes: ${error.message}`, 'error');
        console.error('Error in saveAllChanges:', error);
    }
}
