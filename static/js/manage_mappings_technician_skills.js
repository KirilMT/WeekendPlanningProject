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

        skillSelect.addEventListener('change', async () => {
            const newLevel = parseInt(skillSelect.value);
            // selectedTechnician and currentSelectedTechnicianId are global variables
            await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, technology.id, newLevel);
            // updateTechnicianSkill calls renderTechnicianSkills, which will redraw the list,
            // automatically removing this edit-mode select and showing the updated view mode.
        });

        // Save and Cancel buttons are removed as per the new auto-save requirement.

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
                const skillInfo = techSkills[childTech.id];
                const currentSkillLevel = skillInfo ? skillInfo.level : 0;
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
            const skillInfo = techSkills[topLevelTech.id];
            const currentSkillLevel = skillInfo ? skillInfo.level : 0;
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
            const technology = allTechnologies.find(t => t.id === parseInt(technologyId));
            const technologyName = technology ? technology.name : 'Unknown Skill';
            const techNameForMsg = technicianName || 'Selected Technician';

            displayMessage(`Skill '${escapeHtml(technologyName)}' for technician '${escapeHtml(techNameForMsg)}' updated to level ${escapeHtml(SKILL_LEVEL_TEXTS[skillLevel] || skillLevel)}.`, 'success');

            if (currentMappings.technicians[selectedTechnician]) {
                if (!currentMappings.technicians[selectedTechnician].skills) {
                    currentMappings.technicians[selectedTechnician].skills = {};
                }
                currentMappings.technicians[selectedTechnician].skills[technologyId] = {
                    name: technologyName,
                    level: skillLevel,
                    group_id: technology ? technology.group_id : null,
                    parent_id: technology ? technology.parent_id : null
                };
            }
            renderTechnicianSkills();
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating skill: ${error.message}`, 'error');
        console.error(error);
        await fetchTechnicianSkills(selectedTechnician);
    }
}
