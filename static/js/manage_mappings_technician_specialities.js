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
            specDiv.innerHTML = `<span>${escapeHtml(spec.name)}</span>`;
            const removeBtn = document.createElement('button');
            removeBtn.textContent = 'Remove';
            removeBtn.classList.add('delete-btn');
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
            fetchMappings(selectedTechnician);
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

