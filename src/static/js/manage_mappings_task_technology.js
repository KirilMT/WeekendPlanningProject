// --- Task-Technology Mapping Functions ---

// Helper function to check if a technology has children
const hasChildren = (technologyId) => {
    // Ensure allTechnologies is available and is an array
    if (!Array.isArray(allTechnologies)) {
        console.error("hasChildren: allTechnologies is not an array or not available.");
        return false; // Or throw an error, depending on desired strictness
    }
    return allTechnologies.some(t => t.parent_id === technologyId);
};

// Helper function to get the full hierarchical path of a technology
function getTechnologyPath(technologyId) {
    const tech = allTechnologies.find(t => String(t.id) === String(technologyId));
    if (!tech) {
        return "Unknown Technology";
    }

    let path = escapeHtml(tech.name);
    let current = tech;
    while (current.parent_id) {
        const parentTech = allTechnologies.find(t => String(t.id) === String(current.parent_id));
        if (!parentTech) {
            break; // Parent not found, stop building path
        }
        path = `${escapeHtml(parentTech.name)} / ${path}`;
        current = parentTech;
    }

    if (tech.group_name) {
        path = `${escapeHtml(tech.group_name)} / ${path}`;
    }
    return path;
}

// Enhanced filter function for technology select dropdowns
function filterTechnologySelect(selectElement, searchTerm) {
    const lowerSearchTerm = searchTerm.toLowerCase().trim();
    const allOptions = Array.from(selectElement.options);
    const optgroups = Array.from(selectElement.getElementsByTagName('optgroup'));

    // If search term is empty, show all and reset optgroups
    if (!lowerSearchTerm) {
        allOptions.forEach(opt => { opt.style.display = ''; });
        optgroups.forEach(og => { og.style.display = ''; });
        return;
    }

    // Initially hide all relevant elements when a search term is present
    allOptions.forEach(opt => {
        if (opt.value !== "") { // Don't hide functional placeholders if they were to exist
            opt.style.display = 'none';
        }
    });
    optgroups.forEach(og => { og.style.display = 'none'; });

    const optionsToMakeVisible = new Set();
    const optgroupsToMakeVisible = new Set();

    // Pass 1: Find direct matches and add them to our set
    allOptions.forEach(option => {
        if (option.value === "") return; // Skip placeholder options
        const optionText = (option.textContent || "").toLowerCase().trim();
        if (optionText.includes(lowerSearchTerm)) {
            optionsToMakeVisible.add(option);
        }
    });

    // Pass 2: For each directly matched option, ensure its ancestors and optgroup are marked for display
    const initiallyMatchedOptions = Array.from(optionsToMakeVisible); // Iterate on a copy

    initiallyMatchedOptions.forEach(matchedOption => {
        let currentOpt = matchedOption;
        let currentLevel = parseInt(currentOpt.dataset.level);

        // Ensure the matched option itself and its optgroup are marked
        if (currentOpt.parentElement && currentOpt.parentElement.tagName === 'OPTGROUP') {
            optgroupsToMakeVisible.add(currentOpt.parentElement);
        }

        // Climb up to add parents
        while (currentLevel > 0) {
            const parentLevelToFind = currentLevel - 1;
            let prevSibling = currentOpt.previousElementSibling;
            let parentFoundThisStep = false;

            while (prevSibling) {
                if (prevSibling.tagName === 'OPTION' && parseInt(prevSibling.dataset.level) === parentLevelToFind) {
                    optionsToMakeVisible.add(prevSibling); // Add parent to display set
                    if (prevSibling.parentElement && prevSibling.parentElement.tagName === 'OPTGROUP') {
                        optgroupsToMakeVisible.add(prevSibling.parentElement); // Ensure parent's optgroup is also marked
                    }
                    currentOpt = prevSibling; // Continue climbing from this parent
                    currentLevel = parseInt(currentOpt.dataset.level);
                    parentFoundThisStep = true;
                    break; // Found parent for this level, continue with outer while
                }
                if (prevSibling.tagName === 'OPTGROUP') { // Crossed an optgroup boundary upwards
                    currentLevel = 0; // Stop climbing this branch
                    break;
                }
                prevSibling = prevSibling.previousElementSibling;
            }

            if (!parentFoundThisStep) {
                break; // Stop climbing if a parent link is broken for this branch
            }
        }
    });

    // Apply display styles based on the collected sets
    optionsToMakeVisible.forEach(opt => { opt.style.display = ''; });
    optgroupsToMakeVisible.forEach(og => { og.style.display = ''; });

    // Special handling for the "-- Select Technologies --" placeholder in multi-select if it exists and no other options are visible.
    // Note: Current populateTechnologySelectDropdown doesn't add this for multiple=true selects.
    // If it did, and had value="", this logic would apply:
    if (selectElement.multiple) {
        const placeholderOption = allOptions.find(opt => opt.value === "");
        if (placeholderOption) {
            const anyOtherOptionVisible = Array.from(optionsToMakeVisible).some(opt => opt.value !== "");
            if (optionsToMakeVisible.size === 0 || !anyOtherOptionVisible) { // If only placeholder would be visible or no options at all
                 // If search yields no results, decide if placeholder should show.
                 // Current behavior: if search term exists and no results, placeholder also hidden by initial hide.
                 // To show placeholder if no results: placeholderOption.style.display = '';
            } else {
                // If there are results, the placeholder (if it was part of allOptions and not filtered out by value!="")
                // would have been hidden by the initial loop. If it should be hidden when results exist:
                // placeholderOption.style.display = 'none';
            }
        }
    }
}

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

    function appendOptionsRecursive(parentElement, technologyId, level, currentSelectedValues) {
        const children = childrenByParentId[technologyId] || [];
        children.forEach(childTech => {
            const option = document.createElement('option');
            option.value = childTech.id;
            option.innerHTML = `${'&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(level)}↳ ${escapeHtml(childTech.name)}`;
            option.dataset.level = level; // Add data-level
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
            option.dataset.level = 0; // Add data-level for top-level in group
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

            // If a technician is selected, refresh their details to reflect new task availability
            if (selectedTechnician && typeof fetchMappings === 'function') {
                await fetchMappings(selectedTechnician);
            }

        } else {
            displayMessage(result.message || `Error adding task: Server error ${response.status}`, 'error');
        }
    } catch (error) {
        displayMessage(`Failed to add task. Network error or invalid response.`, 'error');
        // console.error('Error in addNewTaskForMapping:', error); // Removed to avoid duplicate console logging
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
        const responseData = await response.json();
        const tasks = responseData.tasks || []; // Extract tasks array from response object
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
        // Base styles that are always applied
        taskTechSpan.style.fontSize = '0.9em';
        taskTechSpan.style.flexGrow = '1';
        taskTechSpan.style.textAlign = 'right';
        taskTechSpan.style.marginLeft = '10px';

        let currentTechDisplayPaths = []; // To store paths of successfully found and valid (non-parent) technologies
        let hasAnyInvalidAssignments = false; // True if any assigned tech ID is not found, or is a parent, or if tech data failed to load
        let finalDisplayMessageForTechSpan = '(No skills assigned)'; // Default message

        if (task.technology_ids && task.technology_ids.length > 0) {
            if (allTechnologies.length > 0) {
                task.technology_ids.forEach(id => {
                    const tech = allTechnologies.find(t => String(t.id) === String(id));
                    if (!tech || hasChildren(tech.id)) {
                        hasAnyInvalidAssignments = true;
                        // We don't add invalid paths to the display list, but flag the issue.
                    } else {
                        currentTechDisplayPaths.push(getTechnologyPath(id));
                    }
                });

                if (currentTechDisplayPaths.length > 0) {
                    finalDisplayMessageForTechSpan = `(${currentTechDisplayPaths.join('<br />')})`;
                    taskTechSpan.innerHTML = finalDisplayMessageForTechSpan;
                    taskTechSpan.style.whiteSpace = 'normal'; // Allow multi-line
                    taskTechSpan.style.overflow = 'visible';  // Ensure content isn't clipped
                    taskTechSpan.style.textOverflow = 'clip';   // No ellipsis for multi-line
                } else {
                    // This means task.technology_ids had items, but none were valid to display
                    hasAnyInvalidAssignments = true;
                    finalDisplayMessageForTechSpan = '(All assigned skills are invalid)';
                    taskTechSpan.textContent = finalDisplayMessageForTechSpan;
                    taskTechSpan.style.whiteSpace = 'nowrap';
                    taskTechSpan.style.overflow = 'hidden';
                    taskTechSpan.style.textOverflow = 'ellipsis';
                }
            } else { // Technologies not loaded, but task has technology_ids
                hasAnyInvalidAssignments = true;
                finalDisplayMessageForTechSpan = '(Error: Technologies not loaded)';
                taskTechSpan.textContent = finalDisplayMessageForTechSpan;
                taskTechSpan.style.whiteSpace = 'nowrap';
                taskTechSpan.style.overflow = 'hidden';
                taskTechSpan.style.textOverflow = 'ellipsis';
            }
        } else { // No technology_ids for the task
            // finalDisplayMessageForTechSpan remains '(No skills assigned)'
            taskTechSpan.textContent = finalDisplayMessageForTechSpan;
            taskTechSpan.style.whiteSpace = 'nowrap';
            taskTechSpan.style.overflow = 'hidden';
            taskTechSpan.style.textOverflow = 'ellipsis';
        }

        // Styling and warning message based on hasAnyInvalidAssignments
        if (hasAnyInvalidAssignments) {
            taskTechSpan.style.color = 'red';
            taskTechSpan.style.fontWeight = 'bold';
            taskTechSpan.title = 'One or more assigned skills are invalid, non-existent, or technologies failed to load. Please edit.';
            // Show warning message only if there was an attempt to assign skills or tech failed to load
            if (task.technology_ids && task.technology_ids.length > 0) {
                 displayMessage(`Task \\"${escapeHtml(task.name)}\\" has issues with its skill assignments. Please review.`, 'warning');
            }
        } else if (!task.technology_ids || task.technology_ids.length === 0) { // Case for "(No skills assigned)"
            taskTechSpan.style.color = 'red';
            taskTechSpan.style.fontWeight = 'bold';
            taskTechSpan.title = 'No skills have been assigned to this task.';
        } else { // Skills are assigned and valid
            taskTechSpan.style.color = '#555'; // Default color
            taskTechSpan.style.fontWeight = 'normal'; // Default font weight
            taskTechSpan.title = '';
        }

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
        taskNameInput.id = `editTaskName_${task.id}`;
        taskNameInput.name = 'taskName';
        taskNameInput.value = task.name;
        // ... (taskNameInput styling) ...
        taskNameInput.style.flexGrow = '1.5'; // Changed from 0.5 to match add form proportion
        taskNameInput.style.marginRight = '10px'; // Changed from 5px to match add form CSS margin
        taskNameInput.style.width = 'auto'; // Ensure consistent width behavior with add form
        editModeDiv.appendChild(taskNameInput);

        const techSelectContainer = document.createElement('div');
        techSelectContainer.style.flexGrow = '1';
        techSelectContainer.style.display = 'flex';
        techSelectContainer.style.flexDirection = 'column';

        const techSearchInput = document.createElement('input');
        techSearchInput.type = 'text';
        techSearchInput.id = `editTaskTechnologySearch_${task.id}`;
        techSearchInput.name = 'techSearch';
        techSearchInput.classList.add('select-search-input');
        techSearchInput.placeholder = 'Search technologies...';
        techSelectContainer.appendChild(techSearchInput);

        const techSelect = document.createElement('select');
        techSelect.multiple = true; // Make it a multi-select dropdown
        techSelect.name = 'requiredSkills';
        techSelect.classList.add('task-technology-select'); // Add class for styling
        techSelect.style.width = '100%'; // Fill container
        // ... (techSelect styling) ...
        // techSelect.style.flexGrow = '1'; // Not needed as container handles flex growth

        populateTechnologySelectDropdown(techSelect, task.technology_ids || []);
        techSelectContainer.appendChild(techSelect);
        editModeDiv.appendChild(techSelectContainer);

        // Event listener for the search input
        techSearchInput.addEventListener('input', () => {
            filterTechnologySelect(techSelect, techSearchInput.value);
        });

        itemDiv.appendChild(editModeDiv);


        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');
        // ... (actionsDiv styling) ...
        actionsDiv.style.flexShrink = '0';
        actionsDiv.style.display = 'flex';

        const editBtn = document.createElement('button');
        editBtn.innerHTML = '<span class="btn-icon">✏️</span> Edit';
        editBtn.classList.add('btn', 'btn-warning', 'btn-sm');
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
        deleteBtn.innerHTML = '<span class="btn-icon">🗑️</span> Delete';
        deleteBtn.classList.add('btn', 'btn-danger', 'btn-sm');
        deleteBtn.onclick = () => deleteTaskMapping(task.id, task.name);
        actionsDiv.appendChild(deleteBtn);

        const saveBtn = document.createElement('button');
        saveBtn.innerHTML = '<span class="btn-icon">💾</span> Save';
        saveBtn.classList.add('btn', 'btn-success', 'btn-sm');
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
        cancelBtn.classList.add('btn', 'btn-secondary', 'btn-sm');
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

    // Event listener for the new task technology search input
    const newTaskTechnologySearchInput = document.getElementById('newTaskTechnologySearch');
    if (newTaskTechnologySearchInput) {
        newTaskTechnologySearchInput.addEventListener('input', () => {
            filterTechnologySelect(newTaskTechnologySelectForMapping, newTaskTechnologySearchInput.value);
        });
    }
}

async function updateTaskMapping(taskId, newName, newTechnologyIds) { // Changed to newTechnologyIds (array)
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName, technology_ids: newTechnologyIds }), // Send technology_ids
        });
        let result;
        let isJson = false;
        try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
                isJson = true;
            } else {
                result = await response.text();
            }
        } catch (err) {
            result = await response.text();
        }
        if (response.ok && isJson) {
            displayMessage(`Task '${escapeHtml(result.name)}' updated successfully.`, 'success');
        } else if (isJson) {
            displayMessage(`Error updating task: ${escapeHtml(result.message || 'Unknown error')}`, 'error');
        } else {
            displayMessage('Server error: ' + result, 'error');
        }
        await fetchAllTasksForMapping();

        // If a technician is selected, refresh their details to reflect updated task skills
        if (selectedTechnician && typeof fetchMappings === 'function') {
            await fetchMappings(selectedTechnician);
        }

    } catch (error) {
        displayMessage(`Error updating task: ${error.message}`, 'error');
        console.error('Error in updateTaskMapping:', error);
    }
}

async function deleteTaskMapping(taskId, taskName) {
    if (!confirm(`Are you sure you want to delete task \"${escapeHtml(taskName)}\"? This will also remove its assignments to technicians.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
        // const result = await response.json(); // result might not be used if only success/failure matters
        if (response.ok) {
            displayMessage(`Task \"${escapeHtml(taskName)}\" deleted successfully.`, 'success');
            await fetchAllTasksForMapping();

            // If a technician is selected, refresh their details as the deleted task might affect them
            if (selectedTechnician && typeof fetchMappings === 'function') {
                await fetchMappings(selectedTechnician);
            }

        } else {
            const result = await response.json().catch(() => ({ message: "Failed to parse error message." })); // Try to parse error
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting task: ${error.message}`, 'error');
        console.error('Error in deleteTaskMapping:', error);
    }
}

// Removed deprecated function updateTaskTechnologyMapping
