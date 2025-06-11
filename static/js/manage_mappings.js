let currentMappings = {};
let selectedTechnician = null;
let unsavedChanges = false;
let changesSummary = new Set();

let allTechnologies = [];
let allTechnologyGroups = [];
let allSpecialities = [];
let currentSelectedTechnicianId = null;

// DOM Element references
const technicianSelect = document.getElementById('technicianSelect');
const currentTechNameDisplay = document.getElementById('currentTechName');
const techSattelitePointInput = document.getElementById('techSattelitePoint');
const techLinesInput = document.getElementById('techLines');
const taskListDiv = document.getElementById('taskList');
const addTaskBtn = document.getElementById('addTaskBtn');
const saveChangesBtn = document.getElementById('saveChangesBtn');
const statusMessageDiv = document.getElementById('statusMessage');
const backToDashboardBtn = document.getElementById('backToDashboardBtn');

const technologyListContainerDiv = document.getElementById('technologyListContainer');
const newTechnologyNameInput = document.getElementById('newTechnologyName');
const addTechnologyBtn = document.getElementById('addTechnologyBtn');
const technicianSkillsListContainerDiv = document.getElementById('technicianSkillsListContainer');

const technologyGroupListContainerDiv = document.getElementById('technologyGroupListContainer');
const newTechnologyGroupNameInput = document.getElementById('newTechnologyGroupName');
const addTechnologyGroupBtn = document.getElementById('addTechnologyGroupBtn');
const newTechnologyGroupSelect = document.getElementById('newTechnologyGroupSelect');
const newTechnologyParentSelect = document.getElementById('newTechnologyParentSelect');

const specialityListContainerDiv = document.getElementById('specialityListContainer');
const newSpecialityNameInput = document.getElementById('newSpecialityName');
const addSpecialityBtn = document.getElementById('addSpecialityBtn');
const assignSpecialitySelect = document.getElementById('assignSpecialitySelect');
const assignSpecialityBtn = document.getElementById('assignSpecialityBtn');
const technicianSpecialitiesContainerDiv = document.getElementById('technicianSpecialitiesContainer');

// New DOM element for Task-Technology Mappings
const taskTechnologyMappingListContainerDiv = document.getElementById('taskTechnologyMappingListContainer');

function escapeHtml(unsafe) {
    if (unsafe === null || typeof unsafe === 'undefined') return '';
    return String(unsafe).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function displayMessage(message, type = 'info') {
    statusMessageDiv.textContent = message;
    statusMessageDiv.className = type; // Applies .success, .error, or .info
    setTimeout(() => {
        statusMessageDiv.textContent = '';
        statusMessageDiv.className = '';
    }, 5000);
}

function recordChange(description) {
    unsavedChanges = true;
    changesSummary.add(description);
    // console.log("Change recorded:", description); // For debugging
}

function clearUnsavedChanges() {
    unsavedChanges = false;
    changesSummary.clear();
    // console.log("Unsaved changes cleared."); // For debugging
}

function calculateAndAssignDisplayPriorities(tasksArrayToProcess) {
    if (!tasksArrayToProcess || tasksArrayToProcess.length === 0) return;
    let currentDisplayPrioValue = 0;
    let previousUserPrioForGrouping = -Infinity;
    tasksArrayToProcess.forEach(task => {
        if (task.user_prio !== previousUserPrioForGrouping) {
            currentDisplayPrioValue++;
        }
        task.display_prio = currentDisplayPrioValue;
        previousUserPrioForGrouping = task.user_prio;
    });
}

function sortAndRecalculatePriorities(tasksArray) {
    if (!tasksArray) return;
    tasksArray.forEach((task, index) => {
        if (typeof task.user_prio === 'undefined' || task.user_prio === null) {
            task.user_prio = (task.prio !== undefined && task.prio !== null) ? task.prio : index + 1000;
        }
    });
    tasksArray.sort((a, b) => {
        const prioA = a.user_prio;
        const prioB = b.user_prio;
        if (prioA === prioB) return (a.task || "").localeCompare(b.task || "");
        return prioA - prioB;
    });
    calculateAndAssignDisplayPriorities(tasksArray);
}

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
            option.textContent = `${ '  '.repeat(level) }↳ ${ escapeHtml(tech.name) }`;
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
            nameSpan.textContent = escapeHtml(group.name); // Removed (ID: X)
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
    // Attempt to restore previous selection if still valid
    if (Array.from(newTechnologyGroupSelect.options).some(opt => opt.value === previousGroupValue)) {
        newTechnologyGroupSelect.value = previousGroupValue;
    }
    // Manually trigger change if a group is selected to populate parents correctly
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
            fetchAllTechnologies(); // Refresh tech list too
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
            fetchTechnologyGroups(); // Refresh the list of groups
            fetchAllTechnologies(); // Also refresh technologies as group names might be displayed there
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating technology group: ${error.message}`, 'error');
        console.error(error);
    }
}

async function deleteTechnologyGroup(groupId) {
    if (!confirm(`Are you sure you want to delete technology group ID ${groupId}? This might affect associated technologies.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/technology_groups/${groupId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Technology group ID ${groupId} deleted.`, 'success');
            fetchTechnologyGroups(); // Refresh the list of groups
            fetchAllTechnologies(); // Also refresh technologies
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting technology group: ${error.message}`, 'error');
        console.error(error);
    }
}

