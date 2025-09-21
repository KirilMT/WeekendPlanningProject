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
        techDiv.dataset.techId = tech.id;
        techDiv.style.marginLeft = `${level * 25}px`; // Indent child technologies

        const techNameSpan = document.createElement('span');
        techNameSpan.textContent = escapeHtml(tech.name);
        techDiv.appendChild(techNameSpan);

        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');

        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('btn', 'btn-warning', 'btn-sm');
                    editBtn.onclick = (e) => {
                        e.stopPropagation();
                        editTechnology(tech.id);
                    };        actionsDiv.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('btn', 'btn-danger', 'btn-sm');
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
        techDiv.dataset.techId = topLevelTech.id;
        // techDiv.classList.add('no-parent'); // Top-level items don't need extra left margin from this class
        techDiv.style.marginLeft = '0px'; // Explicitly no indent for top-level items under a group header

        const techNameSpan = document.createElement('span');
        techNameSpan.textContent = escapeHtml(topLevelTech.name);
        techDiv.appendChild(techNameSpan);

        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('list-item-actions');
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('btn', 'btn-warning', 'btn-sm');
        editBtn.onclick = (e) => {
            e.stopPropagation();
            editTechnology(topLevelTech.id);
        };
        actionsDiv.appendChild(editBtn);
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('btn', 'btn-danger', 'btn-sm');
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
            await fetchAllTasksForMapping(); // Refresh task mappings
            if (selectedTechnician) { // If a technician is selected, refresh their details
                await fetchMappings(selectedTechnician);
            }
        } else {
            displayMessage(result.message || `Error adding technology: Server error ${response.status}`, 'error');
        }
    } catch (error) {
        displayMessage(`Failed to add technology. Network error or invalid response.`, 'error');
        // console.error(error); // Removed to avoid duplicate console logging
    }
}

