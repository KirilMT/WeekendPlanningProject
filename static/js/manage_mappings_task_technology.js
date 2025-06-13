// --- Task-Technology Mapping Functions ---

// Function to populate a technology select dropdown (used for new task form and edit form)
function populateTechnologySelectDropdown(selectElement, selectedTechnologyValues = null) { // Renamed for clarity, can be single ID or array
    selectElement.innerHTML = ''; // Clear existing options

    const noTechOption = document.createElement('option');
    noTechOption.value = "";
    // For multi-select, a "select technology" might not be appropriate if it's a required field.
    // However, keeping it for now, its behavior in multi-select might need UX review.
    noTechOption.textContent = selectElement.multiple ? '-- Select Technologies --' : '-- Select Technology (Required) --';
    if (!selectElement.multiple) { // Only add "no selection" option for single select
        selectElement.appendChild(noTechOption);
    }


    if (allTechnologies.length === 0) {
        noTechOption.textContent = '-- No Technologies Defined --';
        selectElement.disabled = true;
        return;
    }
    selectElement.disabled = false;

    const technologiesByGroup = {};
    allTechnologies.forEach(t => {
        const groupName = t.group_name || 'Uncategorized';
        if (!technologiesByGroup[groupName]) {
            technologiesByGroup[groupName] = [];
        }
        technologiesByGroup[groupName].push(t);
    });

    const sortedGroupNames = Object.keys(technologiesByGroup).sort();

    const childrenByParentId = {};
    allTechnologies.forEach(t => {
        if (t.parent_id) {
            if (!childrenByParentId[t.parent_id]) childrenByParentId[t.parent_id] = [];
            childrenByParentId[t.parent_id].push(t);
        }
    });
    for (const parentId in childrenByParentId) {
        childrenByParentId[parentId].sort((a, b) => a.name.localeCompare(b.name));
    }

    const hasChildren = (technologyId) => allTechnologies.some(t => t.parent_id === technologyId);

    function appendOptionsRecursive(parentElement, technologyId, level, currentSelectedValues) {
        const children = childrenByParentId[technologyId] || [];
        children.forEach(childTech => {
            const option = document.createElement('option');
            option.value = childTech.id;
            option.textContent = `${'  '.repeat(level)}↳ ${escapeHtml(childTech.name)}`;
            if (currentSelectedValues) {
                if (Array.isArray(currentSelectedValues) && currentSelectedValues.map(String).includes(String(childTech.id))) {
                    option.selected = true;
                } else if (String(currentSelectedValues) === String(childTech.id)) {
                    option.selected = true;
                }
            }
            if (hasChildren(childTech.id)) {
                option.disabled = true;
                option.textContent += " (Parent - cannot assign)";
            }
            parentElement.appendChild(option);
            appendOptionsRecursive(parentElement, childTech.id, level + 1, currentSelectedValues);
        });
    }

    sortedGroupNames.forEach(groupName => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = escapeHtml(groupName);

        const topLevelTechsInGroup = technologiesByGroup[groupName]
            .filter(t => t.parent_id === null)
            .sort((a, b) => a.name.localeCompare(b.name));

        topLevelTechsInGroup.forEach(tech => {
            const option = document.createElement('option');
            option.value = tech.id;
            option.textContent = escapeHtml(tech.name);
            if (selectedTechnologyValues) {
                 if (Array.isArray(selectedTechnologyValues) && selectedTechnologyValues.map(String).includes(String(tech.id))) {
                    option.selected = true;
                } else if (String(selectedTechnologyValues) === String(tech.id)) {
                    option.selected = true;
                }
            }
            if (hasChildren(tech.id)) {
                option.disabled = true;
                option.textContent += " (Parent - cannot assign)";
            }
            optgroup.appendChild(option);
            appendOptionsRecursive(optgroup, tech.id, 1, selectedTechnologyValues);
        });
        selectElement.appendChild(optgroup);
    });
    // For single select, setting .value is fine. For multi-select, 'selected' attribute on options is key.
    // The below line might be redundant if options are correctly marked 'selected', or problematic for multi-select.
    // if (!selectElement.multiple && selectedTechnologyValues && !Array.isArray(selectedTechnologyValues)) {
    //     selectElement.value = selectedTechnologyValues;
    // }
}