// --- Speciality Management ---
async function fetchSpecialities() {
    try {
        const response = await fetch('/api/specialities');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        allSpecialities = await response.json();
        renderSpecialities();
    } catch (error) {
        displayMessage(`Error fetching specialities: ${error.message}`, 'error');
        console.error(error);
    }
}

function renderSpecialities() {
    specialityListContainerDiv.innerHTML = '';
    assignSpecialitySelect.innerHTML = '<option value="">Select speciality to add</option>';
    if (allSpecialities.length === 0) {
        specialityListContainerDiv.innerHTML = '<p>No specialities defined.</p>';
    } else {
        allSpecialities.sort((a, b) => a.name.localeCompare(b.name)).forEach(spec => {
            const specDiv = document.createElement('div');
            specDiv.classList.add('list-item');
            const nameSpan = document.createElement('span');
            nameSpan.textContent = escapeHtml(spec.name); // Removed (ID: X)
            specDiv.appendChild(nameSpan);

            const actionsDiv = document.createElement('div');
            actionsDiv.classList.add('list-item-actions');
            const editBtn = document.createElement('button');
            editBtn.textContent = 'Edit';
            editBtn.classList.add('edit-btn');
            editBtn.onclick = (e) => {
                e.stopPropagation();
                editSpeciality(spec.id, spec.name);
            };
            actionsDiv.appendChild(editBtn);
            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('delete-btn');
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteSpeciality(spec.id);
            };
            actionsDiv.appendChild(deleteBtn);
            specDiv.appendChild(actionsDiv);
            specialityListContainerDiv.appendChild(specDiv);

            const option = document.createElement('option');
            option.value = spec.id;
            option.textContent = escapeHtml(spec.name);
            assignSpecialitySelect.appendChild(option);
        });
    }
}

async function addNewSpeciality() {
    const specName = newSpecialityNameInput.value.trim();
    if (!specName) {
        displayMessage('Speciality name empty.', 'error');
        return;
    }
    try {
        const response = await fetch('/api/specialities', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: specName}),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Speciality '${escapeHtml(result.name)}' added.`, 'success');
            newSpecialityNameInput.value = '';
            fetchSpecialities();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error adding speciality: ${error.message}`, 'error');
        console.error(error);
    }
}

async function editSpeciality(specialityId, currentName) {
    const newName = prompt("Enter the new name for the speciality:", currentName);
    if (newName === null || newName.trim() === "") {
        displayMessage("Edit cancelled or name empty.", "info");
        return;
    }
    try {
        const response = await fetch(`/api/specialities/${specialityId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName.trim()})
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Speciality '${escapeHtml(result.name)}' updated.`, 'success');
            fetchSpecialities(); // Refresh the list of specialities
            // If a technician is selected and their specialities are displayed, refresh that too
            if (selectedTechnician && currentMappings.technicians[selectedTechnician]) {
                fetchMappings(selectedTechnician); // This re-fetches all mappings including technician specialities
            }
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating speciality: ${error.message}`, 'error');
        console.error(error);
    }
}

async function deleteSpeciality(specialityId) {
    if (!confirm(`Are you sure you want to delete speciality ID ${specialityId}? This might affect assigned technician specialities.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/specialities/${specialityId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Speciality ID ${specialityId} deleted.`, 'success');
            fetchSpecialities(); // Refresh the list of specialities
            // If a technician is selected and their specialities are displayed, refresh that too
            if (selectedTechnician && currentMappings.technicians[selectedTechnician]) {
                fetchMappings(selectedTechnician);
            }
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error deleting speciality: ${error.message}`, 'error');
        console.error(error);
    }
}


