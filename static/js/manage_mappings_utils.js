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

// Helper function to get the full technology hierarchy path
function getTechnologyHierarchyPath(technologyId, allTechs) {
    const targetTech = allTechs.find(t => t.id === technologyId);
    if (!targetTech) return 'No Technology Assigned';

    const pathNames = [];
    let currentTech = targetTech;
    let groupName = escapeHtml(targetTech.group_name || 'Uncategorized');

    while (currentTech) {
        pathNames.unshift(escapeHtml(currentTech.name));
        if (currentTech.parent_id) {
            const parentTech = allTechs.find(t => t.id === currentTech.parent_id);
            if (parentTech) {
                currentTech = parentTech;
            } else {
                // Parent ID exists but parent not found, stop traversal
                currentTech = null;
            }
        } else {
            // This is the top-most technology in this specific branch.
            groupName = escapeHtml(currentTech.group_name || 'Uncategorized');
            currentTech = null; // Stop traversal
        }
    }
    pathNames.unshift(groupName);
    return pathNames.join(' / ');
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

