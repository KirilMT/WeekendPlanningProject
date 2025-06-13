// Placeholder for satellite points and lines management
// Functions for Satellite Points will be added here.

// Functions for Satellite Points and Lines Management

// --- Satellite Point Management ---

// Function to fetch and display satellite points
async function loadSatellitePoints() {
    try {
        const response = await window.fetch_get('/api/satellite_points');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));
            window.displayMessage(`Error loading satellite points: ${errorData.message || response.status}`, 'error');
            return;
        }
        const satellitePoints = await response.json();
        renderSatellitePoints(satellitePoints);
        populateSatellitePointDropdowns(satellitePoints); // For line management and technician details
    } catch (error) {
        console.error('Error loading satellite points:', error);
        window.displayMessage('Failed to load satellite points. See console for details.', 'error');
    }
}

// Function to render satellite points in the list
function renderSatellitePoints(satellitePoints) {
    const container = document.getElementById('satellitePointListContainer');
    container.innerHTML = ''; // Clear existing content

    if (!satellitePoints || satellitePoints.length === 0) {
        container.innerHTML = '<p>No satellite points found.</p>';
        return;
    }

    const ul = document.createElement('ul');
    ul.className = 'item-list';
    satellitePoints.forEach(point => {
        const li = document.createElement('li');
        li.className = 'item-list-item';
        li.innerHTML = `
            <span class="item-name">ID: ${point.id} - ${window.escapeHtml(point.name)}</span>
            <div class="item-actions">
                <button class="edit-button" data-id="${point.id}" data-name="${window.escapeHtml(point.name)}">Edit</button>
                <button class="delete-button" data-id="${point.id}" data-name="${window.escapeHtml(point.name)}">Delete</button>
            </div>
        `;
        ul.appendChild(li);
    });
    container.appendChild(ul);

    // Add event listeners for edit and delete buttons
    container.querySelectorAll('.edit-button').forEach(button => {
        button.addEventListener('click', handleEditSatellitePoint);
    });
    container.querySelectorAll('.delete-button').forEach(button => {
        button.addEventListener('click', handleDeleteSatellitePoint);
    });
}

// Function to handle adding a new satellite point
async function handleAddSatellitePoint() {
    const newNameInput = document.getElementById('newSatellitePointName');
    const name = newNameInput.value.trim();

    if (!name) {
        window.displayMessage('Satellite point name cannot be empty.', 'error');
        return;
    }

    try {
        const response = await window.fetch_post('/api/satellite_points', { name });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error adding satellite point: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Satellite point '${window.escapeHtml(responseData.name)}' added successfully.`, 'success');
            newNameInput.value = ''; // Clear input
            loadSatellitePoints(); // Refresh the list
        }
    } catch (error) {
        console.error('Error adding satellite point:', error);
        window.displayMessage('Failed to add satellite point. See console for details.', 'error');
    }
}

// Function to handle initiating an edit for a satellite point
function handleEditSatellitePoint(event) {
    const pointId = event.target.dataset.id;
    const currentName = event.target.dataset.name; // Already escaped by renderSatellitePoints if needed
    const listItem = event.target.closest('.item-list-item');

    listItem.innerHTML = `
        <input type="text" value="${currentName}" class="edit-input" data-id="${pointId}" style="flex-grow:1; margin-right: 5px;">
        <div class="item-actions">
            <button class="save-edit-button" data-id="${pointId}" data-current-name="${currentName}">Save</button>
            <button class="cancel-edit-button">Cancel</button>
        </div>
    `;

    listItem.querySelector('.save-edit-button').addEventListener('click', async (e) => {
        const newName = listItem.querySelector('.edit-input').value.trim();
        const originalName = e.target.dataset.currentName; // Get original name for comparison
        if (!newName) {
            window.displayMessage('Satellite point name cannot be empty.', 'error');
            return;
        }
        if (newName === originalName) {
            window.displayMessage('Name is unchanged.', 'info');
            loadSatellitePoints(); // Restore original view
            return;
        }
        await executeUpdateSatellitePoint(pointId, newName);
    });

    listItem.querySelector('.cancel-edit-button').addEventListener('click', () => {
        loadSatellitePoints(); // Restore original view by reloading
    });
}

// Function to execute the update of a satellite point
async function executeUpdateSatellitePoint(pointId, newName) {
    try {
        const response = await window.fetch_put(`/api/satellite_points/${pointId}`, { name: newName });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error updating satellite point: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Satellite point ID ${pointId} updated to '${window.escapeHtml(responseData.name)}'.`, 'success');
        }
    } catch (error) {
        console.error('Error updating satellite point:', error);
        window.displayMessage('Failed to update satellite point. See console for details.', 'error');
    } finally {
        loadSatellitePoints(); // Refresh the list regardless of outcome to ensure UI consistency
    }
}