// --- Technology Management (Edit and Delete stubs) ---
async function editTechnology(techId, currentName, currentGroupId, currentParentId) {
    const newName = prompt("Enter the new name for the technology:", currentName);
    if (newName === null || newName.trim() === "") {
        displayMessage("Edit cancelled or name empty.", "info");
        return;
    }

    // For simplicity, this example only updates the name.
    // A more complete implementation would involve selects for group and parent, similar to the add form.
    // For now, we'll keep the group and parent the same unless explicitly changed via a more complex UI.
    // This prompt is just for the name. Group/parent changes would need more UI elements.

    const payload = {
        name: newName.trim(),
        group_id: currentGroupId, // Assuming currentGroupId is passed correctly
        parent_id: currentParentId // Assuming currentParentId is passed correctly
    };
    // Potentially, you could add more prompts here for group_id and parent_id
    // or build a small modal/form for editing.

    try {
        const response = await fetch(`/api/technologies/${techId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Technology '${escapeHtml(result.name)}' updated.`, 'success');
            await fetchAllTechnologies(); // Refresh the list of technologies
            fetchAllTasksForMapping(); // Refresh task mappings
            // Potentially refresh technician skills if they are displayed and might be affected
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
    if (!confirm(`Are you sure you want to delete technology ID ${techId}? This may affect child technologies, task mappings, and technician skills.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/technologies/${techId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || `Technology ID ${techId} deleted.`, 'success');
            await fetchAllTechnologies(); // Refresh the list of technologies
            fetchAllTasksForMapping(); // Refresh task mappings as a technology might have been removed
            // Potentially refresh technician skills
            if (selectedTechnician) {
                // Re-fetch skills for the current technician as one they had might be deleted
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

// --- Technician Skill Management ---
async function fetchTechnicianSkills(technicianName) {
    if (!technicianName || !currentSelectedTechnicianId) {
        renderTechnicianSkills();
        return;
    }
    try {
        const response = await fetch(`/api/technician_skills/${currentSelectedTechnicianId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const skillsData = await response.json();
        currentMappings.technicians[technicianName].skills = skillsData.skills || {};
        renderTechnicianSkills();
    } catch (error) {
        displayMessage(`Error fetching skills for ${technicianName}: ${error.message}`, 'error');
        console.error('Error fetching skills:', error);
        if (currentMappings.technicians && currentMappings.technicians[technicianName]) {
            currentMappings.technicians[technicianName].skills = {};
        }
        renderTechnicianSkills();
    }
}

function renderTechnicianSkills() {
    technicianSkillsListContainerDiv.innerHTML = '';
    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        technicianSkillsListContainerDiv.innerHTML = '<p>Select technician to view skills.</p>';
        return;
    }
    if (allTechnologies.length === 0) {
        technicianSkillsListContainerDiv.innerHTML = '<p>No technologies defined. Skills cannot be assigned.</p>';
        return;
    }
    const techSkills = currentMappings.technicians[selectedTechnician].skills || {};

    // Helper to check if a technology has children in the allTechnologies list
    const hasChildren = (technologyId) => {
        return allTechnologies.some(tech => tech.parent_id === technologyId);
    };

    // Recursive function to render child skill items
    function renderSkillItemsRecursive(parentElement, parentTechnologyId, level) {
        const childrenOfParent = allTechnologies.filter(tech => tech.parent_id === parentTechnologyId);
        childrenOfParent.sort((a, b) => a.name.localeCompare(b.name));

        childrenOfParent.forEach(childTech => {
            const skillDiv = document.createElement('div');
            skillDiv.classList.add('skill-item');
            skillDiv.style.marginLeft = `${level * 25}px`; // 25px indentation per level

            const skillLabel = document.createElement('label');
            skillLabel.className = 'skill-label';
            skillLabel.textContent = escapeHtml(childTech.name);
            skillLabel.setAttribute('for', `skill-${childTech.id}-select`); // Set for even if select might not be there
            skillDiv.appendChild(skillLabel);

            // Only add skill select if this childTech is a leaf node (has no children itself)
            if (!hasChildren(childTech.id)) {
                const skillSelect = document.createElement('select');
                skillSelect.id = `skill-${childTech.id}-select`;
                skillSelect.dataset.technologyId = childTech.id;
                ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"].forEach((lvlText, idx) => {
                    const option = document.createElement('option');
                    option.value = idx;
                    option.textContent = lvlText;
                    if (techSkills[childTech.id] === idx) option.selected = true;
                    skillSelect.appendChild(option);
                });
                skillSelect.addEventListener('change', async (e) => {
                    await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, parseInt(e.target.dataset.technologyId), parseInt(e.target.value));
                });
                skillDiv.appendChild(skillSelect);
            }
            parentElement.appendChild(skillDiv);

            // If this childTech is also a parent, recurse for its children
            if (hasChildren(childTech.id)) {
                renderSkillItemsRecursive(parentElement, childTech.id, level + 1);
            }
        });
    }

    // Process top-level technologies (those with no parent_id)
    const topLevelTechnologies = allTechnologies.filter(tech => tech.parent_id === null);
    topLevelTechnologies.sort((a, b) => {
        const groupCompare = (a.group_name || 'ZZZ_Uncategorized').localeCompare(b.group_name || 'ZZZ_Uncategorized');
        if (groupCompare !== 0) return groupCompare;
        return a.name.localeCompare(b.name);
    });

    let currentGroupName = null;
    topLevelTechnologies.forEach(topLevelTech => {
        // Render group header if it changes
        if (topLevelTech.group_name !== currentGroupName) {
            const groupHeader = document.createElement('h4');
            groupHeader.textContent = escapeHtml(topLevelTech.group_name || 'Uncategorized');
            // groupHeader.style.marginTop = '15px'; // Handled by class
            // groupHeader.style.marginBottom = '5px'; // Handled by class
            // groupHeader.style.fontWeight = 'bold'; // Handled by class
            groupHeader.classList.add('skill-group-header'); // Use new class for styling
            technicianSkillsListContainerDiv.appendChild(groupHeader);
            currentGroupName = topLevelTech.group_name;
        }

        const skillDiv = document.createElement('div');
        skillDiv.classList.add('skill-item');
        skillDiv.style.marginLeft = '0px'; // Top-level items have no additional margin beyond group

        const skillLabel = document.createElement('label');
        skillLabel.className = 'skill-label';
        skillLabel.textContent = escapeHtml(topLevelTech.name);
        skillLabel.setAttribute('for', `skill-${topLevelTech.id}-select`);
        skillDiv.appendChild(skillLabel);

        // If top-level tech is a leaf node (no children), add skill select
        if (!hasChildren(topLevelTech.id)) {
            const skillSelect = document.createElement('select');
            skillSelect.id = `skill-${topLevelTech.id}-select`;
            skillSelect.dataset.technologyId = topLevelTech.id;
            ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"].forEach((lvlText, idx) => {
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = lvlText;
                if (techSkills[topLevelTech.id] === idx) option.selected = true;
                skillSelect.appendChild(option);
            });
            skillSelect.addEventListener('change', async (e) => {
                await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, parseInt(e.target.dataset.technologyId), parseInt(e.target.value));
            });
            skillDiv.appendChild(skillSelect);
        }
        technicianSkillsListContainerDiv.appendChild(skillDiv);

        // If top-level tech is a parent, render its children recursively
        if (hasChildren(topLevelTech.id)) {
            renderSkillItemsRecursive(technicianSkillsListContainerDiv, topLevelTech.id, 1); // Children start at level 1 indentation
        }
    });
}

