// --- Fetch API Wrappers ---
async function fetch_get(url) {
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            // Add any other common headers, like CSRF tokens if needed
        }
    });
    return response; // The calling code usually handles response.ok and .json()
}

async function fetch_post(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            // Add any other common headers
        },
        body: JSON.stringify(data)
    });
    return response;
}

async function fetch_put(url, data) {
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            // Add any other common headers
        },
        body: JSON.stringify(data)
    });
    return response;
}

async function fetch_delete(url) {
    const response = await fetch(url, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            // Add any other common headers
        }
    });
    return response;
}

// --- End Fetch API Wrappers ---

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

// Alias for displayMessage or specific implementation for showStatus
function showStatus(message, type = 'info') {
    displayMessage(message, type); // Assuming showStatus is an alias for displayMessage
}

// Helper function to get the full technology hierarchy path
function getTechnologyHierarchyPath(technologyId, allTechnologies) {
    // This is a placeholder implementation.
    // You'll need to replace this with the actual logic to determine the hierarchy path.
    // For example, it might find a technology by ID and then traverse up its parent_id links.
    console.warn('getTechnologyHierarchyPath is a placeholder and needs to be implemented.');
    const tech = allTechnologies.find(t => t.id === technologyId);
    return tech ? tech.name : 'Unknown Technology';
}

// Placeholder for recordChange function
function recordChange(type, entityId, field, oldValue, newValue, entityName = null) {
    if (!window.unsavedChanges) {
        window.unsavedChanges = [];
    }
    // Avoid logging redundant "undefined" to "actual_value" changes during initial population or when old value isn't tracked
    // However, allow logging if an actual value is being cleared (newValue is null/undefined)
    if (oldValue === undefined && newValue === undefined) {
        // This case might occur if an initial state is undefined and it's set to undefined explicitly.
        // Or if the change event fires without proper old/new values.
        // console.warn('recordChange called with both oldValue and newValue undefined. Change not recorded.', { type, entityId, field, entityName });
        // Depending on desired strictness, you might choose to record this or not.
        // For now, let's not record if both are undefined, unless it's a deletion type.
        if (!type.toLowerCase().includes('delete') && !type.toLowerCase().includes('remove')) {
            return;
        }
    }

    let changeDescription = type;
    if (entityName && field) {
        changeDescription = `Field '${field}' for ${entityName} (ID: ${entityId}) changed from '${oldValue}' to '${newValue}'`;
    } else if (entityName) {
        changeDescription = `Change for ${entityName} (ID: ${entityId}): ${type}`;
    }

    window.unsavedChanges.push({
        type: type, // General type of change e.g., "Technician Update", "Task Skill Add"
        description: changeDescription, // More detailed human-readable description
        entity: entityName, // Name of the entity being changed (e.g., technician name, task name)
        entityId: entityId, // ID of the entity
        field: field,       // Specific field that was changed
        oldValue: oldValue,
        newValue: newValue,
        timestamp: new Date().toISOString()
    });
    console.log('Change recorded:', window.unsavedChanges[window.unsavedChanges.length - 1]);
    updateSaveChangesButtonState(); // Assumes this function exists to enable/disable save button
}

// Placeholder for clearUnsavedChanges function
function clearUnsavedChanges() {
    window.unsavedChanges = [];
    console.log('Unsaved changes cleared.');
    updateSaveChangesButtonState(); // Assumes this function exists
}

// Add a function to manage the save button's state
function updateSaveChangesButtonState() {
    const saveChangesBtn = document.getElementById('saveChangesBtn');
    if (saveChangesBtn) {
        if (window.unsavedChanges && window.unsavedChanges.length > 0) {
            saveChangesBtn.disabled = false;
            saveChangesBtn.textContent = `Save All Changes (${window.unsavedChanges.length})`;
        } else {
            saveChangesBtn.disabled = true;
            saveChangesBtn.textContent = 'Save All Changes';
        }
    }
}

// Initialize unsavedChanges array and save button state on load
document.addEventListener('DOMContentLoaded', () => {
    window.unsavedChanges = [];
    updateSaveChangesButtonState();
});

// Make utility functions globally available
window.fetch_get = fetch_get;
window.fetch_post = fetch_post;
window.fetch_put = fetch_put;
window.fetch_delete = fetch_delete;
window.showStatus = showStatus;
window.escapeHtml = escapeHtml;
window.getTechnologyHierarchyPath = getTechnologyHierarchyPath;
window.displayMessage = displayMessage; // Already used in other files, ensure it's global if not already

window.recordChange = recordChange; // Assign after definition
window.clearUnsavedChanges = clearUnsavedChanges; // Assign after definition

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

// Ensure utility functions are globally accessible
window.escapeHtml = escapeHtml;
window.displayMessage = displayMessage;
window.getTechnologyHierarchyPath = getTechnologyHierarchyPath; // Assuming this might be useful globally too
window.recordChange = recordChange;
window.clearUnsavedChanges = clearUnsavedChanges;
window.calculateAndAssignDisplayPriorities = calculateAndAssignDisplayPriorities;
window.sortAndRecalculatePriorities = sortAndRecalculatePriorities;

// Assuming fetch_get, fetch_post, etc. and showStatus are defined in this file or another global script.
// If they are in this file and not yet global, they need to be exposed:
// For example, if showStatus is a local alias for displayMessage or similar:
// window.showStatus = displayMessage; // or its actual definition if different

// If fetch helpers are defined in this file, they should also be exposed:
// Example: Assuming they are defined like function fetch_get(...) { ... }
// window.fetch_get = fetch_get;
// window.fetch_post = fetch_post;
// window.fetch_put = fetch_put;
// window.fetch_delete = fetch_delete;

// It seems showStatus is used in manage_mappings_satellite_lines.js but not defined here.
// Let's assume it's an alias for displayMessage or needs to be defined/exposed.
// For now, we'll rely on displayMessage being global and ensure showStatus calls use window.displayMessage or window.showStatus if defined elsewhere.
// If fetch_get etc. are not in this file, this step might be insufficient for them.
// Based on previous interactions, fetch_get, fetch_post, fetch_put, fetch_delete, and showStatus are expected to be global.
// Let's ensure any fetch helpers *if defined in this file* are global.
// If they are defined in another file that's already making them global, this is fine.
// The critical part is that `manage_mappings_satellite_lines.js` calls them via `window.X`.