async function addNewTaskForMapping() {
    const taskName = newTaskNameForMappingInput.value.trim();
    // Assuming newTaskTechnologySelectForMapping is a multi-select dropdown
    const selectedTechOptions = Array.from(newTaskTechnologySelectForMapping.selectedOptions);
    const technologyIds = selectedTechOptions.map(opt => parseInt(opt.value)).filter(id => !isNaN(id));


    if (!taskName) {
        displayMessage('Task name cannot be empty.', 'error');
        return;
    }
    if (technologyIds.length === 0) {
        displayMessage('At least one technology must be selected for the new task.', 'error');
        return;
    }

    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: taskName, technology_ids: technologyIds }), // Changed to technology_ids
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Task '${escapeHtml(result.name)}' added successfully.`, 'success');
            newTaskNameForMappingInput.value = '';
            // Reset multi-select dropdown
            Array.from(newTaskTechnologySelectForMapping.options).forEach(option => option.selected = false);
            if (newTaskTechnologySelectForMapping.options.length > 0 && !newTaskTechnologySelectForMapping.multiple) {
                 newTaskTechnologySelectForMapping.value = ''; // Reset for single select if it was one
            }
            await fetchAllTasksForMapping(); // Refresh the list
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error adding task: ${error.message}`, 'error');
        console.error('Error in addNewTaskForMapping:', error);
    }
}