async function updateTechnicianSkill(technicianName, technicianId, technologyId, skillLevel) {
    if (!technicianName || typeof technicianId === 'undefined') {
        displayMessage('Technician not selected for skill update.', 'error');
        return;
    }
    try {
        const response = await fetch('/api/technician_skill', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({technician_id: technicianId, technology_id: technologyId, skill_level: skillLevel}),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Skill for tech ID ${technologyId} updated.`, 'success');
            if (!currentMappings.technicians[selectedTechnician].skills) currentMappings.technicians[selectedTechnician].skills = {};
            currentMappings.technicians[selectedTechnician].skills[technologyId] = skillLevel;
            recordChange(`Skill for ${escapeHtml(technicianName)} on tech ID ${technologyId} changed to ${skillLevel}`);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating skill: ${error.message}`, 'error');
        console.error(error);
        await fetchTechnicianSkills(selectedTechnician); // Revert UI
    }
}

// --- Technician Speciality Management (Assignment) ---
function renderTechnicianSpecialities(technicianData) {
    technicianSpecialitiesContainerDiv.innerHTML = '';
    const currentSpecialities = technicianData.specialities || [];
    if (currentSpecialities.length === 0) {
        technicianSpecialitiesContainerDiv.innerHTML = '<p>No specialities assigned.</p>';
    } else {
        currentSpecialities.forEach(spec => {
            const specDiv = document.createElement('div');
            specDiv.classList.add('list-item');
            specDiv.innerHTML = `<span>${escapeHtml(spec.name)}</span>`; // Removed (ID: X)
            const removeBtn = document.createElement('button');
            removeBtn.textContent = 'Remove';
            removeBtn.classList.add('delete-btn'); // Use delete-btn style
            removeBtn.style.marginLeft = '10px';
            removeBtn.onclick = () => removeSpecialityFromSelectedTechnician(spec.id);
            specDiv.appendChild(removeBtn);
            technicianSpecialitiesContainerDiv.appendChild(specDiv);
        });
    }
}

async function assignSpecialityToSelectedTechnician() {
    if (!selectedTechnician || !currentSelectedTechnicianId) {
        displayMessage('Select technician.', 'error');
        return;
    }
    const specialityId = assignSpecialitySelect.value;
    if (!specialityId) {
        displayMessage('Select speciality to add.', 'error');
        return;
    }
    try {
        const response = await fetch(`/api/technicians/${currentSelectedTechnicianId}/specialities`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({speciality_id: parseInt(specialityId)})
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || 'Speciality assigned.', 'success');
            recordChange(`Assigned speciality ID ${specialityId} to ${selectedTechnician}`);
            fetchMappings(selectedTechnician); // Re-fetch to update list
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error assigning speciality: ${error.message}`, 'error');
        console.error(error);
    }
}

async function removeSpecialityFromSelectedTechnician(specialityId) {
    if (!selectedTechnician || !currentSelectedTechnicianId) {
        displayMessage('Select technician.', 'error');
        return;
    }
    if (!confirm(`Remove speciality ID ${specialityId} from ${selectedTechnician}?`)) return;
    try {
        const response = await fetch(`/api/technicians/${currentSelectedTechnicianId}/specialities/${specialityId}`, {method: 'DELETE'});
        const result = await response.json();
        if (response.ok) {
            displayMessage(result.message || 'Speciality removed.', 'success');
            recordChange(`Removed speciality ID ${specialityId} from ${selectedTechnician}`);
            fetchMappings(selectedTechnician);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error removing speciality: ${error.message}`, 'error');
        console.error(error);
    }
}

