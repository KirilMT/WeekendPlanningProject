// --- Technology Management ---
async function fetchAllTechnologies() {
    try {
        const response = await fetch('/api/technologies');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        allTechnologies = await response.json();
        renderAllTechnologies();
        populateParentTechnologySelect();
        if (selectedTechnician) renderTechnicianSkills();
    } catch (error) {
        displayMessage(`Error fetching technologies: ${error.message}`, 'error');
        console.error('Error fetching technologies:', error);
    }
}

function populateParentTechnologySelect() {
    const techName = newTechnologyNameInput.value.trim();
    const selectedGroupId = newTechnologyGroupSelect.value;

    if (techName === '') {
        // If tech name is empty, newTechnologyGroupSelect and newTechnologyParentSelect
        // are typically disabled by handleTechnologyNameInputChange.
        // We ensure newTechnologyParentSelect is correctly reset and disabled.
        newTechnologyParentSelect.innerHTML = '<option value="">No Parent (Top Level)</option>';
        newTechnologyParentSelect.disabled = true;
    } else {
        // Tech name is present.
        // newTechnologyGroupSelect should be enabled (handled by handleTechnologyNameInputChange).
        // Populate newTechnologyParentSelect based on the selected group.
        // populateParentTechnologySelectFiltered handles the content and disabled state
        // of newTechnologyParentSelect based on selectedGroupId.
        populateParentTechnologySelectFiltered(selectedGroupId);
    }
}

function populateParentTechnologySelectFiltered(selectedGroupId) {
    newTechnologyParentSelect.innerHTML = '<option value="">No Parent (Top Level)</option>';
    if (!selectedGroupId) {
        // If "No Group" or empty group ID is selected, parent select remains with only "No Parent"
        newTechnologyParentSelect.disabled = true; // Also disable if no group is selected
        return;
    }
    newTechnologyParentSelect.disabled = newTechnologyNameInput.value.trim() === ''; // Re-evaluate based on name input

    const groupIdInt = parseInt(selectedGroupId);
    const groupTechnologies = allTechnologies.filter(tech => tech.group_id === groupIdInt);

    function addTechOptions(parentElement, currentParentIdInGroup, level) {
        const children = groupTechnologies.filter(tech => tech.parent_id === currentParentIdInGroup);
        children.sort((a, b) => a.name.localeCompare(b.name));

        children.forEach(tech => {
            const option = document.createElement('option');
            option.value = tech.id;
            option.textContent = `${'  '.repeat(level)}↳ ${escapeHtml(tech.name)}`;
            parentElement.appendChild(option);
            addTechOptions(parentElement, tech.id, level + 1);
        });
    }

    const topLevelInGroup = groupTechnologies.filter(tech => tech.parent_id === null || !groupTechnologies.some(parentTech => parentTech.id === tech.parent_id));
    topLevelInGroup.sort((a, b) => a.name.localeCompare(b.name));

    topLevelInGroup.forEach(tech => {
        const option = document.createElement('option');
        option.value = tech.id;
        option.textContent = escapeHtml(tech.name);
        newTechnologyParentSelect.appendChild(option);
        addTechOptions(newTechnologyParentSelect, tech.id, 1);
    });
}


function renderTechnologyTree(parentElement, technologies, parentId, level) {
    // parentId is the ID of the parent whose children we are rendering.
    // level is the indentation level for these children.
    const children = technologies.filter(tech => tech.parent_id === parentId);
    children.sort((a, b) => a.name.localeCompare(b.name));

    children.forEach(tech => {
        const techDiv = document.createElement('div');
        techDiv.classList.add('list-item');
        // techDiv.classList.add('technology-tree-node'); // Class for border if needed, margin handles indent
        techDiv.style.marginLeft = `${level * 25}px`; // Indent child technologies

        const techNameSpan = document.createElement('span');
        techNameSpan.textContent = escapeHtml(tech.name);
        techDiv.appendChild(techNameSpan);

        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');

        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('edit-btn');
        editBtn.onclick = (e) => {
            e.stopPropagation();
            editTechnology(tech.id, tech.name, tech.group_id, tech.parent_id);
        };
        actionsDiv.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('delete-btn');
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteTechnology(tech.id);
        };
        actionsDiv.appendChild(deleteBtn);

        techDiv.appendChild(actionsDiv);
        parentElement.appendChild(techDiv);

        // Render children of the current 'tech'
        renderTechnologyTree(parentElement, technologies, tech.id, level + 1);
    });
}