// Function to handle deleting a satellite point
async function handleDeleteSatellitePoint(event) {
    const pointId = event.target.dataset.id;
    const pointName = event.target.dataset.name; // Get name from data attribute

    if (!confirm(`Are you sure you want to delete satellite point "${pointName}" (ID: ${pointId})?`)) {
        return;
    }

    try {
        const response = await window.fetch_delete(`/api/satellite_points/${pointId}`);
        const responseData = await response.json().catch(() => ({ message: 'Delete operation did not return JSON.' }));

        if (!response.ok) {
            window.displayMessage(`Error deleting satellite point: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(responseData.message || `Satellite point ID ${pointId} deleted successfully.`, 'success');
        }
    } catch (error) {
        console.error('Error deleting satellite point:', error);
        window.displayMessage('Failed to delete satellite point. See console for details.', 'error');
    } finally {
        loadSatellitePoints(); // Refresh the list
    }
}


// --- Line Management ---

// Function to fetch and display lines
async function loadLines() {
    try {
        const response = await window.fetch_get('/api/lines');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));
            window.displayMessage(`Error loading lines: ${errorData.message || response.status}`, 'error');
            return;
        }
        const lines = await response.json();
        renderLines(lines);
    } catch (error) {
        console.error('Error loading lines:', error);
        window.displayMessage('Failed to load lines. See console for details.', 'error');
    }
}

// Function to render lines in the list
function renderLines(lines) {
    const container = document.getElementById('lineListContainer');
    container.innerHTML = ''; // Clear existing content

    if (!lines || lines.length === 0) {
        container.innerHTML = '<p>No lines found. Add lines below or ensure satellite points exist.</p>';
        return;
    }

    const ul = document.createElement('ul');
    ul.className = 'item-list';
    lines.forEach(line => {
        const li = document.createElement('li');
        li.className = 'item-list-item';
        li.innerHTML = `
            <span class="item-name">ID: ${line.id} - ${window.escapeHtml(line.name)} (Satellite Point: ${window.escapeHtml(line.satellite_point_name)} [ID: ${line.satellite_point_id}])</span>
            <div class="item-actions">
                <button class="edit-line-button" data-id="${line.id}" data-name="${window.escapeHtml(line.name)}" data-sp-id="${line.satellite_point_id}">Edit</button>
                <button class="delete-line-button" data-id="${line.id}" data-name="${window.escapeHtml(line.name)}">Delete</button>
            </div>
        `;
        ul.appendChild(li);
    });
    container.appendChild(ul);

    // Add event listeners for edit and delete buttons
    container.querySelectorAll('.edit-line-button').forEach(button => {
        button.addEventListener('click', handleEditLine);
    });
    container.querySelectorAll('.delete-line-button').forEach(button => {
        button.addEventListener('click', handleDeleteLine);
    });
}

// Function to handle adding a new line
async function handleAddLine() {
    const newNameInput = document.getElementById('newLineName');
    const satellitePointSelect = document.getElementById('newLineSatellitePointSelect');
    const name = newNameInput.value.trim();
    const satellitePointId = satellitePointSelect.value;

    if (!name) {
        window.displayMessage('Line name cannot be empty.', 'error');
        return;
    }
    if (!satellitePointId) {
        window.displayMessage('Please select a satellite point for the line.', 'error');
        return;
    }

    try {
        const response = await window.fetch_post('/api/lines', { name, satellite_point_id: parseInt(satellitePointId) });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error adding line: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Line '${window.escapeHtml(responseData.name)}' added successfully to ${window.escapeHtml(responseData.satellite_point_name)}.`, 'success');
            newNameInput.value = ''; // Clear input
            loadLines(); // Refresh the list of lines
        }
    } catch (error) {
        console.error('Error adding line:', error);
        window.displayMessage('Failed to add line. See console for details.', 'error');
    }
}

// Function to handle initiating an edit for a line
function handleEditLine(event) {
    const lineId = event.target.dataset.id;
    const currentName = event.target.dataset.name; // Already escaped
    const currentSpId = event.target.dataset.spId;
    const listItem = event.target.closest('.item-list-item');

    const spSelectElement = document.createElement('select');
    spSelectElement.className = 'edit-line-sp-select';

    const sourceSpDropdown = document.getElementById('newLineSatellitePointSelect'); // Source of truth for SPs
    if (sourceSpDropdown) {
        Array.from(sourceSpDropdown.options).forEach(opt => {
            if(opt.value) { // Exclude the placeholder "Select Satellite Point"
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.textContent;
                if (opt.value === currentSpId) {
                    option.selected = true;
                }
                spSelectElement.appendChild(option);
            }
        });
    } else {
        // Fallback if the primary dropdown isn't available (should not happen ideally)
        const option = document.createElement('option');
        option.value = currentSpId;
        option.textContent = `Current SP ID: ${currentSpId} (Full list unavailable)`;
        option.selected = true;
        spSelectElement.appendChild(option);
        window.displayMessage('Satellite point list for editing line might be incomplete.', 'warning');
    }

    listItem.innerHTML = `
        <input type="text" value="${currentName}" class="edit-line-name-input" style="flex-grow:1; margin-right: 5px;">
        ${spSelectElement.outerHTML}
        <div class="item-actions">
            <button class="save-line-edit-button" data-id="${lineId}" data-current-name="${currentName}" data-current-sp-id="${currentSpId}">Save</button>
            <button class="cancel-line-edit-button">Cancel</button>
        </div>
    `;

    listItem.querySelector('.save-line-edit-button').addEventListener('click', async (e) => {
        const newName = listItem.querySelector('.edit-line-name-input').value.trim();
        const newSpId = listItem.querySelector('.edit-line-sp-select').value;
        const originalName = e.target.dataset.currentName;
        const originalSpId = e.target.dataset.currentSpId;

        if (!newName) {
            window.displayMessage('Line name cannot be empty.', 'error');
            return;
        }
        if (!newSpId) {
            window.displayMessage('Satellite Point ID cannot be empty for a line.', 'error');
            return;
        }
        if (newName === originalName && newSpId === originalSpId) {
            window.displayMessage('Line data unchanged.', 'info');
            loadLines();
            return;
        }
        await executeUpdateLine(lineId, newName, parseInt(newSpId));
    });

    listItem.querySelector('.cancel-line-edit-button').addEventListener('click', () => {
        loadLines();
    });
}