async function editTechnology(techId) {
    const techToEdit = allTechnologies.find(tech => tech.id === techId);
    if (!techToEdit) {
        console.error(`Technology with ID ${techId} not found.`);
        return;
    }

    const currentName = techToEdit.name;
    const currentGroupId = techToEdit.group_id;
    const currentParentId = techToEdit.parent_id;
    const techListItem = technologyListContainerDiv.querySelector(`.list-item[data-tech-id="${techId}"]`);
    if (!techListItem) {
        console.error(`Could not find list item for technology ID ${techId}`);
        return;
    }

    const originalContent = techListItem.innerHTML;

    // Create Group Dropdown
    let groupSelectHtml = `<select id="editTechnologyGroupSelect_${techId}" name="groupId" class="form-control">`;
    allTechnologyGroups.forEach(group => {
        const isSelected = parseInt(group.id) === parseInt(currentGroupId) ? 'selected' : '';
        groupSelectHtml += `<option value="${group.id}" ${isSelected}>${escapeHtml(group.name)}</option>`;
    });
    groupSelectHtml += '</select>';

    // Create Parent Dropdown
    let parentSelectHtml = `<select id="editTechnologyParentSelect_${techId}" name="parentId" class="form-control">`;
    parentSelectHtml += '<option value="">No Parent</option>';
    allTechnologies.forEach(tech => {
        if (tech.id !== techId) { // Cannot be its own parent
            const isSelected = parseInt(tech.id) === parseInt(currentParentId) ? 'selected' : '';
            parentSelectHtml += `<option value="${tech.id}" ${isSelected}>${escapeHtml(tech.name)}</option>`;
        }
    });
    parentSelectHtml += '</select>';

    techListItem.innerHTML = `
        <input type="text" id="editTechnologyName_${techId}" value="${escapeHtml(currentName)}" class="form-control" style="flex-grow: 1;"/>
        ${groupSelectHtml}
        ${parentSelectHtml}
        <div class="item-actions">
            <button class="btn btn-success btn-sm save-tech-btn">💾 Save</button>
            <button class="btn btn-secondary btn-sm cancel-edit-tech-btn">❌ Cancel</button>
        </div>
    `;

    techListItem.querySelector('.save-tech-btn').addEventListener('click', async () => {
        const newName = techListItem.querySelector('input').value.trim();
        const newGroupId = parseInt(techListItem.querySelector('select').value);
        const newParentId = techListItem.querySelectorAll('select')[1].value ? parseInt(techListItem.querySelectorAll('select')[1].value) : null;

        if (newName) {
            const payload = {
                name: newName,
                group_id: newGroupId,
                parent_id: newParentId
            };

            try {
                const response = await fetch(`/api/technologies/${techId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (response.ok) {
                    displayMessage(`Technology '${escapeHtml(result.name)}' updated.`, 'success');
                    // Explicitly update the technology in the allTechnologies array
                    const updatedTechIndex = allTechnologies.findIndex(t => t.id === techId);
                    if (updatedTechIndex !== -1) {
                        allTechnologies[updatedTechIndex].name = newName;
                        allTechnologies[updatedTechIndex].group_id = newGroupId;
                        allTechnologies[updatedTechIndex].parent_id = newParentId;
                    }
                    await fetchAllTechnologies(); // This should refresh allTechnologies
                    await fetchAllTasksForMapping();
                    if (selectedTechnician) {
                        await fetchMappings(selectedTechnician);
                    }
                } else {
                    throw new Error(result.message || `Server error ${response.status}`);
                }
            } catch (error) {
                displayMessage(`Error updating technology: ${error.message}`, 'error');
                techListItem.innerHTML = originalContent; // Revert on error
            }
        }
    });

    techListItem.querySelector('.cancel-edit-tech-btn').addEventListener('click', () => {
        fetchAllTechnologies(); // Re-render all technologies to restore event listeners
    });
}

async function deleteTechnology(techId) {
    const techToDelete = allTechnologies.find(t => t.id === techId);
    let techName = techToDelete ? techToDelete.name : "this technology";

    // Clean up techName for display: replace literal \\\\" with "
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
            await fetchAllTasksForMapping();
            if (selectedTechnician) { // If a technician is selected, refresh their details
                await fetchMappings(selectedTechnician);
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
            groupDiv.dataset.groupId = group.id;
            const nameSpan = document.createElement('span');
            nameSpan.textContent = escapeHtml(group.name);
            groupDiv.appendChild(nameSpan);

            const actionsDiv = document.createElement('div');
            actionsDiv.classList.add('list-item-actions');
            const editBtn = document.createElement('button');
            editBtn.textContent = 'Edit';
            editBtn.classList.add('btn', 'btn-warning', 'btn-sm');
            editBtn.onclick = (e) => {
                e.stopPropagation();
                editTechnologyGroup(group.id, group.name);
            };
            actionsDiv.appendChild(editBtn);
            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('btn', 'btn-danger', 'btn-sm');
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
        // console.error(error);
    }
}

async function editTechnologyGroup(groupId, currentName) {
    const groupListItem = technologyGroupListContainerDiv.querySelector(`.list-item[data-group-id="${groupId}"]`);
    if (!groupListItem) {
        console.error(`Could not find list item for group ID ${groupId}`);
        return;
    }

    const originalContent = groupListItem.innerHTML;

    groupListItem.innerHTML = `
        <input type="text" name="groupName" class="form-control" value="${escapeHtml(currentName)}" style="flex-grow: 1;"/>
        <div class="item-actions">
            <button class="btn btn-success btn-sm save-group-btn">💾 Save</button>
            <button class="btn btn-secondary btn-sm cancel-edit-group-btn">❌ Cancel</button>
        </div>
    `;

    groupListItem.querySelector('.save-group-btn').addEventListener('click', async () => {
        const newName = groupListItem.querySelector('input').value.trim();
        if (newName && newName !== currentName) {
            try {
                const response = await fetch(`/api/technology_groups/${groupId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName })
                });
                const result = await response.json();
                if (response.ok) {
                    displayMessage(`Group updated to '${escapeHtml(newName)}'.`, 'success');
                    await fetchTechnologyGroups(); // Refetch all groups and re-render
                    await fetchAllTechnologies(); // Also refresh technologies as their group names might have changed
                } else {
                    throw new Error(result.message || `Server error ${response.status}`);
                }
            } catch (error) {
                displayMessage(`Error updating group: ${error.message}`, 'error');
                groupListItem.innerHTML = originalContent; // Revert on error
            }
        } else {
            groupListItem.innerHTML = originalContent; // Revert if name is unchanged or empty
        }
    });

    groupListItem.querySelector('.cancel-edit-group-btn').addEventListener('click', () => {
        fetchTechnologyGroups(); // Re-render all groups to restore event listeners
    });
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
