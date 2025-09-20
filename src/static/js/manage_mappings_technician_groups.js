document.addEventListener('DOMContentLoaded', function () {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Technician Groups UI Elements
    const technicianGroupForm = document.getElementById('technicianGroupForm');
    const newTechnicianGroupNameInput = document.getElementById('newTechnicianGroupName');
    const technicianGroupListContainer = document.getElementById('technicianGroupListContainer');

    // Group Membership UI Elements
    const groupMembershipSelect = document.getElementById('groupMembershipSelect');
    const groupMembershipDetails = document.getElementById('groupMembershipDetails');
    const availableTechniciansList = document.getElementById('availableTechniciansList');
    const groupMembersList = document.getElementById('groupMembersList');
    const addTechnicianToGroupBtn = document.getElementById('addTechnicianToGroupBtn');
    const removeTechnicianFromGroupBtn = document.getElementById('removeTechnicianFromGroupBtn');
    const selectedGroupNameSpan = document.getElementById('selectedGroupName');
    const availableTechniciansSearch = document.getElementById('availableTechniciansSearch');
    const groupMembersSearch = document.getElementById('groupMembersSearch');
    const availableTechniciansCount = document.getElementById('availableTechniciansCount');
    const groupMembersCount = document.getElementById('groupMembersCount');

    let allTechnicians = [];
    let allGroups = [];

    function fetchAllTechnicians() {
        fetch('/api/get_technician_mappings')
            .then(response => response.json())
            .then(data => {
                allTechnicians = Object.entries(data.technicians).map(([name, techData]) => ({ id: techData.id, name: name }));
            })
            .catch(error => console.error('Error fetching technicians:', error));
    }

    function fetchTechnicianGroups() {
        fetch('/api/technician_groups') // Corrected endpoint
            .then(response => response.json())
            .then(data => {
                allGroups = data;
                renderTechnicianGroups(allGroups);
                populateGroupMembershipSelect(allGroups);
            })
            .catch(error => console.error('Error fetching technician groups:', error));
    }

    function renderTechnicianGroups(groups) {
        technicianGroupListContainer.innerHTML = '';
        if (groups.length === 0) {
            technicianGroupListContainer.innerHTML = '<p>No technician groups found.</p>';
            return;
        }
        groups.forEach(group => {
            const groupElement = document.createElement('div');
            groupElement.className = 'list-item';
            groupElement.innerHTML = `
                <span class="group-name">${group.name}</span>
                <div class="item-actions">
                    <button class="btn btn-warning btn-sm edit-group-btn" data-group-id="${group.id}" data-group-name="${group.name}">✏️ Edit</button>
                    <button class="btn btn-danger btn-sm delete-group-btn" data-group-id="${group.id}">🗑️ Delete</button>
                </div>
            `;
            technicianGroupListContainer.appendChild(groupElement);
        });
    }

    function populateGroupMembershipSelect(groups) {
        groupMembershipSelect.innerHTML = '<option value="">Choose a group...</option>';
        groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            groupMembershipSelect.appendChild(option);
        });
    }

    technicianGroupForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const groupName = newTechnicianGroupNameInput.value.trim();
        if (!groupName) return;

        fetch('/api/technician_groups', { // Corrected endpoint
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ name: groupName })
        })
        .then(response => response.json().then(result => ({ response, result })))
        .then(({ response, result }) => {
            if (response.ok) {
                if (result.id) {
                    newTechnicianGroupNameInput.value = '';
                    fetchTechnicianGroups();
                    window.displayMessage(`Group '${result.name}' created successfully.`, 'success');
                } else {
                    // This case might indicate a successful response but unexpected data structure
                    window.displayMessage(result.message || 'Error creating group: Unexpected response.', 'error');
                }
            } else {
                // Handle HTTP errors (e.g., 409 Conflict)
                window.displayMessage(result.message || `Error creating group: Server error ${response.status}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error creating technician group:', error);
            // This catch block will handle network errors or issues with response.json() itself
            window.displayMessage(`Failed to add technician group. Network error or invalid response.`, 'error');
        });
    });

    technicianGroupListContainer.addEventListener('click', function (e) {
        const editBtn = e.target.closest('.edit-group-btn');
        const deleteBtn = e.target.closest('.delete-group-btn');
        const saveBtn = e.target.closest('.save-group-btn');
        const cancelBtn = e.target.closest('.cancel-edit-group-btn');

        if (editBtn) {
            const groupId = editBtn.dataset.groupId;
            const groupName = editBtn.dataset.groupName;
            const groupElement = editBtn.closest('.list-item');

            groupElement.innerHTML = `
                <input type="text" class="form-control" value="${groupName}" style="flex-grow: 1;"/>
                <div class="item-actions">
                    <button class="btn btn-success btn-sm save-group-btn" data-group-id="${groupId}">💾 Save</button>
                    <button class="btn btn-secondary btn-sm cancel-edit-group-btn">❌ Cancel</button>
                </div>
            `;
        } else if (deleteBtn) {
            const groupId = deleteBtn.dataset.groupId;
            if (!groupId) {
                alert('Could not find group ID. Cannot delete.');
                return;
            }
            if (confirm('Are you sure you want to delete this group?')) {
                fetch(`/api/technician_groups/${groupId}`, { // Corrected endpoint
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => {
                    if (response.ok) {
                        fetchTechnicianGroups();
                        groupMembershipSelect.value = '';
                        groupMembershipDetails.style.display = 'none';
                    } else {
                        response.json().then(data => alert(data.message || 'Error deleting group'));
                    }
                })
                .catch(error => console.error('Error deleting technician group:', error));
            }
        } else if (saveBtn) {
            const groupId = saveBtn.dataset.groupId;
            if (!groupId) {
                alert('Could not find group ID. Cannot save.');
                return;
            }
            const input = saveBtn.closest('.list-item').querySelector('input');
            const newName = input.value.trim();

            if (newName) {
                fetch(`/api/technician_groups/${groupId}`, { // Corrected endpoint
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ name: newName })
                })
                .then(response => {
                    if (response.ok) {
                        fetchTechnicianGroups();
                    } else {
                        response.json().then(data => alert(data.message || 'Error updating group'));
                    }
                })
                .catch(error => console.error('Error updating technician group:', error));
            }
        } else if (cancelBtn) {
            fetchTechnicianGroups();
        }
    });

    groupMembershipSelect.addEventListener('change', function () {
        const groupId = this.value;
        if (groupId) {
            selectedGroupNameSpan.textContent = this.options[this.selectedIndex].text;
            groupMembershipDetails.style.display = 'block';
            loadGroupMembers(groupId);
        } else {
            groupMembershipDetails.style.display = 'none';
        }
    });

    function loadGroupMembers(groupId) {
        fetch(`/api/technician_groups/${groupId}/members`) // Corrected endpoint
            .then(response => response.json())
            .then(members => {
                const memberIds = new Set(members.map(m => m.id));
                const availableTechnicians = allTechnicians.filter(t => !memberIds.has(t.id));
                
                renderMembershipLists(availableTechnicians, members);
            })
            .catch(error => console.error(`Error fetching members for group ${groupId}:`, error));
    }

    function renderMembershipLists(available, members) {
        renderList(availableTechniciansList, available, availableTechniciansSearch.value, availableTechniciansCount);
        renderList(groupMembersList, members, groupMembersSearch.value, groupMembersCount);
        updateButtonStates();
    }

    function renderList(listElement, items, filter, countElement) {
        listElement.innerHTML = '';
        const safeFilter = (filter || '').toLowerCase();
        if (!items) {
            countElement.textContent = '(0)';
            return;
        }
        let count = 0;
        for (const item of items) {
            if (item && item.name && typeof item.name === 'string') {
                if (item.name.toLowerCase().includes(safeFilter)) {
                    const card = document.createElement('div');
                    card.className = 'technician-card';
                    card.dataset.id = item.id;
                    card.innerHTML = `
                        <span class="user-icon">👨‍🔧</span>
                        <span>${item.name}</span>
                    `;
                    listElement.appendChild(card);
                    count++;
                }
            }
        }
        countElement.textContent = `(${count})`
    }

    function updateButtonStates() {
        const selectedAvailable = availableTechniciansList.querySelectorAll('.technician-card.selected').length > 0;
        addTechnicianToGroupBtn.disabled = !selectedAvailable;

        const selectedMembers = groupMembersList.querySelectorAll('.technician-card.selected').length > 0;
        removeTechnicianFromGroupBtn.disabled = !selectedMembers;
    }

    availableTechniciansSearch.addEventListener('input', () => {
        const groupId = groupMembershipSelect.value;
        if (groupId) loadGroupMembers(groupId);
    });

    groupMembersSearch.addEventListener('input', () => {
        const groupId = groupMembershipSelect.value;
        if (groupId) loadGroupMembers(groupId);
    });

    addTechnicianToGroupBtn.addEventListener('click', () => moveTechnicians(availableTechniciansList, true));
    removeTechnicianFromGroupBtn.addEventListener('click', () => moveTechnicians(groupMembersList, false));

    function moveTechnicians(sourceList, isAdding) {
        const groupId = groupMembershipSelect.value;
        if (!groupId) return;

        const selectedItems = Array.from(sourceList.querySelectorAll('div.technician-card.selected'));
        if (selectedItems.length === 0) return;

        const technicianIds = selectedItems.map(card => card.dataset.id);

        const promises = technicianIds.map(technicianId => {
            return fetch('/api/technician_groups/members', { // Corrected endpoint
                method: isAdding ? 'POST' : 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ technician_id: technicianId, group_id: groupId })
            });
        });

        Promise.all(promises).then(() => {
            loadGroupMembers(groupId);
        });
    }

    [availableTechniciansList, groupMembersList].forEach(list => {
        list.addEventListener('click', e => {
            const card = e.target.closest('.technician-card');
            if (card) {
                card.classList.toggle('selected');
                updateButtonStates();
            }
        });
    });

    // Initial data load
    fetchAllTechnicians();
    fetchTechnicianGroups();
});
