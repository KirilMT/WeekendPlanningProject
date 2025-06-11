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
            nameSpan.textContent = escapeHtml(spec.name);
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
            fetchSpecialities();
            if (selectedTechnician && currentMappings.technicians[selectedTechnician]) {
                fetchMappings(selectedTechnician);
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
            fetchSpecialities();
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

