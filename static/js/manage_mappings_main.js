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
    if (addNewTaskForMappingBtn) {
        addNewTaskForMappingBtn.addEventListener('click', addNewTaskForMapping);
    }

    // Technician action buttons
    const addNewTechnicianBtn = document.getElementById('addNewTechnicianBtn');
    if (addNewTechnicianBtn) {
        addNewTechnicianBtn.addEventListener('click', handleAddTechnician);
    }
    const editTechnicianNameBtn = document.getElementById('editTechnicianNameBtn');
    if (editTechnicianNameBtn) {
        editTechnicianNameBtn.addEventListener('click', handleEditTechnicianName);
    }
    const deleteTechnicianBtn = document.getElementById('deleteTechnicianBtn');
    if (deleteTechnicianBtn) {
        deleteTechnicianBtn.addEventListener('click', handleDeleteTechnician);
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
        if (!content || !icon) return;

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
                // Remove automatic selection of first technician when expanding section
                // if (header.parentElement.id === 'manageTechnicianDetailsSection' && !selectedTechnician && technicianSelect.options.length > 1) {
                //     technicianSelect.value = technicianSelect.options[1].value;
                //     loadTechnicianDetails(technicianSelect.value);
                // }
            }
        });
    });

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

    // Initialize Satellite Points and Lines Management
    document.getElementById('addSatellitePointBtn').addEventListener('click', handleAddSatellitePoint);
    document.getElementById('addLineBtn').addEventListener('click', handleAddLine); // Added event listener for Add Line button
    loadSatellitePoints(); // Also populates dropdowns for other sections
    loadLines(); // Load lines after satellite points are loaded

    // Initialize Technologies & Groups Management
    await fetchAllInitialData();
}

// --- DOMContentLoaded ---
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
    newTechnologyParentSelect.disabled = isDisabled;

    if (isDisabled) {
        newTechnologyGroupSelect.value = '';
        newTechnologyGroupSelect.dispatchEvent(new Event('change'));
    } else {
        if (newTechnologyGroupSelect.value) {
            populateParentTechnologySelectFiltered(newTechnologyGroupSelect.value);
        } else {
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
    await fetchTechnologyGroups();
    await fetchAllTechnologies();
    await fetchAllTasksForMapping();
    await fetchAndPopulateSatellitePointsDropdown(); // Added call
    await fetchMappings();

    handleTechnologyNameInputChange();

    if (newTaskTechnologySelectForMapping) {
        populateTechnologySelectDropdown(newTaskTechnologySelectForMapping);
    }
}
