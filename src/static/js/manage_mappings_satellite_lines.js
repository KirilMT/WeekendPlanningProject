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
        li.style.display = 'flex';
        li.style.alignItems = 'center';

        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = window.escapeHtml(point.name); // Display escaped name
        nameSpan.style.marginRight = '10px';

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'item-actions';

        const editButton = document.createElement('button');
        editButton.className = 'btn btn-warning btn-sm';
        editButton.dataset.id = point.id;
        editButton.dataset.name = point.name; // Store raw name
        editButton.innerHTML = '<span class="btn-icon">✏️</span> Edit';
        editButton.style.padding = '2px 6px';
        editButton.style.fontSize = '0.8em';
        editButton.style.marginRight = '5px';

        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-danger btn-sm';
        deleteButton.dataset.id = point.id;
        deleteButton.dataset.name = point.name; // Store raw name
        deleteButton.innerHTML = '<span class="btn-icon">🗑️</span> Delete';
        deleteButton.style.padding = '2px 6px';
        deleteButton.style.fontSize = '0.8em';

        actionsDiv.appendChild(editButton);
        actionsDiv.appendChild(deleteButton);

        li.appendChild(nameSpan);
        li.appendChild(actionsDiv);
        ul.appendChild(li);
    });
    container.appendChild(ul);

    // Add event listeners for edit and delete buttons
    container.querySelectorAll('.btn-warning').forEach(button => {
        button.addEventListener('click', handleEditSatellitePoint);
    });
    container.querySelectorAll('.btn-danger').forEach(button => {
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
        window.displayMessage('Failed to add satellite point. See console for details.', 'error');
    }
}

// Function to handle initiating an edit for a satellite point
function handleEditSatellitePoint(event) {
    const pointId = event.target.dataset.id;
    const currentRawName = event.target.dataset.name; // Raw name
    const listItem = event.target.closest('.item-list-item');

    listItem.innerHTML = `
        <input type="text" value="${window.escapeHtml(currentRawName)}" class="edit-input form-control" data-id="${pointId}" style="flex-grow:1; margin-right: 5px;">
        <div class="item-actions">
            <button class="btn btn-success btn-sm save-edit-satellite-point" data-id="${pointId}" data-current-name="${currentRawName}">
                <span class="btn-icon">💾</span> Save
            </button>
            <button class="btn btn-secondary btn-sm cancel-edit-satellite-point">Cancel</button>
        </div>
    `;

    listItem.querySelector('.save-edit-satellite-point').addEventListener('click', async (e) => {
        const newName = listItem.querySelector('.edit-input').value.trim();
        const originalRawName = e.target.dataset.currentName; // Raw name for comparison
        if (!newName) {
            window.displayMessage('Satellite point name cannot be empty.', 'error');
            return;
        }
        if (newName === originalRawName) {
            window.displayMessage('Name is unchanged.', 'info');
            loadSatellitePoints();
            return;
        }
        await executeUpdateSatellitePoint(pointId, newName);
    });

    listItem.querySelector('.cancel-edit-satellite-point').addEventListener('click', () => {
        loadSatellitePoints();
    });
}