// --- Task-Technology Mapping Functions ---
async function fetchAllTasksForMapping() {
    if (allTechnologies.length === 0) {
        console.warn("fetchAllTasksForMapping: allTechnologies is empty. Retrying in 1.5s. Ensure fetchAllTechnologies completes successfully first.");
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>Waiting for technologies to load before fetching task mappings...</p>';
        setTimeout(fetchAllTasksForMapping, 1500); // Retry with a slightly longer delay
        return; // Crucial: stop this execution path if retrying
    }
    try {
        const response = await fetch('/api/tasks_for_mapping');
        if (!response.ok) {
            const errorText = await response.text(); // Attempt to get more error details from server response
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
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>No tasks found to map.</p>';
        return;
    }

    if (allTechnologies.length === 0) {
        taskTechnologyMappingListContainerDiv.innerHTML = '<p>Technologies not loaded yet. Cannot map tasks.</p>';
        return;
    }

    tasks.sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    // Helper to check if a technology has children
    const hasChildren = (technologyId) => {
        return allTechnologies.some(t => t.parent_id === technologyId);
    };

    // Prepare technologies for hierarchical display in select
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

    tasks.forEach(task => {
        const itemDiv = document.createElement('div');
        itemDiv.classList.add('list-item'); // Re-use list-item style

        const taskNameSpan = document.createElement('span');
        taskNameSpan.textContent = escapeHtml(task.name); // Removed (ID: X)
        itemDiv.appendChild(taskNameSpan);

        const techSelect = document.createElement('select');
        techSelect.dataset.taskId = task.id;
        techSelect.style.width = '350px'; // Consistent width for the select bar, aligned right by flex parent

        const noTechOption = document.createElement('option');
        noTechOption.value = ""; // Represents NULL or no technology
        noTechOption.textContent = '-- No Technology --';
        techSelect.appendChild(noTechOption);

        // Group technologies by group_name
        const technologiesByGroup = {};
        allTechnologies.forEach(t => {
            const groupName = t.group_name || 'Uncategorized';
            if (!technologiesByGroup[groupName]) {
                technologiesByGroup[groupName] = [];
            }
            technologiesByGroup[groupName].push(t);
        });

        const sortedGroupNames = Object.keys(technologiesByGroup).sort();

        function appendOptionsRecursive(parentElement, technologyId, level, currentTaskTechnologyId) {
            const children = childrenByParentId[technologyId] || [];
            children.forEach(childTech => {
                const option = document.createElement('option');
                option.value = childTech.id;
                option.textContent = `${'  '.repeat(level)}↳ ${escapeHtml(childTech.name)}`;
                if (currentTaskTechnologyId === childTech.id) {
                    option.selected = true;
                }
                if (hasChildren(childTech.id)) {
                    option.disabled = true;
                    option.textContent += " (Parent)";
                }
                parentElement.appendChild(option);
                appendOptionsRecursive(parentElement, childTech.id, level + 1, currentTaskTechnologyId);
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
                option.textContent = escapeHtml(tech.name); // Top-level in group, no indent needed beyond optgroup
                if (task.technology_id === tech.id) {
                    option.selected = true;
                }
                if (hasChildren(tech.id)) {
                    option.disabled = true;
                    option.textContent += " (Parent)";
                }
                optgroup.appendChild(option);
                // Append children recursively
                appendOptionsRecursive(optgroup, tech.id, 1, task.technology_id);
            });
            techSelect.appendChild(optgroup);
        });


        techSelect.addEventListener('change', async (e) => {
            const selectedTechnologyId = e.target.value ? parseInt(e.target.value) : null;
            await updateTaskTechnologyMapping(task.id, selectedTechnologyId);
        });

        itemDiv.appendChild(techSelect);
        taskTechnologyMappingListContainerDiv.appendChild(itemDiv);
    });
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
            // Optionally, record change or refresh specific data if needed
            // For example, find the task in a local cache and update its technology_id
            // recordChange(`Technology for task ID ${taskId} updated to ${technologyId === null ? 'none' : `ID ${technologyId}`}`);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating task technology: ${error.message}`, 'error');
        console.error('Error in updateTaskTechnologyMapping:', error);
        // Optionally, re-fetch task mappings to revert UI if the update failed
        // await fetchAllTasksForMapping();
    }
}

