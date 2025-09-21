// --- Main Initialization Function ---
async function initializePage() {
    // 1. Initial UI State Setup for technology form
    newTechnologyGroupSelect.disabled = true;
    newTechnologyParentSelect.disabled = true;
    newTechnologyParentSelect.innerHTML = '<option value="">No Parent (Top Level)</option>';

    // 2. Setup collapsible sections
    setupCollapsibleSections();

    // 3. Event Listeners
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
    const technologyForm = document.getElementById('technologyForm');
    if (technologyForm) {
        technologyForm.addEventListener('submit', (event) => {
            event.preventDefault();
            addNewTechnology();
        });
    }
    const technologyGroupForm = document.getElementById('technologyGroupForm');
    if (technologyGroupForm) {
        technologyGroupForm.addEventListener('submit', (event) => {
            event.preventDefault();
            addNewTechnologyGroup();
        });
    }
    const newTaskForm = document.getElementById('newTaskForm');
    if (newTaskForm) {
        newTaskForm.addEventListener('submit', (event) => {
            event.preventDefault(); // Prevent page reload
            addNewTaskForMapping();
        });
    }

    // Technician action buttons
    const addNewTechnicianForm = document.getElementById('addNewTechnicianForm');
    if (addNewTechnicianForm) {
        addNewTechnicianForm.addEventListener('submit', (event) => {
            event.preventDefault();
            handleSaveNewTechnician();
        });
    }
    const editTechnicianNameBtn = document.getElementById('editTechnicianNameBtn');
    if (editTechnicianNameBtn) {
        editTechnicianNameBtn.addEventListener('click', handleEditTechnicianName); // handleEditTechnicianName is in manage_mappings_technician_data.js
    }
    const deleteTechnicianBtn = document.getElementById('deleteTechnicianBtn');
    if (deleteTechnicianBtn) {
        deleteTechnicianBtn.addEventListener('click', handleDeleteTechnician); // handleDeleteTechnician is in manage_mappings_technician_data.js
    }

    // New Technician Form listeners (from manage_mappings_technician_data.js)
    const newTechnicianNameInputElement = document.getElementById('newTechnicianNameInput');
    if (newTechnicianNameInputElement) {
        newTechnicianNameInputElement.addEventListener('input', handleNewTechnicianNameInputChange);
    }
    const newTechnicianForm = document.getElementById('addNewTechnicianFormContainer');
    if (newTechnicianForm) {
        newTechnicianForm.addEventListener('submit', (event) => {
            event.preventDefault(); // Prevent page reload
            handleSaveNewTechnician();
        });
    }
    const cancelNewTechnicianButton = document.getElementById('cancelNewTechnicianBtn');
    if (cancelNewTechnicianButton) {
        cancelNewTechnicianButton.addEventListener('click', hideNewTechnicianForm); // hideNewTechnicianForm is in manage_mappings_technician_data.js
    }

    // Existing listeners for selected technician details (ensure they are correctly scoped or managed)
    const editTechSatellitePointButton = document.getElementById('editTechSatellitePointBtn');
    if (editTechSatellitePointButton) {
        editTechSatellitePointButton.addEventListener('click', handleTechSatellitePointEdit); // from manage_mappings_technician_data.js
    }
    const techSatellitePointSelectElement = document.getElementById('techSatellitePointSelect');
    if (techSatellitePointSelectElement) {
        techSatellitePointSelectElement.addEventListener('change', handleTechSatellitePointChange); // from manage_mappings_technician_data.js
    }
    // Ensure fetchAndPopulateSatellitePointsDropdowns is called on initialization
    if (typeof fetchAndPopulateSatellitePointsDropdowns === 'function') {
        fetchAndPopulateSatellitePointsDropdowns();
    } else {
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
    document.getElementById('satellitePointForm').addEventListener('submit', (event) => {
        event.preventDefault();
        handleAddSatellitePoint();
    });
    document.getElementById('productionLineForm').addEventListener('submit', (event) => {
        event.preventDefault();
        handleAddLine();
    });
    loadSatellitePoints(); // Also populates dropdowns for other sections
    loadLines(); // Load lines after satellite points are loaded
    initializeNewLineForm(); // Added this call

    // Initialize Technologies & Groups Management
    await fetchAllInitialData();
}

// --- DOMContentLoaded ---
document.addEventListener('DOMContentLoaded', () => {
    initializePage().catch(error => {
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
    await fetchAndPopulateSatellitePointsDropdowns(); // Updated call
    await fetchMappings();

    handleTechnologyNameInputChange();

    if (newTaskTechnologySelectForMapping) {
        populateTechnologySelectDropdown(newTaskTechnologySelectForMapping);
    }
}

// Setup collapsible sections for the new template structure
function setupCollapsibleSections() {
    document.querySelectorAll('.section-header').forEach(header => {
        const section = header.closest('.management-section');
        const content = section.querySelector('.section-content');
        const toggleIcon = header.querySelector('.toggle-icon');

        if (!content || !toggleIcon) return;

        // Initialize as collapsed
        content.style.display = 'none';
        header.setAttribute('aria-expanded', 'false');
        toggleIcon.textContent = '▼';

        header.addEventListener('click', () => {
            const isExpanded = header.getAttribute('aria-expanded') === 'true';

            if (isExpanded) {
                content.style.display = 'none';
                header.setAttribute('aria-expanded', 'false');
                toggleIcon.textContent = '▼';
                content.classList.remove('expanded');
            } else {
                content.style.display = 'block';
                header.setAttribute('aria-expanded', 'true');
                toggleIcon.textContent = '▲';
                content.classList.add('expanded');
            }
        });
    });
}
