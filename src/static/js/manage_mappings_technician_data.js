// Variables like currentMappings, selectedTechnician, currentSelectedTechnicianId, etc.,
// are now expected to be defined in manage_mappings_globals.js

// DOM Elements (assuming these are specific to this file's scope or managed carefully if also global)
// const technicianSelect = document.getElementById('technicianSelect'); // Already in globals
const techSatellitePointSelect = document.getElementById('techSatellitePointSelect');
// const techSattelitePointInput = document.getElementById('techSattelitePoint'); // Old input, also in globals if still used
// const techLinesInput = document.getElementById('techLines'); // Old input, also in globals if still used
// const taskListDiv = document.getElementById('taskList'); // Already in globals
// const technicianSkillsListContainerDiv = document.getElementById('technicianSkillsListContainer'); // This might be specific or global
// const currentTechNameDisplay = document.getElementById('currentTechNameDisplay'); // Already in globals

// New Technician Form Elements
const addNewTechnicianFormContainer = document.getElementById('addNewTechnicianFormContainer');
const newTechnicianNameInput = document.getElementById('newTechnicianNameInput');
const newTechnicianSatellitePointSelect = document.getElementById('newTechnicianSatellitePointSelect');
const saveNewTechnicianBtn = document.getElementById('saveNewTechnicianBtn');
const cancelNewTechnicianBtn = document.getElementById('cancelNewTechnicianBtn');
const newTechnicianError = document.getElementById('newTechnicianError');


