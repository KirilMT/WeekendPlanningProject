// --- Technician Skill Management ---
async function fetchTechnicianSkills(technicianName) {
    if (!technicianName || !currentSelectedTechnicianId) {
        renderTechnicianSkills();
        return;
    }
    try {
        const response = await fetch(`/api/technician_skills/${currentSelectedTechnicianId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const skillsData = await response.json();
        currentMappings.technicians[technicianName].skills = skillsData.skills || {};
        renderTechnicianSkills();
    } catch (error) {
        displayMessage(`Error fetching skills for ${technicianName}: ${error.message}`, 'error');
        console.error('Error fetching skills:', error);
        if (currentMappings.technicians && currentMappings.technicians[technicianName]) {
            currentMappings.technicians[technicianName].skills = {};
        }
        renderTechnicianSkills();
    }
}

const SKILL_LEVEL_TEXTS = ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"];

function renderTechnicianSkills() {
    technicianSkillsListContainerDiv.innerHTML = '';
    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        technicianSkillsListContainerDiv.innerHTML = '<p>Select technician to view skills.</p>';
        return;
    }
    if (allTechnologies.length === 0) {
        technicianSkillsListContainerDiv.innerHTML = '<p>No technologies defined. Skills cannot be assigned.</p>';
        return;
    }

    const techSkills = currentMappings.technicians[selectedTechnician].skills || {};

    const hasChildren = (technologyId) => {
        return allTechnologies.some(tech => tech.parent_id === technologyId);
    };

    const createSkillViewMode = (technology, currentLevel) => {
        const container = document.createElement('div');
        container.classList.add('skill-level-container');

        const levelTextSpan = document.createElement('span');
        levelTextSpan.classList.add('skill-level-text');
        levelTextSpan.textContent = `Level: ${SKILL_LEVEL_TEXTS[currentLevel]}`;
        container.appendChild(levelTextSpan);

        const editButton = document.createElement('button');
        editButton.classList.add('edit-skill-btn');
        editButton.textContent = 'Edit';
        editButton.addEventListener('click', () => {
            const skillItemDiv = container.closest('.skill-item-controls');
            skillItemDiv.innerHTML = ''; // Clear view mode
            skillItemDiv.appendChild(createSkillEditMode(technology, currentLevel));
        });
        container.appendChild(editButton);
        return container;
    };

    const createSkillEditMode = (technology, currentLevel) => {
        const container = document.createElement('div');
        container.classList.add('skill-level-container', 'edit-mode');

        const skillSelect = document.createElement('select');
        skillSelect.id = `skill-${technology.id}-select`;
        skillSelect.dataset.technologyId = technology.id;
        SKILL_LEVEL_TEXTS.forEach((lvlText, idx) => {
            const option = document.createElement('option');
            option.value = idx;
            option.textContent = lvlText;
            if (currentLevel === idx) option.selected = true;
            skillSelect.appendChild(option);
        });
        container.appendChild(skillSelect);

        const saveButton = document.createElement('button');
        saveButton.textContent = 'Save';
        saveButton.classList.add('save-skill-btn');
        saveButton.addEventListener('click', async () => {
            const newLevel = parseInt(skillSelect.value);
            await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, technology.id, newLevel);
            // After successful save, revert to view mode.
            // The updateTechnicianSkill function already updates currentMappings.
            // We need to re-render this specific skill's controls or the whole list.
            // For simplicity here, we'll replace the controls for this skill.
            const skillItemDiv = container.closest('.skill-item-controls');
            skillItemDiv.innerHTML = ''; // Clear edit mode
            skillItemDiv.appendChild(createSkillViewMode(technology, newLevel));
        });
        container.appendChild(saveButton);

        const cancelButton = document.createElement('button');
        cancelButton.textContent = 'Cancel';
        cancelButton.classList.add('cancel-skill-btn');
        cancelButton.addEventListener('click', () => {
            const skillItemDiv = container.closest('.skill-item-controls');
            skillItemDiv.innerHTML = ''; // Clear edit mode
            skillItemDiv.appendChild(createSkillViewMode(technology, currentLevel)); // Revert to original level
        });
        container.appendChild(cancelButton);

        return container;
    };


    function renderSkillItemsRecursive(parentElement, parentTechnologyId, level) {
        const childrenOfParent = allTechnologies.filter(tech => tech.parent_id === parentTechnologyId);
        childrenOfParent.sort((a, b) => a.name.localeCompare(b.name));

        childrenOfParent.forEach(childTech => {
            const skillDiv = document.createElement('div');
            skillDiv.classList.add('skill-item');
            skillDiv.style.marginLeft = `${level * 25}px`;

            const skillLabel = document.createElement('label');
            skillLabel.className = 'skill-label';
            skillLabel.textContent = escapeHtml(childTech.name);
            skillDiv.appendChild(skillLabel);

            const controlsDiv = document.createElement('div');
            controlsDiv.classList.add('skill-item-controls');

            if (!hasChildren(childTech.id)) {
                const currentSkillLevel = techSkills[childTech.id] || 0;
                controlsDiv.appendChild(createSkillViewMode(childTech, currentSkillLevel));
            }
            skillDiv.appendChild(controlsDiv);
            parentElement.appendChild(skillDiv);

            if (hasChildren(childTech.id)) {
                renderSkillItemsRecursive(parentElement, childTech.id, level + 1);
            }
        });
    }

    const topLevelTechnologies = allTechnologies.filter(tech => tech.parent_id === null);
    topLevelTechnologies.sort((a, b) => {
        const groupCompare = (a.group_name || 'ZZZ_Uncategorized').localeCompare(b.group_name || 'ZZZ_Uncategorized');
        if (groupCompare !== 0) return groupCompare;
        return a.name.localeCompare(b.name);
    });

    let currentGroupName = null;
    topLevelTechnologies.forEach(topLevelTech => {
        if (topLevelTech.group_name !== currentGroupName) {
            const groupHeader = document.createElement('h4');
            groupHeader.textContent = escapeHtml(topLevelTech.group_name || 'Uncategorized');
            groupHeader.classList.add('skill-group-header');
            technicianSkillsListContainerDiv.appendChild(groupHeader);
            currentGroupName = topLevelTech.group_name;
        }

        const skillDiv = document.createElement('div');
        skillDiv.classList.add('skill-item');
        skillDiv.style.marginLeft = '0px';

        const skillLabel = document.createElement('label');
        skillLabel.className = 'skill-label';
        skillLabel.textContent = escapeHtml(topLevelTech.name);
        skillDiv.appendChild(skillLabel);

        const controlsDiv = document.createElement('div');
        controlsDiv.classList.add('skill-item-controls');

        if (!hasChildren(topLevelTech.id)) {
            const currentSkillLevel = techSkills[topLevelTech.id] || 0;
            controlsDiv.appendChild(createSkillViewMode(topLevelTech, currentSkillLevel));
        }
        skillDiv.appendChild(controlsDiv);
        technicianSkillsListContainerDiv.appendChild(skillDiv);

        if (hasChildren(topLevelTech.id)) {
            renderSkillItemsRecursive(technicianSkillsListContainerDiv, topLevelTech.id, 1);
        }
    });
}

async function updateTechnicianSkill(technicianName, technicianId, technologyId, skillLevel) {
    if (!technicianName || typeof technicianId === 'undefined') {
        displayMessage('Technician not selected for skill update.', 'error');
        return;
    }
    try {
        const response = await fetch('/api/technician_skill', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({technician_id: technicianId, technology_id: technologyId, skill_level: skillLevel}),
        });
        const result = await response.json();
        if (response.ok) {
            displayMessage(`Skill for tech ID ${technologyId} updated.`, 'success');
            if (!currentMappings.technicians[selectedTechnician].skills) currentMappings.technicians[selectedTechnician].skills = {};
            currentMappings.technicians[selectedTechnician].skills[technologyId] = skillLevel;
            recordChange(`Skill for ${escapeHtml(technicianName)} on tech ID ${technologyId} changed to ${skillLevel}`);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating skill: ${error.message}`, 'error');
        console.error(error);
        await fetchTechnicianSkills(selectedTechnician); // Revert UI
    }
}