function renderAllTechnologies() {
    technologyListContainerDiv.innerHTML = '';
    if (allTechnologies.length === 0) {
        technologyListContainerDiv.innerHTML = '<p>No technologies defined yet.</p>';
        return;
    }

    const topLevelTechnologies = allTechnologies.filter(tech => tech.parent_id === null);
    topLevelTechnologies.sort((a, b) => {
        const groupCompare = (a.group_name || 'ZZZ').localeCompare(b.group_name || 'ZZZ');
        if (groupCompare !== 0) return groupCompare;
        return a.name.localeCompare(b.name);
    });

    let currentGroupName = null;
    topLevelTechnologies.forEach(topLevelTech => {
        if (topLevelTech.group_name !== currentGroupName) {
            const groupHeader = document.createElement('h4');
            groupHeader.textContent = escapeHtml(topLevelTech.group_name || 'Uncategorized');
            // groupHeader.style.marginTop = '15px'; // Handled by class
            // groupHeader.style.marginBottom = '5px'; // Handled by class
            // groupHeader.style.fontWeight = 'bold'; // Handled by class
            groupHeader.classList.add('skill-group-header'); // Use new class for styling
            technologyListContainerDiv.appendChild(groupHeader);
            currentGroupName = topLevelTech.group_name;
        }

        const techDiv = document.createElement('div');
        techDiv.classList.add('list-item');
        // techDiv.classList.add('no-parent'); // Top-level items don't need extra left margin from this class
        techDiv.style.marginLeft = '0px'; // Explicitly no indent for top-level items under a group header

        const techNameSpan = document.createElement('span');
        techNameSpan.textContent = escapeHtml(topLevelTech.name);
        techDiv.appendChild(techNameSpan);

        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('edit-btn');
        editBtn.onclick = (e) => {
            e.stopPropagation();
            editTechnology(topLevelTech.id, topLevelTech.name, topLevelTech.group_id, topLevelTech.parent_id);
        };
        actionsDiv.appendChild(editBtn);
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('delete-btn');
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteTechnology(topLevelTech.id);
        };
        actionsDiv.appendChild(deleteBtn);
        techDiv.appendChild(actionsDiv);
        technologyListContainerDiv.appendChild(techDiv);

        // Render children of this topLevelTech, starting at level 1 for indentation
        renderTechnologyTree(technologyListContainerDiv, allTechnologies, topLevelTech.id, 1);
    });
    populateParentTechnologySelect();
}


async function addNewTechnology() {
    const techName = newTechnologyNameInput.value.trim();
    const selectedGroupId = newTechnologyGroupSelect.value;
    const selectedParentId = newTechnologyParentSelect.value;

    if (!techName) {
        displayMessage('Technology name cannot be empty.', 'error');
        return;
    }

    if (!selectedGroupId) {
        displayMessage('Please assign a technology group. This field is mandatory.', 'error');
        return;
    }

    const payload = { name: techName, group_id: parseInt(selectedGroupId) };
    if (selectedParentId) {
        payload.parent_id = parseInt(selectedParentId);
    }

    try {
        const response = await fetch('/api/technologies', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Technology '${escapeHtml(result.name)}' added.`, 'success');
            newTechnologyNameInput.value = '';
            newTechnologyGroupSelect.value = '';
            newTechnologyParentSelect.value = '';
            // Trigger input event on name input to reset disabled states and dependent dropdowns
            newTechnologyNameInput.dispatchEvent(new Event('input'));
            await fetchAllTechnologies();
            fetchAllTasksForMapping(); // Refresh task mappings
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error adding technology: ${error.message}`, 'error');
        console.error(error);
    }
}