async function fetchAllTasksForMapping() {
    if (allTechnologies.length === 0) {
        console.warn("fetchAllTasksForMapping: allTechnologies is empty. Retrying in 1.5s. Ensure fetchAllTechnologies completes successfully first.");
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>Waiting for technologies to load before fetching task mappings...</p>';
        setTimeout(fetchAllTasksForMapping, 1500);
        return;
    }
    try {
        const response = await fetch('/api/tasks_for_mapping');
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Error fetching tasks for mapping. Status: ${response.status}, StatusText: ${response.statusText}, ServerResponse: ${errorText}`);
            throw new Error(`HTTP error! status: ${response.status}. Server said: ${response.statusText}`);
        }
        const tasks = await response.json();
        renderTasksForTechnologyMapping(tasks);
    } catch (error) {
        displayMessage(`Error fetching tasks for mapping: ${error.message}`, 'error');
        console.error('Full error details in fetchAllTasksForMapping catch block:', error);
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>Error loading tasks. Check console and ensure server is running correctly with the latest API endpoints.</p>';
    }
}

function renderTasksForTechnologyMapping(tasks) {
    taskTechnologyMappingListContainerDiv.innerHTML = '';
    if (!tasks || tasks.length === 0) {
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>No tasks found to map. Add a new task above.</p>';
        return;
    }

    if (allTechnologies.length === 0) {
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>Technologies not loaded yet. Cannot map tasks.</p>';
        if (newTaskTechnologySelectForMapping && newTaskTechnologySelectForMapping.options.length <= 1) { // Check if it has more than the placeholder
            populateTechnologySelectDropdown(newTaskTechnologySelectForMapping); // Populate for new task form
        }
        return;
    }
    // Ensure the main new task technology dropdown is populated
    if (newTaskTechnologySelectForMapping) {
         // Assuming newTaskTechnologySelectForMapping is already set to multiple in HTML if needed
        populateTechnologySelectDropdown(newTaskTechnologySelectForMapping);
    }


    tasks.sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    tasks.forEach(task => {
        const itemDiv = document.createElement('div');
        itemDiv.classList.add('list-item', 'task-mapping-item');
        itemDiv.dataset.taskId = task.id;
        // ... (itemDiv styling) ...
        itemDiv.style.display = 'flex';
        itemDiv.style.justifyContent = 'space-between';
        itemDiv.style.alignItems = 'center';
        itemDiv.style.paddingTop = '5px';
        itemDiv.style.paddingBottom = '5px';


        const viewModeDiv = document.createElement('div');
        viewModeDiv.classList.add('task-mapping-view');
        // ... (viewModeDiv styling) ...
        viewModeDiv.style.display = 'flex';
        viewModeDiv.style.flexGrow = '1';
        viewModeDiv.style.alignItems = 'center';
        viewModeDiv.style.marginRight = '10px';

        const taskNameSpan = document.createElement('span');
        taskNameSpan.textContent = escapeHtml(task.name);
        // ... (taskNameSpan styling) ...
        taskNameSpan.style.fontWeight = 'bold';
        taskNameSpan.style.marginRight = '10px';
        taskNameSpan.style.whiteSpace = 'nowrap';
        viewModeDiv.appendChild(taskNameSpan);

        const taskTechSpan = document.createElement('span');
        // Assuming task.technology_ids is an array of IDs and allTechnologies is available
        // Or task.technologies is an array of {id, name} objects
        let techNames = 'No skills assigned';
        if (task.technology_ids && task.technology_ids.length > 0 && allTechnologies.length > 0) {
            techNames = task.technology_ids.map(id => {
                const tech = allTechnologies.find(t => t.id === id);
                return tech ? escapeHtml(tech.name) : 'Unknown Skill';
            }).join(', ');
        } else if (task.technologies && task.technologies.length > 0) { // Alternative if API sends full tech objects
             techNames = task.technologies.map(t => escapeHtml(t.name)).join(', ');
        }
        taskTechSpan.textContent = `(${techNames})`;
        // ... (taskTechSpan styling) ...
        taskTechSpan.style.fontSize = '0.9em';
        taskTechSpan.style.color = '#555';
        taskTechSpan.style.flexGrow = '1';
        taskTechSpan.style.textAlign = 'right';
        taskTechSpan.style.marginLeft = '10px';
        taskTechSpan.style.whiteSpace = 'nowrap';
        taskTechSpan.style.overflow = 'hidden';
        taskTechSpan.style.textOverflow = 'ellipsis';
        viewModeDiv.appendChild(taskTechSpan);
        itemDiv.appendChild(viewModeDiv);

        const editModeDiv = document.createElement('div');
        editModeDiv.classList.add('task-mapping-edit');
        // ... (editModeDiv styling) ...
        editModeDiv.style.display = 'none';
        editModeDiv.style.flexGrow = '1';
        editModeDiv.style.alignItems = 'center';
        editModeDiv.style.marginRight = '10px';


        const taskNameInput = document.createElement('input');
        taskNameInput.type = 'text';
        taskNameInput.value = task.name;
        // ... (taskNameInput styling) ...
        taskNameInput.style.flexGrow = '0.5'; // Adjust as needed
        taskNameInput.style.marginRight = '5px';
        editModeDiv.appendChild(taskNameInput);

        const techSelect = document.createElement('select');
        techSelect.multiple = true; // Make it a multi-select dropdown
        // ... (techSelect styling) ...
        techSelect.style.flexGrow = '1';
        techSelect.style.marginRight = '5px';
        // Populate with all technologies, and select current task's technologies
        // Assuming task.technology_ids is an array of IDs.
        populateTechnologySelectDropdown(techSelect, task.technology_ids || []);
        editModeDiv.appendChild(techSelect);
        itemDiv.appendChild(editModeDiv);


        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');
        // ... (actionsDiv styling) ...
        actionsDiv.style.flexShrink = '0';
        actionsDiv.style.display = 'flex';

        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('edit-btn');
        editBtn.onclick = () => {
            viewModeDiv.style.display = 'none';
            editModeDiv.style.display = 'flex';
            editBtn.style.display = 'none';
            deleteBtn.style.display = 'none';
            saveBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'inline-block';
            // Repopulate and set selected values for the multi-select dropdown
            populateTechnologySelectDropdown(techSelect, task.technology_ids || []);
            taskNameInput.value = task.name; // Ensure name is current
        };
        actionsDiv.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('delete-btn');
        deleteBtn.onclick = () => deleteTaskMapping(task.id, task.name);
        actionsDiv.appendChild(deleteBtn);

        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Save';
        saveBtn.classList.add('save-btn');
        saveBtn.style.backgroundColor = '#28a745';
        saveBtn.style.display = 'none';
        saveBtn.onclick = async () => {
            const newName = taskNameInput.value.trim();
            const selectedTechOptions = Array.from(techSelect.selectedOptions);
            const newTechnologyIds = selectedTechOptions.map(opt => parseInt(opt.value)).filter(id => !isNaN(id));

            if (!newName) {
                displayMessage('Task name cannot be empty.', 'error');
                return;
            }
            if (newTechnologyIds.length === 0) {
                displayMessage('At least one technology must be selected.', 'error');
                return;
            }
            await updateTaskMapping(task.id, newName, newTechnologyIds); // Pass array of IDs
        };
        actionsDiv.appendChild(saveBtn);

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.classList.add('cancel-btn');
        cancelBtn.style.backgroundColor = '#6c757d';
        cancelBtn.style.display = 'none';
        cancelBtn.onclick = () => {
            viewModeDiv.style.display = 'flex';
            editModeDiv.style.display = 'none';
            editBtn.style.display = 'inline-block';
            deleteBtn.style.display = 'inline-block';
            saveBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
        };
        actionsDiv.appendChild(cancelBtn);

        itemDiv.appendChild(actionsDiv);
        taskTechnologyMappingListContainerDiv.appendChild(itemDiv);
    });
}

async function updateTaskMapping(taskId, newName, newTechnologyIds) { // Changed to newTechnologyIds (array)
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName, technology_ids: newTechnologyIds }), // Send technology_ids
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Task '${escapeHtml(result.name)}' updated successfully.`, 'success');
            await fetchAllTasksForMapping();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating task: ${error.message}`, 'error');
        console.error('Error in updateTaskMapping:', error);
    }
}

async function deleteTaskMapping(taskId, taskName) {
    if (!confirm(`Are you sure you want to delete task "${escapeHtml(taskName)}"? This will also remove its assignments to technicians.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Task "${escapeHtml(taskName)}" deleted successfully.`, 'success');
            await fetchAllTasksForMapping();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting task: ${error.message}`, 'error');
        console.error('Error in deleteTaskMapping:', error);
    }
}

async function updateTaskTechnologyMapping(taskId, technologyId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/technology`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({technology_id: technologyId}),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Task ${taskId} technology updated.`, 'success');
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating task technology: ${error.message}`, 'error');
        console.error('Error in updateTaskTechnologyMapping:', error);
    }
}