// Function to execute the update of a satellite point
async function executeUpdateSatellitePoint(pointId, newName) { // newName is raw
    try {
        const response = await window.fetch_put(`/api/satellite_points/${pointId}`, { name: newName });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error updating satellite point: ${responseData.message || response.status}`, 'error');
        } else {
            const displayName = responseData.name || newName; // Prefer responseData.name, fallback to input newName
            window.displayMessage(`Satellite point '${window.escapeHtml(displayName)}' updated successfully.`, 'success');
        }
    } catch (error) {
        window.displayMessage('Failed to update satellite point. See console for details.', 'error');
    } finally {
        loadSatellitePoints();
    }
}

// Function to handle deleting a satellite point
async function handleDeleteSatellitePoint(event) {
    const pointId = event.target.dataset.id;
    const rawPointName = event.target.dataset.name; // Raw name

    const cleanedPointName = typeof rawPointName === 'string' ? rawPointName.replace(/\"/g, '"') : rawPointName;

    if (!confirm(`Are you sure you want to delete satellite point "${cleanedPointName}"?`)) {
        return;
    }

    try {
        const response = await window.fetch_delete(`/api/satellite_points/${pointId}`);
        // Assuming responseData might not always be JSON or relevant for delete success message
        await response.json().catch(() => {}); // Consume JSON if any, ignore error

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Failed to parse error response.' }));
            window.displayMessage(`Error deleting satellite point: ${errorData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Satellite point '${window.escapeHtml(rawPointName)}' deleted successfully.`, 'success');
        }
    } catch (error) {
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

    const linesBySatellitePoint = lines.reduce((acc, line) => {
        const spName = line.satellite_point_name || 'Unassigned Lines';
        if (!acc[spName]) {
            acc[spName] = [];
        }
        acc[spName].push(line);
        return acc;
    }, {});

    const sortedSpNames = Object.keys(linesBySatellitePoint).sort((a, b) => {
        if (a === 'Unassigned Lines') return 1;
        if (b === 'Unassigned Lines') return -1;
        return a.localeCompare(b);
    });

    for (const spName of sortedSpNames) {
        const groupLines = linesBySatellitePoint[spName];

        const groupHeader = document.createElement('h4');
        groupHeader.className = 'line-group-header';
        groupHeader.textContent = window.escapeHtml(spName);
        container.appendChild(groupHeader);

        const ul = document.createElement('ul');
        ul.className = 'item-list';

        groupLines.forEach(line => {
            const li = document.createElement('li');
            li.className = 'item-list-item';
            li.style.display = 'flex';
            li.style.alignItems = 'center';

            const nameSpan = document.createElement('span');
            nameSpan.className = 'item-name';
            nameSpan.textContent = window.escapeHtml(line.name); // Display escaped name
            nameSpan.style.marginRight = '10px';

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'item-actions';

            const editButton = document.createElement('button');
            editButton.className = 'btn btn-warning btn-sm';
            editButton.dataset.id = line.id;
            editButton.dataset.name = line.name; // Store raw name
            editButton.dataset.spId = line.satellite_point_id;
            editButton.innerHTML = '<span class="btn-icon">✏️</span> Edit';
            editButton.style.padding = '2px 6px';
            editButton.style.fontSize = '0.8em';
            editButton.style.marginRight = '5px';

            const deleteButton = document.createElement('button');
            deleteButton.className = 'btn btn-danger btn-sm';
            deleteButton.dataset.id = line.id;
            deleteButton.dataset.name = line.name; // Store raw name
            deleteButton.innerHTML = '<span class="btn-icon">🗑️</span> Delete';
            deleteButton.style.padding = '2px 6px';
            deleteButton.style.fontSize = '0.8em';

            actionsDiv.appendChild(editButton);
            actionsDiv.appendChild(deleteButton);

            li.appendChild(nameSpan);
            li.appendChild(actionsDiv);
            ul.appendChild(li);
        });
        container.appendChild(ul);
    }

    container.querySelectorAll('.btn-warning').forEach(button => {
        button.addEventListener('click', handleEditLine);
    });
    container.querySelectorAll('.btn-danger').forEach(button => {
        button.addEventListener('click', handleDeleteLine);
    });
}

// Function to handle adding a new line
async function handleAddLine() {
    const newNameInput = document.getElementById('newLineName');
    const satellitePointSelect = document.getElementById('newLineSatellitePointSelect');
    const name = newNameInput.value.trim(); // raw name
    const satellitePointId = satellitePointSelect.value;
    const newLineErrorDiv = document.getElementById('newLineError');

    if (newLineErrorDiv) {
        newLineErrorDiv.textContent = '';
        newLineErrorDiv.style.display = 'none';
    }

    if (!name) {
        if (newLineErrorDiv) {
            newLineErrorDiv.textContent = 'Line name cannot be empty.';
            newLineErrorDiv.style.display = 'block';
        }
        return;
    }
    if (!satellitePointId) {
        if (newLineErrorDiv) {
            newLineErrorDiv.textContent = 'Please select a satellite point for the line.';
            newLineErrorDiv.style.display = 'block';
        }
        return;
    }

    try {
        const response = await window.fetch_post('/api/lines', { name, satellite_point_id: parseInt(satellitePointId) });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error adding line: ${responseData.message || response.status}`, 'error');
        } else {
            const rawLineName = responseData.name; // raw
            const rawSpName = responseData.satellite_point_name; // raw
            const lineNameStr = window.escapeHtml(rawLineName);
            let successMsg;
            if (rawSpName) {
                successMsg = `Line '${lineNameStr}' added successfully to satellite point '${window.escapeHtml(rawSpName)}'.`;
            } else {
                successMsg = `Line '${lineNameStr}' added successfully.`;
            }
            window.displayMessage(successMsg, 'success');
            newNameInput.value = '';
            satellitePointSelect.value = '';
            satellitePointSelect.disabled = true;
            loadLines();
        }
    } catch (error) {
        window.displayMessage('Failed to add line. See console for details.', 'error');
    }
}