async function editTechnology(techId, currentName, currentGroupId, currentParentId) {
    const newName = prompt("Enter the new name for the technology:", currentName);
    if (newName === null || newName.trim() === "") {
        displayMessage("Edit cancelled or name empty.", "info");
        return;
    }

    const payload = {
        name: newName.trim(),
        group_id: currentGroupId,
        parent_id: currentParentId
    };

    try {
        const response = await fetch(`/api/technologies/${techId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Technology '${escapeHtml(result.name)}' updated.`, 'success');
            await fetchAllTechnologies();
            fetchAllTasksForMapping();
            if (selectedTechnician) renderTechnicianSkills();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating technology: ${error.message}`, 'error');
        console.error(error);
    }
}

async function deleteTechnology(techId) {
    const techToDelete = allTechnologies.find(t => t.id === techId);
    let techName = techToDelete ? techToDelete.name : "this technology";

    // Clean up techName for display: replace literal \\" with "
    if (typeof techName === 'string') {
        techName = techName.replace(/\\\\"/g, '"'); // techName now holds the cleaned name
    }

    // Use the cleaned techName directly in the confirm dialog, without escapeHtml
    if (!confirm(`Are you sure you want to delete \\"${techName}\\"? This may affect child technologies, task mappings, and technician skills.`)) { // Removed ID
        return;
    }
    try {
        const response = await fetch(`/api/technologies/${techId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            // For HTML display, use escapeHtml with the cleaned techName
            displayMessage(result.message || `Technology \\"${escapeHtml(techName)}\\" deleted.`, 'success'); // Removed ID
            await fetchAllTechnologies();
            fetchAllTasksForMapping();
            if (selectedTechnician) {
                await fetchTechnicianSkills(selectedTechnician);
            }
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting technology: ${error.message}`, 'error');
        console.error(error);
    }
}

// --- Technology Group Management ---
async function fetchTechnologyGroups() {
    try {
        const response = await fetch('/api/technology_groups');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        allTechnologyGroups = await response.json();
        renderTechnologyGroups();
    } catch (error) {
        displayMessage(`Error fetching groups: ${error.message}`, 'error');
        console.error(error);
    }
}

function renderTechnologyGroups() {
    technologyGroupListContainerDiv.innerHTML = '';
    const previousGroupValue = newTechnologyGroupSelect.value; // Preserve value if possible
    newTechnologyGroupSelect.innerHTML = '<option value="">No Group</option>';
    if (allTechnologyGroups.length === 0) {
        technologyGroupListContainerDiv.innerHTML = '<p>No groups defined.</p>';
    } else {
        allTechnologyGroups.sort((a, b) => a.name.localeCompare(b.name)).forEach(group => {
            const groupDiv = document.createElement('div');
            groupDiv.classList.add('list-item');
            const nameSpan = document.createElement('span');
            nameSpan.textContent = escapeHtml(group.name);
            groupDiv.appendChild(nameSpan);

            const actionsDiv = document.createElement('div');
            actionsDiv.classList.add('list-item-actions');
            const editBtn = document.createElement('button');
            editBtn.textContent = 'Edit';
            editBtn.classList.add('edit-btn');
            editBtn.onclick = (e) => {
                e.stopPropagation();
                editTechnologyGroup(group.id, group.name);
            };
            actionsDiv.appendChild(editBtn);
            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('delete-btn');
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteTechnologyGroup(group.id);
            };
            actionsDiv.appendChild(deleteBtn);
            groupDiv.appendChild(actionsDiv);
            technologyGroupListContainerDiv.appendChild(groupDiv);

            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = escapeHtml(group.name);
            newTechnologyGroupSelect.appendChild(option);
        });
    }
    if (Array.from(newTechnologyGroupSelect.options).some(opt => opt.value === previousGroupValue)) {
        newTechnologyGroupSelect.value = previousGroupValue;
    }
    if(newTechnologyGroupSelect.value){
        newTechnologyGroupSelect.dispatchEvent(new Event('change'));
    }
}

async function addNewTechnologyGroup() {
    const groupName = newTechnologyGroupNameInput.value.trim();
    if (!groupName) {
        displayMessage('Group name empty.', 'error');
        return;
    }
    try {
        const response = await fetch('/api/technology_groups', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: groupName}),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Group '${escapeHtml(result.name)}' added.`, 'success');
            newTechnologyGroupNameInput.value = '';
            fetchTechnologyGroups();
            fetchAllTechnologies();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error adding group: ${error.message}`, 'error');
        console.error(error);
    }
}

async function editTechnologyGroup(groupId, currentName) {
    const newName = prompt("Enter the new name for the technology group:", currentName);
    if (newName === null || newName.trim() === "") {
        displayMessage("Edit cancelled or name empty.", "info");
        return;
    }
    try {
        const response = await fetch(`/api/technology_groups/${groupId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName.trim()})
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Technology group '${escapeHtml(result.name)}' updated.`, 'success');
            fetchTechnologyGroups();
            fetchAllTechnologies();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating technology group: ${error.message}`, 'error');
        console.error(error);
    }
}

async function deleteTechnologyGroup(groupId) {
    const groupToDelete = allTechnologyGroups.find(g => g.id === groupId);
    const groupName = groupToDelete ? groupToDelete.name : "this group";

    if (!confirm(`Are you sure you want to delete technology group \"${escapeHtml(groupName)}\"? This might affect associated technologies.`)) { // Removed ID
        return;
    }
    try {
        const response = await fetch(`/api/technology_groups/${groupId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Technology group \"${escapeHtml(groupName)}\" deleted.`, 'success'); // Removed ID
            fetchTechnologyGroups();
            fetchAllTechnologies();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting technology group: ${error.message}`, 'error');
        console.error(error);
    }
}