// --- Satellite Points Dropdown Population ---
async function fetchAndPopulateSatellitePointsDropdowns() { // Renamed to reflect multiple dropdowns
    try {
        const response = await fetch('/api/satellite_points');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const satellitePoints = await response.json();

        // Populate existing dropdown for selected technician's satellite point
        if (techSatellitePointSelect) {
            const currentSPValue = techSatellitePointSelect.value;
            techSatellitePointSelect.innerHTML = '<option value="">Select Satellite Point</option>'; // Default option
            satellitePoints.forEach(sp => {
                const option = document.createElement('option');
                option.value = sp.id;
                option.textContent = escapeHtml(sp.name);
                techSatellitePointSelect.appendChild(option);
            });
            if (currentSPValue) techSatellitePointSelect.value = currentSPValue; // Preserve selection if any
        }

        // Populate dropdown for the new technician form
        if (newTechnicianSatellitePointSelect) {
            newTechnicianSatellitePointSelect.innerHTML = '<option value="">Select Satellite Point</option>'; // Default option
            satellitePoints.forEach(sp => {
                const option = document.createElement('option');
                option.value = sp.id;
                option.textContent = escapeHtml(sp.name);
                newTechnicianSatellitePointSelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error fetching satellite points:', error);
        displayMessage('Could not load satellite points for dropdowns.', 'error');
        if (techSatellitePointSelect) techSatellitePointSelect.innerHTML = '<option value="">Error loading</option>';
        if (newTechnicianSatellitePointSelect) newTechnicianSatellitePointSelect.innerHTML = '<option value="">Error loading</option>';
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
                const option = document.createElement('option'); // Corrected: Removed unnecessary backslashes
                option.value = techName;
                option.textContent = escapeHtml(techName);
                technicianSelect.appendChild(option);
            });
        }

        let finalTechnicianToLoad = null;
        if (technicianNameToSelect && data.technicians && data.technicians[technicianNameToSelect]) {
            finalTechnicianToLoad = technicianNameToSelect;
        } else if (oldSelectedValue && data.technicians && data.technicians[oldSelectedValue] && oldSelectedValue !== "") { // check oldSelectedValue is not placeholder
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
            // Explicitly set to placeholder and clear details if no technician is to be loaded
            technicianSelect.value = ""; // Default to placeholder
            selectedTechnician = null;
            currentSelectedTechnicianId = null;
            if (document.getElementById('technicianDetails')) {
                document.getElementById('technicianDetails').style.display = 'none';
            }
            if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
            if (taskListDiv) taskListDiv.innerHTML = '';
            if (technicianSkillsListContainerDiv) technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician to view details.</p>';
            // Ensure Edit/Delete buttons are hidden
            const editBtn = document.getElementById('editTechnicianNameBtn');
            const deleteBtn = document.getElementById('deleteTechnicianBtn');
            if (editBtn) editBtn.style.display = 'none';
            if (deleteBtn) deleteBtn.style.display = 'none';
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
    const editBtn = document.getElementById('editTechnicianNameBtn');
    const deleteBtn = document.getElementById('deleteTechnicianBtn');

    if (!technicianName) {
        selectedTechnician = null;
        currentSelectedTechnicianId = null;
        document.getElementById('technicianDetails').style.display = 'none';
        if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
        if (techSatellitePointSelect) techSatellitePointSelect.value = ''; // Reset dropdown
        if (taskListDiv) taskListDiv.innerHTML = '';
        if (technicianSkillsListContainerDiv) technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician to view details.</p>';
        if (editBtn) editBtn.style.display = 'none';
        if (deleteBtn) deleteBtn.style.display = 'none';
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

    // Satellite Point Display and Edit Handling
    const techSatellitePointNameDisplay = document.getElementById('techSatellitePointNameDisplay');
    const editTechSatellitePointBtn = document.getElementById('editTechSatellitePointBtn');
    // techSatellitePointSelect is already a global or correctly scoped variable

    if (techSatellitePointNameDisplay && techSatellitePointSelect && editTechSatellitePointBtn) {
        // Set initial display value
        techSatellitePointNameDisplay.textContent = techData.satellite_point_name || 'Not Set';
        techSatellitePointSelect.value = techData.satellite_point_id || '';

        // Hide select, show text and edit button initially
        techSatellitePointNameDisplay.style.display = 'inline';
        editTechSatellitePointBtn.style.display = 'inline';
        techSatellitePointSelect.style.display = 'none';
    }

    document.getElementById('technicianDetails').style.display = 'block';
    if (editBtn) editBtn.style.display = 'inline-block'; // Or 'block' based on layout
    if (deleteBtn) deleteBtn.style.display = 'inline-block'; // Or 'block' based on layout

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
    // For now, the \`renderTaskCategory\` handles adding/removing from \`explicitly_assigned_tasks\`.

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

// --- Function to handle editing of technician satellite point ---
async function handleTechSatellitePointEdit() {
    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        displayMessage("Please select a technician first.", "info");
        return;
    }

    const techSatellitePointNameDisplay = document.getElementById('techSatellitePointNameDisplay');
    const editTechSatellitePointBtn = document.getElementById('editTechSatellitePointBtn');
    // techSatellitePointSelect is already a global or correctly scoped variable

    if (techSatellitePointNameDisplay && techSatellitePointSelect && editTechSatellitePointBtn) {
        techSatellitePointNameDisplay.style.display = 'none';
        editTechSatellitePointBtn.style.display = 'none';
        techSatellitePointSelect.style.display = 'inline';
        // Ensure the select shows the current value before editing
        techSatellitePointSelect.value = currentMappings.technicians[selectedTechnician]?.satellite_point_id || '';
        techSatellitePointSelect.focus();
    }
}

// --- Function to handle change and auto-save of technician satellite point ---
async function handleTechSatellitePointChange() {
    if (!selectedTechnician || !currentSelectedTechnicianId) {
        displayMessage("No technician selected for saving satellite point.", "error");
        // Optionally revert UI if needed, but an error message should suffice
        return;
    }

    // Ensure this uses the correct select element for the *selected* technician, not the new one.
    const techSatSelect = document.getElementById('techSatellitePointSelect'); // Explicitly get it here for clarity

    const oldSatellitePointName = currentMappings.technicians[selectedTechnician]?.satellite_point_name || 'Not Set';
    const newSatellitePointId = parseInt(techSatSelect.value, 10);
    const newSatellitePointName = techSatSelect.options[techSatSelect.selectedIndex]?.text || 'Not Set';

    const payload = {
        technicians: {
            [selectedTechnician]: { // selectedTechnician is the name
                id: currentSelectedTechnicianId,
                satellite_point_id: isNaN(newSatellitePointId) || newSatellitePointId <= 0 ? null : newSatellitePointId
            }
        }
    };

    try {
        const response = await fetch('/api/save_technician_mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        const techSatellitePointNameDisplay = document.getElementById('techSatellitePointNameDisplay');
        const editTechSatellitePointBtn = document.getElementById('editTechSatellitePointBtn');

        if (response.ok) {
            // displayMessage(result.message || 'Satellite point updated successfully.', 'success'); // Old message
            const successMessage = `Satellite point for ${escapeHtml(selectedTechnician)} changed from '${escapeHtml(oldSatellitePointName)}' to '${escapeHtml(newSatellitePointName)}'.`;
            displayMessage(successMessage, 'success');

            // Update local state
            if (currentMappings.technicians[selectedTechnician]) {
                currentMappings.technicians[selectedTechnician].satellite_point_id = isNaN(newSatellitePointId) || newSatellitePointId <= 0 ? null : newSatellitePointId;
                currentMappings.technicians[selectedTechnician].satellite_point_name = (isNaN(newSatellitePointId) || newSatellitePointId <= 0) ? 'Not Set' : newSatellitePointName;
            }

            // Update UI
            if (techSatellitePointNameDisplay) techSatellitePointNameDisplay.textContent = currentMappings.technicians[selectedTechnician]?.satellite_point_name || 'Not Set';
            if (techSatellitePointSelect) techSatellitePointSelect.style.display = 'none';
            if (techSatellitePointNameDisplay) techSatellitePointNameDisplay.style.display = 'inline';
            if (editTechSatellitePointBtn) editTechSatellitePointBtn.style.display = 'inline';

        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating satellite point: ${error.message}`, 'error');
        // Keep select visible for correction
        const techSatellitePointNameDisplay = document.getElementById('techSatellitePointNameDisplay');
        const editTechSatellitePointBtn = document.getElementById('editTechSatellitePointBtn');
        if (techSatellitePointSelect) techSatellitePointSelect.style.display = 'inline';
        if (techSatellitePointNameDisplay) techSatellitePointNameDisplay.style.display = 'none';
        if (editTechSatellitePointBtn) editTechSatellitePointBtn.style.display = 'none';
    }
}

// --- Placeholder functions for Technician CUD operations --- // This comment might be outdated
// --- Technician CUD operations ---



function handleNewTechnicianNameInputChange() {
    if (newTechnicianNameInput && newTechnicianSatellitePointSelect) {
        newTechnicianSatellitePointSelect.disabled = newTechnicianNameInput.value.trim() === '';
    }
}

async function handleSaveNewTechnician() {
    const name = newTechnicianNameInput.value.trim();
    const satellitePointId = newTechnicianSatellitePointSelect.value;
    const newTechErrorDiv = document.getElementById('newTechnicianError'); // get it fresh

    if (!newTechErrorDiv) {
        console.error("Error display element not found for new technician form.");
        displayMessage("An unexpected UI error occurred.", "error");
        return;
    }
    newTechErrorDiv.style.display = 'none';
    newTechErrorDiv.textContent = '';

    if (!name) {
        newTechErrorDiv.textContent = "Technician name cannot be empty.";
        newTechErrorDiv.style.display = 'block';
        return;
    }
    if (!satellitePointId) {
        newTechErrorDiv.textContent = "Please select a satellite point.";
        newTechErrorDiv.style.display = 'block';
        return;
    }

    const satellitePointIdInt = parseInt(satellitePointId, 10);

    try {
        const payload = { name: name };
        if (!isNaN(satellitePointIdInt) && satellitePointIdInt > 0) {
            payload.satellite_point_id = satellitePointIdInt;
        } else {
            newTechErrorDiv.textContent = "Invalid satellite point selected.";
            newTechErrorDiv.style.display = 'block';
            return;
        }

        const response = await fetch('/api/technicians', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Technician '${escapeHtml(name)}' added successfully.`, 'success');
            newTechnicianNameInput.value = '';
            newTechnicianSatellitePointSelect.value = '';
            await fetchMappings(name); // Refresh and select the new technician
        } else {
            if (response.status === 409) {
                newTechErrorDiv.textContent = `Error: Technician '${name}' already exists.`;
                newTechErrorDiv.style.display = 'block';
            } else {
                throw new Error(result.message || `Server error ${response.status}`);
            }
        }
    } catch (error) {
        console.error('Error in handleSaveNewTechnician:', error);
        newTechErrorDiv.textContent = `Error adding technician: ${error.message}`;
        newTechErrorDiv.style.display = 'block';
    }
}




async function handleEditTechnicianName() {
    if (!selectedTechnician || !currentSelectedTechnicianId) {
        displayMessage("Please select a technician to edit.", "warning");
        return;
    }
    const oldName = selectedTechnician;
    const newNamePrompt = prompt(`Enter new name for ${oldName}:`, oldName);

    if (newNamePrompt && newNamePrompt.trim() !== '' && newNamePrompt.trim() !== oldName) {
        const newName = newNamePrompt.trim();
        try {
            const response = await fetch(`/api/technicians/${currentSelectedTechnicianId}`,
            {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name: newName }), // Only send name for name edit
            });
            const result = await response.json();
            if (response.ok) {
                displayMessage(`Changed name of technician from '${escapeHtml(oldName)}' to '${escapeHtml(newName)}'.`, 'success');
                selectedTechnician = newName; // Update selectedTechnician global variable
                await fetchMappings(newName); // Refresh with the new name selected
            } else {
                throw new Error(result.message || `Server error ${response.status}`);
            }
        } catch (error) {
            displayMessage(`Error editing technician name: ${error.message}`, 'error');
            console.error('Error in handleEditTechnicianName:', error);
            await fetchMappings(oldName);
        }
    } else if (newNamePrompt === oldName) {
        displayMessage("Name is unchanged.", "info");
    } else if (newNamePrompt !== null) { // null means cancel was hit
        displayMessage("Invalid or empty name entered.", "warning");
    } else {
        displayMessage("Edit technician name cancelled.", "info");
    }
}

async function handleDeleteTechnician() {
    if (!selectedTechnician || !currentSelectedTechnicianId) {
        displayMessage("Please select a technician to delete.", "warning");
        return;
    }
    const technicianNameToDelete = selectedTechnician; // Capture for success message
    if (confirm(`Are you sure you want to delete technician \"${escapeHtml(technicianNameToDelete)}\"? This will also remove their skills and task assignments.`)) {
        try {
            const response = await fetch(`/api/technicians/${currentSelectedTechnicianId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            const result = await response.json();
            if (response.ok) {
                displayMessage(`Technician '${escapeHtml(technicianNameToDelete)}' deleted successfully.`, 'success');
                selectedTechnician = null;
                currentSelectedTechnicianId = null;
                // Clear technician details display
                if (document.getElementById('technicianDetails')) {
                    document.getElementById('technicianDetails').style.display = 'none';
                }
                if (currentTechNameDisplay) currentTechNameDisplay.textContent = '';
                if (taskListDiv) taskListDiv.innerHTML = '';
                if (technicianSkillsListContainerDiv) technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician to view details.</p>';

                await fetchMappings(); // Refresh the technician dropdown and main list
            } else {
                throw new Error(result.message || `Server error ${response.status}`);
            }
        } catch (error) {
            displayMessage(`Error deleting technician: ${error.message}`, 'error');
            console.error('Error in handleDeleteTechnician:', error);
        }
    } else {
        displayMessage("Delete cancelled.", "info");
    }
}

// Event Listeners (ensure this runs after DOM is loaded and elements exist)
// It's generally better to place these in a main DOMContentLoaded listener,
// but adding here for self-containment if this script is loaded last.
// Ensure these elements exist before adding listeners.

/* // Removed DOMContentLoaded as listeners are now in manage_mappings_main.js
document.addEventListener('DOMContentLoaded', () => {
    const editButton = document.getElementById('editTechSatellitePointBtn');
    if (editButton) {
        editButton.addEventListener('click', handleTechSatellitePointEdit);
    }

    const selectElement = document.getElementById('techSatellitePointSelect');
    if (selectElement) {
        selectElement.addEventListener('change', handleTechSatellitePointChange);
    }
});
*/