// Function to execute the update of a line
async function executeUpdateLine(lineId, newName, newSatellitePointId) {
    try {
        const response = await window.fetch_put(`/api/lines/${lineId}`, { name: newName, satellite_point_id: newSatellitePointId });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error updating line: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Line ID ${lineId} updated to '${window.escapeHtml(responseData.name)}' for SP '${window.escapeHtml(responseData.satellite_point_name)}'.`, 'success');
        }
    } catch (error) {
        console.error('Error updating line:', error);
        window.displayMessage('Failed to update line. See console for details.', 'error');
    } finally {
        loadLines();
    }
}

// Function to handle deleting a line
async function handleDeleteLine(event) {
    const lineId = event.target.dataset.id;
    const lineName = event.target.dataset.name; // Get name from data attribute

    if (!confirm(`Are you sure you want to delete line "${lineName}" (ID: ${lineId})?`)) {
        return;
    }

    try {
        const response = await window.fetch_delete(`/api/lines/${lineId}`);
        const responseData = await response.json().catch(() => ({ message: 'Delete operation did not return JSON.' }));

        if (!response.ok) {
            window.displayMessage(`Error deleting line: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(responseData.message || `Line ID ${lineId} deleted successfully.`, 'success');
        }
    } catch (error) {
        console.error('Error deleting line:', error);
        window.displayMessage('Failed to delete line. See console for details.', 'error');
    } finally {
        loadLines();
    }
}

// Utility to populate satellite point dropdowns (used for Lines and Technician Details)
function populateSatellitePointDropdowns(satellitePoints) {
    const newLineSpSelect = document.getElementById('newLineSatellitePointSelect');
    const techSpSelect = document.getElementById('techSatellitePointSelect');

    if(newLineSpSelect) {
        const currentVal = newLineSpSelect.value;
        newLineSpSelect.innerHTML = '<option value="">Select Satellite Point</option>';
        satellitePoints.forEach(point => {
            const option = document.createElement('option');
            option.value = point.id;
            option.textContent = window.escapeHtml(point.name);
            newLineSpSelect.appendChild(option);
        });
        if (satellitePoints.some(p => p.id.toString() === currentVal)) {
             newLineSpSelect.value = currentVal;
        } else {
            newLineSpSelect.value = ""; // Reset if previous value is no longer valid
        }
    }

    if(techSpSelect) {
        const currentVal = techSpSelect.value;
        techSpSelect.innerHTML = '';
         satellitePoints.forEach(point => {
            const option = document.createElement('option');
            option.value = point.id;
            option.textContent = window.escapeHtml(point.name);
            techSpSelect.appendChild(option);
        });

        // Attempt to reselect based on GLOBAL_STATE or current value
        if (window.GLOBAL_STATE && window.GLOBAL_STATE.selectedTechnician && window.GLOBAL_STATE.selectedTechnician.satellite_point_id) {
            if (satellitePoints.some(p => p.id.toString() === window.GLOBAL_STATE.selectedTechnician.satellite_point_id.toString())) {
                 techSpSelect.value = window.GLOBAL_STATE.selectedTechnician.satellite_point_id;
            } else if (currentVal && satellitePoints.some(p => p.id.toString() === currentVal)) {
                techSpSelect.value = currentVal;
            } else if (satellitePoints.length > 0) {
                techSpSelect.value = satellitePoints[0].id; // Default to first if selection is invalid
            }
        } else if (currentVal && satellitePoints.some(p => p.id.toString() === currentVal)) {
             techSpSelect.value = currentVal;
        } else if (satellitePoints.length > 0) {
             techSpSelect.value = satellitePoints[0].id; // Default to first if no other selection criteria met
        }
    }
}
