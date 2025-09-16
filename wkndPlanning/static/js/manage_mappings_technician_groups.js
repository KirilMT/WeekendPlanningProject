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

    // Task Priority UI Elements
    const taskTypePriorityContainer = document.getElementById('taskTypePriorityContainer');
    const saveGroupPrioritiesBtn = document.getElementById('saveGroupPrioritiesBtn');

    let allTechnicians = [];
    let allGroups = [];
    let allTaskTypes = [];

    function fetchAllTechnicians() {
        fetch('/api/get_technician_mappings')
            .then(response => response.json())
            .then(data => {
                allTechnicians = Object.entries(data.technicians).map(([name, techData]) => ({ id: techData.id, name: name }));
            })
            .catch(error => console.error('Error fetching technicians:', error));
    }

    function fetchTechnicianGroups() {
        fetch('/api/technician_groups')
            .then(response => response.json())
            .then(data => {
                allGroups = data;
                renderTechnicianGroups(allGroups);
                populateGroupMembershipSelect(allGroups);
            })
            .catch(error => console.error('Error fetching technician groups:', error));
    }

    function fetchAllTaskTypes() {
        fetch('/api/task_types')
            .then(response => response.json())
            .then(data => {
                allTaskTypes = data;
            })
            .catch(error => console.error('Error fetching task types:', error));
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
                <span>${group.name}</span>
                <button class="btn btn-danger btn-sm" data-group-id="${group.id}">🗑️</button>
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

        fetch('/api/technician_groups', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ name: groupName })
        })
        .then(response => response.json())
        .then(data => {
            if (data.id) {
                newTechnicianGroupNameInput.value = '';
                fetchTechnicianGroups();
            } else {
                alert(data.message || 'Error creating group');
            }
        })
        .catch(error => console.error('Error creating technician group:', error));
    });

    technicianGroupListContainer.addEventListener('click', function (e) {
        if (e.target.tagName === 'BUTTON' && e.target.dataset.groupId) {
            const groupId = e.target.dataset.groupId;
            if (confirm('Are you sure you want to delete this group?')) {
                fetch(`/api/technician_groups/${groupId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => {
                    if (response.ok) {
                        fetchTechnicianGroups();
                    } else {
                        response.json().then(data => alert(data.message || 'Error deleting group'));
                    }
                })
                .catch(error => console.error('Error deleting technician group:', error));
            }
        }
    });

    groupMembershipSelect.addEventListener('change', function () {
        const groupId = this.value;
        if (groupId) {
            selectedGroupNameSpan.textContent = this.options[this.selectedIndex].text;
            groupMembershipDetails.style.display = 'block';
            loadGroupMembers(groupId);
            loadGroupPriorities(groupId);
            saveGroupPrioritiesBtn.style.display = 'block';
        } else {
            groupMembershipDetails.style.display = 'none';
            taskTypePriorityContainer.innerHTML = '<p>Select a group to manage priorities.</p>';
            saveGroupPrioritiesBtn.style.display = 'none';
        }
    });

    function loadGroupMembers(groupId) {
        fetch(`/api/technician_groups/${groupId}/technicians`)
            .then(response => response.json())
            .then(members => {
                const memberIds = new Set(members.map(m => m.id));
                const availableTechnicians = allTechnicians.filter(t => !memberIds.has(t.id));
                
                renderMembershipLists(availableTechnicians, members);
            })
            .catch(error => console.error(`Error fetching members for group ${groupId}:`, error));
    }

    function loadGroupPriorities(groupId) {
        fetch(`/api/technician_groups/${groupId}/priorities`)
            .then(response => response.json())
            .then(priorities => {
                renderTaskTypePriorities(priorities);
            })
            .catch(error => console.error(`Error fetching priorities for group ${groupId}:`, error));
    }

    function renderTaskTypePriorities(priorities) {
        taskTypePriorityContainer.innerHTML = '';
        const prioritizedTaskIds = new Set(priorities.map(p => p.task_type_id));
        const unprioritizedTasks = allTaskTypes.filter(taskType => !prioritizedTaskIds.has(taskType.id));

        const allTasksForGroup = [
            ...priorities.map(p => ({...allTaskTypes.find(t => t.id === p.task_type_id), priority: p.priority})),
            ...unprioritizedTasks.map(t => ({...t, priority: null}))
        ];

        allTasksForGroup.sort((a, b) => {
            if (a.priority === null) return 1;
            if (b.priority === null) return -1;
            return a.priority - b.priority;
        });

        if (allTasksForGroup.length === 0) {
            taskTypePriorityContainer.innerHTML = '<p>No task types found.</p>';
            return;
        }

        allTasksForGroup.forEach((taskType, index) => {
            const item = document.createElement('div');
            item.className = 'list-item priority-item';
            item.dataset.taskTypeId = taskType.id;
            item.innerHTML = `
                <span>${taskType.name}</span>
                <div class="btn-group">
                    <button class="btn btn-sm btn-outline-secondary up-btn" ${index === 0 ? 'disabled' : ''}>⬆️</button>
                    <button class="btn btn-sm btn-outline-secondary down-btn" ${index === allTasksForGroup.length - 1 ? 'disabled' : ''}>⬇️</button>
                </div>
            `;
            taskTypePriorityContainer.appendChild(item);
        });
    }

    taskTypePriorityContainer.addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;

        const item = target.closest('.priority-item');
        if (!item) return;

        if (target.classList.contains('up-btn')) {
            const prev = item.previousElementSibling;
            if (prev) {
                item.parentNode.insertBefore(item, prev);
                updatePriorityButtons();
            }
        } else if (target.classList.contains('down-btn')) {
            const next = item.nextElementSibling;
            if (next) {
                item.parentNode.insertBefore(next, item);
                updatePriorityButtons();
            }
        }
    });

    function updatePriorityButtons() {
        const items = taskTypePriorityContainer.querySelectorAll('.priority-item');
        items.forEach((item, index) => {
            const upBtn = item.querySelector('.up-btn');
            const downBtn = item.querySelector('.down-btn');
            if (upBtn) upBtn.disabled = index === 0;
            if (downBtn) downBtn.disabled = index === items.length - 1;
        });
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
            return fetch('/api/technician_group_members', {
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

    saveGroupPrioritiesBtn.addEventListener('click', function () {
        const groupId = groupMembershipSelect.value;
        if (!groupId) return;

        const priorityItems = taskTypePriorityContainer.querySelectorAll('.priority-item');
        const priorities = Array.from(priorityItems).map((item, index) => ({
            task_type_id: item.dataset.taskTypeId,
            priority: index + 1
        }));

        fetch(`/api/technician_groups/${groupId}/priorities`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ priorities: priorities })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatusMessage('Priorities saved successfully!', 'success');
                loadGroupPriorities(groupId);
            } else {
                showStatusMessage(data.message || 'Error saving priorities.', 'error');
            }
        })
        .catch(error => {
            console.error('Error saving priorities:', error)
            showStatusMessage('An error occurred while saving priorities.', 'error');
        });
    });

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
    fetchAllTaskTypes();
});