// Function to handle initiating an edit for a line
function handleEditLine(event) {
    const lineId = event.target.dataset.id;
    const currentRawName = event.target.dataset.name; // Raw name
    const currentSpId = event.target.dataset.spId;
    const listItem = event.target.closest('.item-list-item');

    const spSelectElement = document.createElement('select');
    spSelectElement.className = 'edit-line-sp-select';
    spSelectElement.style.padding = '8px';
    spSelectElement.style.marginRight = '5px';

    const sourceSpDropdown = document.getElementById('newLineSatellitePointSelect');
    if (sourceSpDropdown) {
        Array.from(sourceSpDropdown.options).forEach(opt => {
            if(opt.value) {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.textContent; // Already escaped if source is, or raw if source is
                if (opt.value === currentSpId) {
                    option.selected = true;
                }
                spSelectElement.appendChild(option);
            }
        });
    } else {
        const option = document.createElement('option');
        option.value = currentSpId;
        option.textContent = `Current SP ID: ${currentSpId} (Full list unavailable)`;
        option.selected = true;
        spSelectElement.appendChild(option);
        window.displayMessage('Satellite point list for editing line might be incomplete.', 'warning');
    }

    listItem.innerHTML = `
        <input type="text" value="${window.escapeHtml(currentRawName)}" class="edit-line-name-input form-control" style="flex-grow:1; margin-right: 5px;">
        ${spSelectElement.outerHTML}
        <div class="item-actions" style="display: flex; align-items: center;">
            <button class="btn btn-success btn-sm save-line-edit-button" data-id="${lineId}" data-current-name="${currentRawName}" data-current-sp-id="${currentSpId}">
                <span class="btn-icon">💾</span> Save
            </button>
            <button class="btn btn-secondary btn-sm cancel-line-edit-button">Cancel</button>
        </div>
    `;

    listItem.querySelector('.save-line-edit-button').addEventListener('click', async (e) => {
        const newName = listItem.querySelector('.edit-line-name-input').value.trim(); // raw
        const newSpId = listItem.querySelector('.edit-line-sp-select').value;
        const originalRawName = e.target.dataset.currentName; // raw
        const originalSpId = e.target.dataset.currentSpId;

        if (!newName) {
            window.displayMessage('Line name cannot be empty.', 'error');
            return;
        }
        if (!newSpId) {
            window.displayMessage('Satellite Point ID cannot be empty for a line.', 'error');
            return;
        }
        if (newName === originalRawName && newSpId === originalSpId) {
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
async function executeUpdateLine(lineId, newName, newSatellitePointId) { // newName is raw
    try {
        const response = await window.fetch_put(`/api/lines/${lineId}`, { name: newName, satellite_point_id: newSatellitePointId });
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error updating line: ${responseData.message || response.status}`, 'error');
        } else {
            const rawLineName = responseData.name || newName; // Prefer response, fallback to input
            let rawSpName = 'Unknown Satellite Point';

            const satellitePointSelect = document.getElementById('newLineSatellitePointSelect');
            if (satellitePointSelect) {
                const selectedOption = Array.from(satellitePointSelect.options).find(opt => opt.value === String(newSatellitePointId));
                if (selectedOption && selectedOption.textContent) {
                    rawSpName = selectedOption.textContent; // This textContent should be raw or consistently escaped
                }
            }
            if (responseData.satellite_point_name) { // Prefer actual name from DB response
                rawSpName = responseData.satellite_point_name;
            }

            const lineNameStr = window.escapeHtml(rawLineName);
            if (rawSpName && rawSpName !== 'Unknown Satellite Point') {
                window.displayMessage(`Line '${lineNameStr}' updated successfully for satellite point '${window.escapeHtml(rawSpName)}'.`, 'success');
            } else {
                window.displayMessage(`Line '${lineNameStr}' updated successfully.`, 'success');
            }
        }
    } catch (error) {
        window.displayMessage('Failed to update line. See console for details.', 'error');
    } finally {
        loadLines();
    }
}

// Function to handle deleting a line
async function handleDeleteLine(event) {
    const lineId = event.target.dataset.id;
    const rawLineName = event.target.dataset.name; // Raw name

    const cleanedLineName = typeof rawLineName === 'string' ? rawLineName.replace(/\"/g, '"') : rawLineName;

    if (!confirm(`Are you sure you want to delete line "${cleanedLineName}"?`)) {
        return;
    }

    try {
        const response = await window.fetch_delete(`/api/lines/${lineId}`);
        await response.json().catch(() => {}); // Consume JSON if any

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Failed to parse error response.' }));
            window.displayMessage(`Error deleting line: ${errorData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Line '${window.escapeHtml(rawLineName)}' deleted successfully.`, 'success');
        }
    } catch (error) {
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

// Function to handle form submission for technician details
async function handleTechnicianFormSubmit(event) {
    event.preventDefault(); // Prevent default form submission

    const form = event.target;
    const satellitePointId = form.querySelector('select[name="satellite_point_id"]').value;
    const technicianName = form.querySelector('input[name="name"]').value.trim();
    const technicianPhone = form.querySelector('input[name="phone"]').value.trim();
    const technicianEmail = form.querySelector('input[name="email"]').value.trim();
    const technicianId = form.dataset.technicianId; // Get technician ID from form dataset

    // Basic validation
    if (!satellitePointId) {
        window.displayMessage('Satellite point is required.', 'error');
        return;
    }
    if (!technicianName) {
        window.displayMessage('Technician name is required.', 'error');
        return;
    }
    if (!technicianPhone && !technicianEmail) {
        window.displayMessage('At least one contact method (phone or email) is required.', 'error');
        return;
    }

    const technicianData = {
        satellite_point_id: parseInt(satellitePointId),
        name: technicianName,
        phone: technicianPhone,
        email: technicianEmail
    };

    try {
        let response;
        if (technicianId) {
            // Update existing technician
            response = await window.fetch_put(`/api/technicians/${technicianId}`, technicianData);
        } else {
            // Add new technician
            response = await window.fetch_post('/api/technicians', technicianData);
        }
        const responseData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));

        if (!response.ok) {
            window.displayMessage(`Error saving technician details: ${responseData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Technician details saved successfully.`, 'success');
            loadTechnicians(); // Refresh technician list
        }
    } catch (error) {
        window.displayMessage('Failed to save technician details. See console for details.', 'error');
    }
}

// Function to load and display technicians
async function loadTechnicians() {
    try {
        const response = await window.fetch_get('/api/technicians');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Invalid JSON response' }));
            window.displayMessage(`Error loading technicians: ${errorData.message || response.status}`, 'error');
            return;
        }
        const technicians = await response.json();
        renderTechnicians(technicians);
    } catch (error) {
        window.displayMessage('Failed to load technicians. See console for details.', 'error');
    }
}

// Function to render technicians in the list
function renderTechnicians(technicians) {
    const container = document.getElementById('technicianListContainer');
    container.innerHTML = ''; // Clear existing content

    if (!technicians || technicians.length === 0) {
        container.innerHTML = '<p>No technicians found. Add technicians above.</p>';
        return;
    }

    const ul = document.createElement('ul');
    ul.className = 'item-list';
    technicians.forEach(tech => {
        const li = document.createElement('li');
        li.className = 'item-list-item';
        li.style.display = 'flex';
        li.style.alignItems = 'center';

        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = window.escapeHtml(tech.name); // Display escaped name
        nameSpan.style.flexGrow = '1';

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'item-actions';

        const editButton = document.createElement('button');
        editButton.className = 'btn btn-warning btn-sm';
        editButton.dataset.id = tech.id;
        editButton.dataset.name = tech.name; // Store raw name
        editButton.innerHTML = '<span class="btn-icon">✏️</span> Edit';
        editButton.style.padding = '2px 6px';
        editButton.style.fontSize = '0.8em';
        editButton.style.marginRight = '5px';

        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-danger btn-sm';
        deleteButton.dataset.id = tech.id;
        deleteButton.dataset.name = tech.name; // Store raw name
        deleteButton.innerHTML = '<span class="btn-icon">🗑️</span> Delete';
        deleteButton.style.padding = '2px 6px';
        deleteButton.style.fontSize = '0.8em';

        actionsDiv.appendChild(editButton);
        actionsDiv.appendChild(deleteButton);

        li.appendChild(nameSpan);
        li.appendChild(actionsDiv);
        ul.appendChild(li);
    });
    container.appendChild(ul);

    container.querySelectorAll('.btn-warning').forEach(button => {
        button.addEventListener('click', handleEditTechnician);
    });
    container.querySelectorAll('.btn-danger').forEach(button => {
        button.addEventListener('click', handleDeleteTechnician);
    });
}

// Function to handle editing a technician
function handleEditTechnician(event) {
    const technicianId = event.target.dataset.id;
    // const rawTechnicianName = event.target.dataset.name; // Raw name

    const form = document.getElementById('technicianForm');
    form.dataset.technicianId = technicianId;

    const nameInput = form.querySelector('input[name="name"]');
    const phoneInput = form.querySelector('input[name="phone"]');
    const emailInput = form.querySelector('input[name="email"]');
    const satellitePointSelect = form.querySelector('select[name="satellite_point_id"]');

    // nameInput.value = rawTechnicianName; // Set initial raw name, then fetch full details

    fetch(`/api/technicians/${technicianId}`)
        .then(response => response.json())
        .then(data => {
            if (data && data.length > 0) {
                const tech = data[0];
                nameInput.value = tech.name; // tech.name is raw
                phoneInput.value = tech.phone || '';
                emailInput.value = tech.email || '';
                satellitePointSelect.value = tech.satellite_point_id || '';
            } else {
                window.displayMessage('Technician not found.', 'error');
            }
        })
        .catch(error => {
            window.displayMessage('Failed to load technician details. See console for details.', 'error');
        });
}

// Function to handle deleting a technician
async function handleDeleteTechnician(event) {
    const technicianId = event.target.dataset.id;
    const rawTechnicianName = event.target.dataset.name; // Raw name

    const cleanedTechName = typeof rawTechnicianName === 'string' ? rawTechnicianName.replace(/\"/g, '"') : rawTechnicianName;

    if (!confirm(`Are you sure you want to delete technician "${cleanedTechName}" (ID: ${technicianId})?`)) {
        return;
    }

    try {
        const response = await window.fetch_delete(`/api/technicians/${technicianId}`);
        await response.json().catch(() => {}); // Consume JSON

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Failed to parse error response.' }));
            window.displayMessage(`Error deleting technician: ${errorData.message || response.status}`, 'error');
        } else {
            window.displayMessage(`Technician '${window.escapeHtml(rawTechnicianName)}' deleted successfully.`, 'success');
            loadTechnicians();
        }
    } catch (error) {
        window.displayMessage('Failed to delete technician. See console for details.', 'error');
    }
}

// Call this new function to set up initial state and listeners for the new line form
// This should be called once, e.g. in the main script's DOMContentLoaded or initializePage
// For now, defining it here. It will be called from manage_mappings_main.js
function initializeNewLineForm() {
    const newLineNameInput = document.getElementById('newLineName');
    const newLineSatellitePointSelect = document.getElementById('newLineSatellitePointSelect');
    const newLineErrorDiv = document.getElementById('newLineError');

    if (newLineNameInput && newLineSatellitePointSelect) {
        newLineSatellitePointSelect.disabled = true; // Initial state

        newLineNameInput.addEventListener('input', () => {
            newLineSatellitePointSelect.disabled = newLineNameInput.value.trim() === '';
            if (newLineNameInput.value.trim() !== '' && newLineErrorDiv) { // Clear error if name is filled
                newLineErrorDiv.textContent = '';
                newLineErrorDiv.style.display = 'none';
            }
        });

        // Also clear error if satellite point is selected (after name was entered)
        newLineSatellitePointSelect.addEventListener('change', () => {
            if (newLineSatellitePointSelect.value !== '' && newLineErrorDiv) {
                newLineErrorDiv.textContent = '';
                newLineErrorDiv.style.display = 'none';
            }
        });
    }
}

// Initialize the new line form on script load
initializeNewLineForm();