// --- Technician Data Fetching and UI Population ---
async function fetchMappings(technicianNameToSelect = null) {
    try {
        const response = await fetch('/api/get_technician_mappings');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        currentMappings = data; // Store all mappings, should be like {"technicians": {"name": {id: ..., details...}}}

        // Populate technicianSelect dropdown
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
            // Ensure loadTechnicianDetails is defined and handles UI updates correctly
            if (typeof loadTechnicianDetails === 'function') {
                await loadTechnicianDetails(finalTechnicianToLoad);
            } else {
                console.error('loadTechnicianDetails function is not defined. Cannot refresh technician view.');
                displayMessage('Error: UI refresh function missing.', 'error');
            }
        } else {
            // If no specific tech to select, or previous selection is gone/invalid, clear details
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
        // displayMessage('Technician data loaded.', 'info'); // Optional
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
        selectedTechnician = null; // Reset if data is missing
        currentSelectedTechnicianId = null;
        document.getElementById('technicianDetails').style.display = 'none';
        return;
    }

    currentSelectedTechnicianId = techData.id; // Store the ID

    if (currentTechNameDisplay) currentTechNameDisplay.textContent = `Details for: ${escapeHtml(selectedTechnician)}`;
    if (techSattelitePointInput) techSattelitePointInput.value = techData.sattelite_point || '';
    if (techLinesInput) techLinesInput.value = (techData.technician_lines || []).join(', ');

    document.getElementById('technicianDetails').style.display = 'block';

    // Render Task Assignments
    taskListDiv.innerHTML = '';
    const tasks = techData.task_assignments || [];
    sortAndRecalculatePriorities(tasks); // Sort and assign display_prio

    if (tasks.length === 0) {
        taskListDiv.innerHTML = '<p>No tasks assigned.</p>';
    } else {
        tasks.forEach((task, index) => {
            const taskDiv = document.createElement('div');
            taskDiv.classList.add('task-item'); // Add class for styling
            taskDiv.dataset.taskId = task.id || `task-${index}`; // Use a unique ID

            const taskNameInput = document.createElement('input');
            taskNameInput.type = 'text';
            taskNameInput.classList.add('task-name-input'); // Add class for styling

            if (task.task === "New Task" && String(task.id).startsWith("new_")) {
                taskNameInput.placeholder = "New Task"; // Set "New Task" as placeholder
                taskNameInput.value = ""; // Clear the value for placeholder to show
            } else {
                taskNameInput.value = escapeHtml(task.task);
                taskNameInput.placeholder = 'Task Name'; // Default placeholder for existing tasks
            }

            taskNameInput.addEventListener('change', (e) => {
                task.task = e.target.value;
                recordChange(`Task name changed for ${selectedTechnician}`);
                // No need to re-render all tasks, just update the model
            });

            const displayPrioSpan = document.createElement('span');
            displayPrioSpan.textContent = ` (Display Group: ${task.display_prio || 'N/A'})`;
            displayPrioSpan.style.fontSize = '0.9em';
            displayPrioSpan.style.marginRight = '10px'; // Add some margin to separate from prio input
            displayPrioSpan.style.whiteSpace = 'nowrap'; // Ensure content stays on one line

            const taskPrioInput = document.createElement('input');
            taskPrioInput.type = 'number';
            taskPrioInput.value = task.user_prio; // Use user_prio for editing
            taskPrioInput.min = 1;
            taskPrioInput.classList.add('task-prio-input'); // Add class for styling
            taskPrioInput.addEventListener('change', (e) => {
                const newPrio = parseInt(e.target.value);
                if (!isNaN(newPrio) && newPrio >= 1) {
                    task.user_prio = newPrio;
                    recordChange(`Task priority changed for ${selectedTechnician}`);
                    sortAndRecalculatePriorities(tasks); // Re-sort and re-calculate display_prio
                    loadTechnicianDetails(selectedTechnician); // Re-render tasks to reflect new order
                } else {
                    e.target.value = task.user_prio; // Revert if invalid
                    displayMessage('Priority must be a number >= 1.', 'error');
                }
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('delete-task-btn', 'task-action-btn'); // Add classes for styling
            deleteBtn.onclick = () => {
                if (confirm(`Delete task "${escapeHtml(task.task)}"?`)) {
                    currentMappings.technicians[selectedTechnician].task_assignments = tasks.filter(t => t !== task);
                    recordChange(`Task "${escapeHtml(task.task)}" deleted for ${selectedTechnician}`);
                    loadTechnicianDetails(selectedTechnician); // Re-render
                }
            };

            // PM Link (if applicable, assuming task object might have 'ticket_url' and 'ticket_mo')
            if (task.ticket_url && task.ticket_mo) {
                const pmLink = document.createElement('a');
                pmLink.href = task.ticket_url;
                pmLink.textContent = `PM: ${escapeHtml(task.ticket_mo)}`;
                pmLink.target = '_blank';
                pmLink.classList.add('pm-link'); // Add class for styling
                pmLink.style.marginLeft = '10px';
                taskDiv.appendChild(pmLink);
            }


            taskDiv.appendChild(taskNameInput);
            taskDiv.appendChild(displayPrioSpan); // Moved before taskPrioInput
            taskDiv.appendChild(taskPrioInput);
            taskDiv.appendChild(deleteBtn);
            taskListDiv.appendChild(taskDiv);
        });
    }

    // Render Specialities
    renderTechnicianSpecialities(techData);

    // Fetch and Render Skills (conditionally or always)
    // Check if skills are already loaded or if a fetch is needed
    if (!techData.skills || Object.keys(techData.skills).length === 0) { // Basic check, might need more robust logic
        await fetchTechnicianSkills(selectedTechnician); // This will call renderTechnicianSkills internally on success
    } else {
        renderTechnicianSkills(); // Skills already in currentMappings, just render them
    }
}

// --- Function to Save All Changes ---
async function saveAllChanges() {
    // If unsavedChanges is false, it implies no direct interaction was flagged.
    // However, saveAllChanges might be intended to save the entire current state regardless.
    // For now, we proceed even if unsavedChanges is false, to save the current state of all technicians.

    const payload = {technicians: {}};
    let dataToSaveExists = false;

    // Iterate over all technicians known to the frontend
    for (const techName in currentMappings.technicians) {
        if (currentMappings.technicians.hasOwnProperty(techName)) {
            const techDataFromState = currentMappings.technicians[techName];
            let currentTechPayload = {
                sattelite_point: techDataFromState.sattelite_point, // Default to stored state
                technician_lines: techDataFromState.technician_lines || [], // Default to stored state
                task_assignments: []
            };

            // If this is the currently selected technician, grab values directly from input fields
            // as they are the most current source of truth for the displayed technician.
            if (selectedTechnician === techName) {
                currentTechPayload.sattelite_point = techSattelitePointInput.value.trim();
                const linesStr = techLinesInput.value.trim();
                currentTechPayload.technician_lines = linesStr ? linesStr.split(',').map(l => {
                    const num = parseInt(l.trim());
                    return isNaN(num) ? null : num;
                }).filter(n => n !== null) : [];
            }

            // Task assignments are assumed to be up-to-date in techDataFromState.task_assignments
            // due to direct manipulation in task editing functions.
            if (techDataFromState.task_assignments && Array.isArray(techDataFromState.task_assignments)) {
                currentTechPayload.task_assignments = techDataFromState.task_assignments.map(task => ({
                    task: task.task, // Name of the task
                    prio: task.user_prio // Use user_prio as 'prio' for saving
                })).filter(t => t.task && typeof t.prio === 'number'); // Ensure valid tasks
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
            clearUnsavedChanges(); // Reset the unsaved changes flag and summary
            // Re-fetch mappings to ensure UI consistency, especially if backend modifies data (e.g., new IDs)
            // Pass the currently selected technician name to attempt to re-select them after fetch.
            await fetchMappings(selectedTechnician);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error saving changes: ${error.message}`, 'error');
        console.error('Error in saveAllChanges:', error);
    }
}

// --- Main Initialization Function ---
async function initializePage() {
    // 1. Initial UI State Setup for technology form
    newTechnologyGroupSelect.disabled = true;
    newTechnologyParentSelect.disabled = true;
    newTechnologyParentSelect.innerHTML = '<option value="">No Parent (Top Level)</option>';

    // 2. Event Listeners
    // Global controls
    if (technicianSelect) {
        technicianSelect.addEventListener('change', async (event) => {
            if (unsavedChanges && selectedTechnician) {
                let changesText = Array.from(changesSummary).join('\n- ');
                if (changesText) changesText = `- ${changesText}`; else changesText = "General modifications.";
                if (!confirm(`You have unsaved changes:\n${changesText}\n\nDiscard and switch?`)) {
                    event.target.value = selectedTechnician;
                    return;
                }
            }
            clearUnsavedChanges();
            await loadTechnicianDetails(event.target.value);
        });
    }

    if (addTaskBtn) {
        addTaskBtn.addEventListener('click', () => {
            if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
                displayMessage('Select technician first.', 'error');
                return;
            }
            const tasksArray = currentMappings.technicians[selectedTechnician].task_assignments || [];
            currentMappings.technicians[selectedTechnician].task_assignments = tasksArray;
            let maxUserPrio = 0;
            tasksArray.forEach(t => {
                if (t.user_prio && t.user_prio > maxUserPrio) maxUserPrio = t.user_prio;
            });
            const newTask = {task: "New Task", user_prio: maxUserPrio + 1, id: `new_${Date.now()}`};
            tasksArray.push(newTask);
            recordChange(`New task added for '${selectedTechnician}'`);
            sortAndRecalculatePriorities(tasksArray);
            loadTechnicianDetails(selectedTechnician); // Reload to show new task
        });
    }

    if (saveChangesBtn) {
        saveChangesBtn.addEventListener('click', saveAllChanges);
    }

    if (backToDashboardBtn) {
        backToDashboardBtn.addEventListener('click', (event) => {
            if (unsavedChanges) {
                let changesText = Array.from(changesSummary).join('\n- ');
                if (changesText) changesText = `- ${changesText}`; else changesText = "General modifications.";
                if (!confirm(`Unsaved changes:\n${changesText}\n\nLeave without saving?`)) {
                    event.preventDefault();
                    return;
                }
            }
            window.location.href = "/";
        });
    }

    // Management section "add" buttons
    if (addTechnologyBtn) {
        addTechnologyBtn.addEventListener('click', addNewTechnology);
    }
    if (addTechnologyGroupBtn) {
        addTechnologyGroupBtn.addEventListener('click', addNewTechnologyGroup);
    }
    if (addSpecialityBtn) {
        addSpecialityBtn.addEventListener('click', addNewSpeciality);
    }
    if (assignSpecialityBtn) {
        assignSpecialityBtn.addEventListener('click', assignSpecialityToSelectedTechnician);
    }

    // Tech detail input listeners
    if (techSattelitePointInput) {
        techSattelitePointInput.addEventListener('change', (e) => recordChange(`Sattelite point for '${selectedTechnician}' to '${e.target.value}'`));
    }
    if (techLinesInput) {
        techLinesInput.addEventListener('change', (e) => recordChange(`Lines for '${selectedTechnician}' to '${e.target.value}'`));
    }

    // New technology form enhancements listeners
    if (newTechnologyNameInput) {
        newTechnologyNameInput.addEventListener('input', handleTechnologyNameInputChange);
    }
    if (newTechnologyGroupSelect) {
        newTechnologyGroupSelect.addEventListener('change', handleTechnologyGroupChange);
    }

    // Foldable sections
    document.querySelectorAll('.section-header').forEach(header => {
        const content = header.nextElementSibling;
        const icon = header.querySelector('.toggle-icon');
        if (!content || !icon) return; // Safety check

        // Set initial state based on 'collapsed' class in HTML
        if (content.classList.contains('collapsed')) {
            icon.textContent = '+';
        } else {
            icon.textContent = '-';
        }

        header.addEventListener('click', () => {
            content.classList.toggle('collapsed');
            if (content.classList.contains('collapsed')) {
                icon.textContent = '+';
            } else {
                icon.textContent = '-';
                // Auto-load technician if details section is opened and no tech selected
                if (header.parentElement.id === 'manageTechnicianDetailsSection' && !selectedTechnician && technicianSelect.options.length > 1) {
                    technicianSelect.value = technicianSelect.options[1].value; // Select first actual tech
                    loadTechnicianDetails(technicianSelect.value);
                }
            }
        });
    });

    // Make subsections foldable
    document.querySelectorAll('.subsection-header').forEach(header => {
        const content = header.nextElementSibling;
        const icon = header.querySelector('.toggle-icon');
        if (!content || !icon) return;

        if (content.classList.contains('collapsed')) {
            icon.textContent = '+';
        } else {
            icon.textContent = '-';
        }

        header.addEventListener('click', () => {
            content.classList.toggle('collapsed');
            icon.textContent = content.classList.contains('collapsed') ? '+' : '-';
        });
    });

    // 3. Fetch Initial Data
    await fetchAllInitialData();
}

// --- DOMContentLoaded ---
// This should be the only DOMContentLoaded listener for this script.
document.addEventListener('DOMContentLoaded', () => {
    initializePage().catch(error => {
        console.error("Critical error during page initialization:", error);
        displayMessage("Page failed to load completely. Check console for errors.", "error");
    });
});

function handleTechnologyNameInputChange() {
    const techName = newTechnologyNameInput.value.trim();
    const isDisabled = techName === '';

    newTechnologyGroupSelect.disabled = isDisabled;
    // Parent select's disabled state is also affected by group selection, handled in populateParentTechnologySelectFiltered
    // and handleTechnologyGroupChange. However, if techName is empty, parent should definitely be disabled.
    newTechnologyParentSelect.disabled = isDisabled;

    if (isDisabled) {
        newTechnologyGroupSelect.value = ''; // Reset group selection
        // Manually trigger change on group select to clear/update parent select
        newTechnologyGroupSelect.dispatchEvent(new Event('change'));
    } else {
        // If enabling, and a group is already selected, ensure parent select is correctly populated
        if (newTechnologyGroupSelect.value) {
            populateParentTechnologySelectFiltered(newTechnologyGroupSelect.value);
        } else {
            // If no group selected yet, parent select should be empty or just "No Parent"
            newTechnologyParentSelect.innerHTML = '<option value="">No Parent (Top Level)</option>';
        }
    }
}

function handleTechnologyGroupChange() {
    const selectedGroupId = newTechnologyGroupSelect.value;
    populateParentTechnologySelectFiltered(selectedGroupId);
}

// --- Centralized initial data fetching ---
async function fetchAllInitialData() {
    await fetchTechnologyGroups(); // Fetches groups and populates newTechnologyGroupSelect
    await fetchAllTechnologies();  // Fetches all technologies
    await fetchSpecialities();
    await fetchAllTasksForMapping(); // Depends on technologies
    await fetchMappings(); // Fetches technician data

    // After all data is loaded and initial rendering might have occurred,
    // ensure the dependent dropdowns for new technology are in the correct state.
    // This will check name, and enable/disable group/parent accordingly.
    // If a group was pre-selected by renderTechnologyGroups, handleTechnologyGroupChange (triggered by it)
    // would have already called populateParentTechnologySelectFiltered.
    // Calling this ensures consistency if no group was pre-selected or if name input is empty.
    handleTechnologyNameInputChange();
}
